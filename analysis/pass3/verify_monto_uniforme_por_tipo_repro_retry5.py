# Verificacion independiente (reintento) de "monto_uniforme_por_tipo" - parte 5: homogeneidad de la DISTRIBUCION completa de u
# (no solo la media) entre grupos: tabla (ttype x grupo) x decil de u -> chi2 de homogeneidad y V de Cramer; min/max/var de u por grupo
import duckdb, numpy as np, pandas as pd
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250)
q = lambda s: con.execute(s).df()
K = "(case t.currency when 'ARS' then 350.0 when 'COP' then 4000.0 when 'USD' then 1.0 end)"
LOs = "(case t.ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Payment' then 50 when 'Adjustment' then 10 when 'Deposit' then 50 else 100 end)"
HIs = "(case t.ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Payment' then 2000 when 'Adjustment' then 1000 when 'Deposit' then 5000 else 10000 end)"
con.execute(f"""create temp table w as select t.ttype, t.currency, t.channel, t.status, coalesce(t.code,'NA') code, t.fraud::int fraud,
  coalesce(floor(t.fscore/10)::int::varchar,'NA') fsb, t.country, coalesce(t.mcat,'NA') mcat, year(t.ts) yr, cu.segment, p.ptype,
  least(floor((t.amount/{K} - {LOs})/({HIs}-{LOs})*10),9)::int decil, (t.amount/{K} - {LOs})/({HIs}-{LOs}) u
  from tx t left join cu using(customer_id) left join pr p on p.product_id=t.product_id""")
rows = []
for g in ['currency', 'channel', 'status', 'code', 'fraud', 'fsb', 'country', 'mcat', 'yr', 'segment', 'ptype']:
    d = q(f"select ttype, coalesce({g}::varchar,'NA') grp, decil, count(*) n from w group by all")
    chi_tot, df_tot, N, vmax = 0.0, 0, 0, 0.0
    for t, gt in d.groupby('ttype'):
        tab = gt.pivot_table(index='grp', columns="decil", values='n', fill_value=0, aggfunc='sum')
        tab = tab[tab.sum(axis=1) >= 200]  # grupos con n suficiente
        if tab.shape[0] < 2: continue
        c = stats.chi2_contingency(tab.values, correction=False)
        n = tab.values.sum(); v = np.sqrt(c.statistic / (n * (min(tab.shape) - 1)))
        chi_tot += c.statistic; df_tot += c.dof; N += n; vmax = max(vmax, v)
    rows.append(dict(var=g, chi2=round(chi_tot, 1), gl=df_tot, p=stats.chi2.sf(chi_tot, df_tot), chi2_sobre_gl=chi_tot / df_tot, V_cramer_max_por_ttype=vmax, N=N))
print("== Homogeneidad de la distribucion de u (deciles) entre grupos, dentro de cada ttype (chi2 sumado sobre ttypes)")
print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: '%.4g' % x))
print("\n== Rango y varianza de u por ttype x ptype y ttype x channel (uniforme: min~0, max~1, var=0.0833)")
for g in ['ptype', 'channel']:
    d = q(f"select ttype, {g} grp, count(*) n, min(u) mn, max(u) mx, var_samp(u) var_u from w group by all having count(*)>=1000 order by 1,2")
    print(f"  {g}: grupos={len(d)}  min(u) max={d.mn.max():.5f}  max(u) min={d.mx.min():.5f}  var_u rango=[{d.var_u.min():.5f}, {d.var_u.max():.5f}]")
print(q("select ttype, ptype, count(*) n from w group by all order by 1, 3 desc").groupby('ttype').head(3).to_string(index=False))
