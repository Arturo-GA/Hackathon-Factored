"""Verificación independiente (reintento) de 'fraud_geo_inutilizable'.
Parte 2: coordenadas de sucursales, distancia tx-sucursal, fraude por tramo de distancia (cortes del original),
confusión por país del cliente / tipo de sucursal.
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_fraud_geo_inutilizable_repro_retry2.py
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

BASE = con.execute("select avg(fraud::int) from tx").fetchone()[0]
print(f'tasa base de fraude (todas las tx): {1e3*BASE:.4f} por mil\n')

# ---------------------------------------------------------------- 1. sucursales
show('1a sucursales por país y ciudad: coordenadas', """
select country, city, count(*) n, round(avg(lat),3) mlat, round(stddev(lat),3) sdlat, round(avg(lon),3) mlon,
  round(max(abs(lat)),3) max_abs_lat, sum((abs(lat)<1 and abs(lon)<1)::int) n_cerca_00
from br group by all order by 1,2""")
show('1b sucursales cerca de (0,0) en total', """
select count(*) n_br, sum((abs(lat)<1 and abs(lon)<1)::int) n_00, count(distinct city) filter (where abs(lat)<1 and abs(lon)<1) n_ciudades_00,
  count(distinct city) n_ciudades, round(max(greatest(abs(lat),abs(lon))) filter (where abs(lat)<1 and abs(lon)<1),3) max_desvio_00
from br""")
show('1c branch_id por canal y join con br', """
select channel, count(*) n, round(100.0*count(branch_id)/count(*),2) pct_branch, count(b.branch_id) n_join_br
from tx t left join br b using(branch_id) group by 1 order by n desc""")
show('1d país sucursal vs país cliente vs país tx; ciudad sucursal vs ciudad tx', """
select count(*) n,
  round(100*avg((b.country=cu.country)::int),2) pct_br_pais_cliente,
  round(100*avg((b.country=t.country)::int),2) pct_br_pais_tx,
  round(100*avg((b.country=t.country)::int) filter (where t.country<>cu.country),2) pct_br_pais_tx_en_foraneas,
  round(100*avg((b.city=t.city)::int) filter (where t.city is not null),2) pct_br_ciudad_tx
from tx t join br b using(branch_id) join cu using(customer_id)""")

# ---------------------------------------------------------------- 2. distancias
HAV = "2*6371*asin(sqrt(pow(sin(radians(b.lat-t.lat)/2),2)+cos(radians(t.lat))*cos(radians(b.lat))*pow(sin(radians(b.lon-t.lon)/2),2)))"
EQR = "111*sqrt(pow(t.lat-b.lat,2)+pow((t.lon-b.lon)*cos(radians(t.lat)),2))"
con.execute(f"""create temp table d as
select t.customer_id, t.fraud, t.lat is not null and t.lon is not null ambas, cu.country cc, b.country bc, b.city bcity,
  (abs(b.lat)<1 and abs(b.lon)<1) br00, {HAV} km_hav, {EQR} km_eqr
from tx t join br b using(branch_id) join cu using(customer_id) where t.lat is not null""")
show('2a tamaño del subconjunto (lat no nula y branch_id válido)', """
select count(*) n, sum(fraud::int) f, count(km_hav) n_km_no_nulo, sum((km_hav is null)::int) n_km_nulo, sum((km_hav is null and fraud)::int) f_km_nulo from d""")
show('2b % >50 km por fraude (haversine y equirectangular; km no nulo)', """
select fraud, count(km_hav) n, round(100*avg((km_hav>50)::int),2) pct_gt50_hav, round(100*avg((km_eqr>50)::int),2) pct_gt50_eqr,
  round(100*avg((km_hav>100)::int),2) pct_gt100, round(median(km_hav),1) mediana_km
from d where km_hav is not null group by 1 order by 1""")
show('2c % >50 km legítimas por tipo de sucursal ((0,0) vs real)', """
select br00, count(*) n, round(100*avg((km_hav>50)::int),2) pct_gt50, round(median(km_hav),1) mediana_km,
  round(quantile_cont(km_hav,0.05),1) p05, round(quantile_cont(km_hav,0.95),1) p95
from d where km_hav is not null and not fraud group by 1 order by 1""")

def bins_table(title, where_null_to_else=True, col='km_eqr'):
    # cortes del original; si where_null_to_else, las filas con km NULL caen al ELSE (bug del original)
    cond = '' if where_null_to_else else f'where {col} is not null'
    r = con.execute(f"""
      select case when {col}<100 then 'a<100' when {col}<500 then 'b<500' when {col}<1000 then 'c<1000'
                  when {col}<3000 then 'd<3000' when {col}<6000 then 'e<6000' else 'f>=6000' end bin,
        count(*) n, sum(fraud::int) f from d {cond} group by 1 order by 1""").df()
    base_sub = r.f.sum()/r.n.sum()
    r['rate_pm'] = 1e3*r.f/r.n
    r['rr_vs_base_global'] = (r.f/r.n)/BASE
    lo, hi = [], []
    for _, x in r.iterrows():
        n1, f1 = x.n, x.f; n0, f0 = r.n.sum()-n1, r.f.sum()-f1
        rr = (f1/n1)/(f0/n0); se = np.sqrt(1/f1-1/n1+1/f0-1/n0) if f1 > 0 else np.nan
        lo.append(rr*np.exp(-1.96*se)); hi.append(rr*np.exp(1.96*se))
    r['rr_vs_resto'] = [(x.f/x.n)/((r.f.sum()-x.f)/(r.n.sum()-x.n)) for _, x in r.iterrows()]
    r['ic95_lo'] = lo; r['ic95_hi'] = hi
    chi = stats.chi2_contingency(np.c_[r.f, r.n-r.f])
    print('##', title); print(r.round(3).to_string(index=False))
    print(f'   base del subconjunto {1e3*base_sub:.3f} por mil; chi2 homogeneidad={chi[0]:.2f}, gl={chi[2]}, p={chi[1]:.3f}\n')
    return r

bins_table('2d fraude por tramo (cortes y fórmula del original, km NULL -> ELSE)', True)
bins_table('2e fraude por tramo, excluyendo km NULL (equirectangular)', False)
bins_table('2f fraude por tramo, excluyendo km NULL (haversine)', False, 'km_hav')

# ---------------------------------------------------------------- 3. confusión / mezcla
show('3a tasa de fraude por país del cliente (todas las tx) y en el subconjunto con distancia', """
select cu.country cc, count(*) n, sum(t.fraud::int) f, round(1e3*avg(t.fraud::int),3) rate_pm
from tx t join cu using(customer_id) group by 1 order by 1""")
show('3b composición de los tramos por país del cliente y tipo de sucursal', """
select case when km_eqr<100 then 'a<100' when km_eqr<500 then 'b<500' when km_eqr<1000 then 'c<1000'
            when km_eqr<3000 then 'd<3000' when km_eqr<6000 then 'e<6000' else 'f>=6000' end bin,
  count(*) n, round(100*avg((cc='México')::int),1) pct_mx, round(100*avg((cc='Colombia')::int),1) pct_co,
  round(100*avg((cc='Argentina')::int),1) pct_ar, round(100*avg(br00::int),1) pct_br00
from d where km_eqr is not null group by 1 order by 1""")
show('3c mediana km por fraude dentro de país de la sucursal (=país del cliente)', """
select bc, fraud, count(*) n, round(median(km_hav),1) mediana_km, round(100*avg((km_hav<200)::int),1) pct_cerca_lt200
from d where km_hav is not null group by all order by 1,2""")
show('3d tasa de fraude sucursal (0,0) vs real, dentro de país cliente (subconjunto con distancia)', """
select cc, br00, count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm
from d where km_hav is not null group by all order by 1,2""")
show('3e tasa de fraude sucursal (0,0) vs real, TODAS las tx con branch_id (sin requerir coords)', """
select (abs(b.lat)<1 and abs(b.lon)<1) br00, count(*) n, sum(t.fraud::int) f, round(1e3*avg(t.fraud::int),3) rate_pm
from tx t join br b using(branch_id) group by 1 order by 1""")
# Mantel-Haenszel RR lejos (>=200 km) vs cerca (<200 km), estratificado por país del cliente
m = con.execute("""select cc, (km_hav>=200) lejos, count(*) n, sum(fraud::int) f from d where km_hav is not null group by all""").df()
num = den = 0.0
for cc, g in m.groupby('cc'):
    g = g.set_index('lejos'); N = g.n.sum()
    a, n1 = g.loc[True, 'f'], g.loc[True, 'n']; c, n0 = g.loc[False, 'f'], g.loc[False, 'n']
    num += a*n0/N; den += c*n1/N
    print(f'   {cc}: lejos {a}/{n1} ({1e3*a/n1:.3f}‰)  cerca {c}/{n0} ({1e3*c/n0:.3f}‰)  RR={(a/n1)/(c/n0):.3f}')
print(f'## 3f RR Mantel-Haenszel lejos(>=200km) vs cerca, estratificado por país cliente = {num/den:.3f}\n')
