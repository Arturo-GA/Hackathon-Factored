"""Verificación independiente (reintento) de 'fraud_geo_inutilizable'.
Parte 3: ¿el RR ~1.39 lejos/cerca de la sucursal (estratificado por país del cliente) es señal geográfica o azar?
'Cerca' se define SOLO con coordenadas de la sucursal vs ancla del país del cliente (sin usar coords de la tx),
así se puede replicar en las tx SIN coordenadas (muestra independiente).
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_fraud_geo_inutilizable_repro_retry3.py
"""
import duckdb, pandas as pd, numpy as np
from scipy import stats
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

def show(title, sql):
    d = con.execute(sql).df()
    print('##', title); print(d.to_string(index=False)); print()
    return d

con.execute("""create temp table anc as
select cu.country cc, (min(t.lat)+max(t.lat))/2 alat, (min(t.lon)+max(t.lon))/2 alon
from tx t join cu using(customer_id) where t.lat is not null group by 1""")
# distancia sucursal -> ancla del país del cliente (independiente de la tx)
con.execute("""create temp table bt as
select t.customer_id, t.fraud, t.channel, t.lat is not null tiene_lat, cu.country cc, b.city bcity,
  2*6371*asin(sqrt(pow(sin(radians(b.lat-a.alat)/2),2)+cos(radians(a.alat))*cos(radians(b.lat))*pow(sin(radians(b.lon-a.alon)/2),2))) km_br_ancla
from tx t join br b using(branch_id) join cu using(customer_id) join anc a on a.cc=cu.country""")

show('3a ciudad de sucursal: distancia media al ancla del país del cliente', """
select cc, bcity, count(*) n, round(avg(km_br_ancla),0) km_medio, round(min(km_br_ancla),0) km_min, round(max(km_br_ancla),0) km_max
from bt group by all order by 1,4""")

def mh(df, label):
    num = den = 0.0; var_num = 0.0
    rows = []
    for cc, g in df.groupby('cc'):
        g = g.set_index('lejos'); N = g.n.sum()
        a, n1 = g.loc[True, 'f'], g.loc[True, 'n']; c, n0 = g.loc[False, 'f'], g.loc[False, 'n']
        num += a*n0/N; den += c*n1/N
        rows.append(f'{cc}: lejos {int(a)}/{int(n1)} ({1e3*a/n1:.3f}‰) cerca {int(c)}/{int(n0)} ({1e3*c/n0:.3f}‰) RR={(a/n1)/(c/n0):.2f}')
    rr = num/den
    # IC aproximado con log-RR y conteos totales
    A = df[df.lejos].f.sum(); C = df[~df.lejos].f.sum()
    se = np.sqrt(1/A + 1/C)
    print(f'## {label}: RR_MH={rr:.3f} IC95~[{rr*np.exp(-1.96*se):.3f}, {rr*np.exp(1.96*se):.3f}] (fraudes lejos={int(A)}, cerca={int(C)})')
    for r in rows: print('    ', r)
    print()

for sub, cond in [('tx CON lat (subconjunto del hallazgo)', 'tiene_lat'), ('tx SIN lat (réplica independiente)', 'not tiene_lat'), ('todas las tx con branch_id', 'true')]:
    df = con.execute(f"select cc, (km_br_ancla>=200) lejos, count(*) n, sum(fraud::int) f from bt where {cond} group by all").df()
    mh(df, f'3b sucursal lejos (>=200 km del ancla) vs cerca — {sub}')

show('3c tasa de fraude por ciudad de sucursal: con lat vs sin lat', """
select cc, bcity, round(avg(km_br_ancla),0) km,
  count(*) filter (where tiene_lat) n_con, sum(fraud::int) filter (where tiene_lat) f_con, round(1e3*avg(fraud::int) filter (where tiene_lat),3) pm_con,
  count(*) filter (where not tiene_lat) n_sin, sum(fraud::int) filter (where not tiene_lat) f_sin, round(1e3*avg(fraud::int) filter (where not tiene_lat),3) pm_sin
from bt group by all order by 1,3""")
d = con.execute("select bcity, tiene_lat, count(*) n, sum(fraud::int) f from bt group by all").df()
for flag, lab in [(True, 'con lat'), (False, 'sin lat')]:
    x = d[d.tiene_lat == flag]
    chi = stats.chi2_contingency(np.c_[x.f, x.n - x.f])
    print(f'## 3d homogeneidad de fraude entre 16 ciudades de sucursal ({lab}): chi2={chi[0]:.1f}, gl={chi[2]}, p={chi[1]:.3f}')
x = d.groupby('bcity')[['n', 'f']].sum()
chi = stats.chi2_contingency(np.c_[x.f, x.n - x.f])
print(f'## 3d homogeneidad entre ciudades (todas): chi2={chi[0]:.1f}, gl={chi[2]}, p={chi[1]:.3f}')
# correlación entre tasas por ciudad con lat y sin lat (¿el patrón se replica?)
p = d.pivot(index='bcity', columns='tiene_lat', values=['n', 'f'])
r_con = p[('f', True)]/p[('n', True)]; r_sin = p[('f', False)]/p[('n', False)]
print(f'## 3e correlación (Spearman) de la tasa por ciudad con lat vs sin lat: rho={stats.spearmanr(r_con, r_sin)[0]:.3f}, p={stats.spearmanr(r_con, r_sin)[1]:.3f}\n')
show('3f fraude por canal (ATM/Branch) con y sin lat', """
select channel, tiene_lat, count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from bt group by all order by 1,2""")
