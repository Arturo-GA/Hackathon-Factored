# Verificacion independiente (reintento) de "monto_uniforme_por_tipo" - parte 2: dependencia del monto con otras variables
import duckdb, numpy as np, pandas as pd, sys
SEC = sys.argv[1] if len(sys.argv) > 1 else 'ABCDE'
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
q = lambda s: con.execute(s).df()
LO = {'Purchase': 5, 'Withdrawal': 20, 'Payment': 50, 'Adjustment': 10, 'Deposit': 50, 'Transfer': 100}
HI = {'Purchase': 500, 'Withdrawal': 500, 'Payment': 2000, 'Adjustment': 1000, 'Deposit': 5000, 'Transfer': 10000}
K = "(case t.currency when 'ARS' then 350.0 when 'COP' then 4000.0 when 'USD' then 1.0 end)"
LOs = "(case t.ttype " + " ".join(f"when '{k}' then {v}" for k, v in LO.items()) + " end)"
HIs = "(case t.ttype " + " ".join(f"when '{k}' then {v}" for k, v in HI.items()) + " end)"
con.execute(f"""create temp view v as select t.*, t.amount/{K} a, (t.amount/{K} - {LOs})/({HIs}-{LOs}) u,
  year(t.ts) yr, month(t.ts) mo, dayofweek(t.ts) dow, hour(t.ts) hr, datediff('day', t.ts::date, t.process_date) lagd,
  cu.segment, cu.cstatus, cu.country cu_country, cu.occupation, cu.education_level, cu.gender, cu.income, cu.credit_score,
  cu.marital_status, (cu.mkt)::int mkt,
  p.ptype, p.pstatus, p.opening_channel, p.bal/{K} bal_usd, p.credit_limit/{K} lim_usd, p.rate prate, p.dpd,
  datediff('day', p.opened, t.ts::date) prod_age_d, datediff('day', cu.registration_date::date, t.ts::date) tenure_d
  from tx t left join cu using(customer_id) left join pr p on p.product_id=t.product_id""")

print("== A) ANOVA de u (posicion dentro del rango del ttype, uniforme[0,1] si la hipotesis es cierta) agrupando por ttype x variable")
print("   F ~ 1 => sin efecto; eta2_exceso = eta2 - (G-1)/(N-1) (lo que excede al azar); max_dif = max |media_grupo - 0.5| en grupos con n>=1000")
cat_vars = ['status', "coalesce(code,'NA')", 'fraud', "coalesce(floor(fscore/10)::varchar,'NA')", 'channel', 'country', 'country_raw', 'currency',
            'city', "coalesce(mcat,'NA')", "coalesce(tcat,'NA')", "coalesce(merchant_name,'NA')", "coalesce(branch_id,'NA')",
            'yr', 'mo', 'dow', 'hr', 'lagd', "coalesce(segment,'NA')", "coalesce(cstatus,'NA')", 'cu_country', 'occupation', 'education_level',
            'gender', 'marital_status', 'mkt', "coalesce(ptype,'NA')", "coalesce(pstatus,'NA')", 'opening_channel',
            "coalesce(floor(income/1e5)::varchar,'NA')", "floor(credit_score/50)", "floor(least(prod_age_d,3650)/180)", "floor(least(tenure_d,3650)/180)",
            'customer_id', 'product_id']
res = []
for g in (cat_vars if 'A' in SEC else []):
    d = q(f"""with s as (select ttype, {g} grp, count(*) n, avg(u) m, var_samp(u) vv from v group by all),
      tot as (select sum(n) N, sum(n*m)/sum(n) gm from s)
      select count(*) G, (select N from tot) N, sum(n*(m-(select gm from tot))^2) ssb, sum(case when n>1 then (n-1)*vv else 0 end) ssw,
      max(case when n>=1000 then abs(m-0.5) end) max_dif, count(*) filter (where n>=1000) g1000 from s""").iloc[0]
    G, N = d.G, d.N
    F = (d.ssb / (G - 1)) / (d.ssw / (N - G))
    eta2 = d.ssb / (d.ssb + d.ssw)
    res.append(dict(var=g[:40], G=int(G), N=int(N), F=F, p=stats.f.sf(F, G - 1, N - G), eta2=eta2, eta2_exceso=eta2 - (G - 1) / (N - 1),
                    max_dif_n1000=d.max_dif, grupos_n1000=int(d.g1000)))
r = pd.DataFrame(res) if res else None
if r is not None: print(r.to_string(index=False, float_format=lambda x: '%.4g' % x))

print("\n== B) Correlaciones numericas con u (nivel transaccion; Pearson y Spearman) ")
num = ['fscore', 'income', 'credit_score', 'bal_usd', 'lim_usd', 'prate', 'dpd', 'prod_age_d', 'tenure_d', 'lat', 'lon', 'hr', 'epoch(ts)']
for c in (num if 'B' in SEC else []):
    d = q(f"select count({c}) n, corr(u, {c}) r from v where {c} is not null").iloc[0]
    print(f"  {c:12s} n={int(d.n):8d} pearson r={d.r:+.5f}")
# Spearman sobre muestra (rank) para variables con colas
s = q("select u, fscore, income, credit_score, bal_usd, lim_usd, dpd from v using sample 300000 rows (reservoir, 7)")
print("  spearman (muestra 300k):", {c: round(stats.spearmanr(s.u, s[c], nan_policy='omit').statistic, 5) for c in ['fscore', 'income', 'credit_score', 'bal_usd', 'lim_usd', 'dpd']})

print("\n== C) Rechazo / codigo 51 / fraude por quintil de u (dentro del ttype) y por quintil del monto USD-eq absoluto")
qu = q("""select least(floor(u*5),4)::int quintil_u, count(*) n, avg((status='Declined')::int)*100 decl_pct, avg(coalesce(code='51',false)::int)*100 c51_pct,
  avg((code is not null)::int)*100 any_code_pct, avg(fraud::int)*1000 fraud_pm, avg(fscore) fscore_m from v group by 1 order by 1""")
print(qu.to_string(index=False, float_format=lambda x: '%.3f' % x))
qa = q("""with w as (select *, ntile(5) over (order by a) qa from v) select qa quintil_monto_usd, count(*) n, min(a) mn, max(a) mx,
  avg((status='Declined')::int)*100 decl_pct, avg(coalesce(code='51',false)::int)*100 c51_pct, avg(fraud::int)*1000 fraud_pm from w group by 1 order by 1""")
print(qa.to_string(index=False, float_format=lambda x: '%.3f' % x))
print("razon de tasas Q5/Q1 (u): decl=%.3f c51=%.3f fraude=%.3f | (monto abs): decl=%.3f c51=%.3f fraude=%.3f" % (
    qu.decl_pct.iloc[4] / qu.decl_pct.iloc[0], qu.c51_pct.iloc[4] / qu.c51_pct.iloc[0], qu.fraud_pm.iloc[4] / qu.fraud_pm.iloc[0],
    qa.decl_pct.iloc[4] / qa.decl_pct.iloc[0], qa.c51_pct.iloc[4] / qa.c51_pct.iloc[0], qa.fraud_pm.iloc[4] / qa.fraud_pm.iloc[0]))
# dentro de cada ttype: rango de la tasa de rechazo por quintil de u
qt = q("""select ttype, least(floor(u*5),4)::int qu, count(*) n, avg((status='Declined')::int)*100 decl, avg(coalesce(code='51',false)::int)*100 c51 from v group by all""")
print(qt.groupby('ttype').agg(n=('n', 'sum'), decl_min=('decl', 'min'), decl_max=('decl', 'max'), c51_min=('c51', 'min'), c51_max=('c51', 'max')).round(3).to_string())
print("tasa de rechazo por ttype:", q("select ttype, round(avg((status='Declined')::int)*100,3) decl from v group by 1 order by 1").values.tolist())
# AUC del monto (u y a) para predecir rechazo / fraude / codigo 51 (Mann-Whitney sobre todo el universo via rangos en SQL seria pesado: usar muestra grande)
s = q("select u, a, ttype, (status='Declined')::int decl, coalesce(code='51',false)::int c51, fraud::int fr from v using sample 300000 rows (reservoir, 11)")
from sklearn.metrics import roc_auc_score
for y in ['decl', 'c51', 'fr']:
    print(f"  AUC u->{y}: {roc_auc_score(s[y], s.u):.4f}   AUC monto_abs->{y}: {roc_auc_score(s[y], s.a):.4f}  (positivos={s[y].sum()})")

print("\n== D) Efecto cliente / producto: varianza de medias vs iid, split-half y autocorrelacion lag-1")
for key in ['customer_id', 'product_id']:
    d = q(f"""with c as (select {key}, count(*) n, avg(u) mu from v group by 1 having count(*)>=20)
      select count(*) k, avg(n) n_medio, var_samp(mu) var_medias, avg(1.0/12/n) var_esperada from c""").iloc[0]
    print(f"  {key}: grupos con >=20 tx = {int(d.k)}, tx medio={d.n_medio:.1f}, var_medias={d.var_medias:.6f}, esperada iid={d.var_esperada:.6f}, razon={d.var_medias/d.var_esperada:.4f}")
# split-half: media de u en tx pares vs impares por cliente (orden por transaction_id)
d = q("""with w as (select customer_id, u, row_number() over (partition by customer_id order by transaction_id) rn from v),
  c as (select customer_id, avg(u) filter (where rn%2=0) m0, avg(u) filter (where rn%2=1) m1, count(*) n from w group by 1 having count(*)>=20)
  select count(*) k, corr(m0,m1) r from c""").iloc[0]
print(f"  split-half (clientes >=20 tx): k={int(d.k)}, corr(media pares, media impares) = {d.r:+.4f}")
d = q("""with w as (select customer_id, u, lag(u) over (partition by customer_id order by ts, transaction_id) u1 from v)
  select count(u1) n, corr(u, u1) r from w""").iloc[0]
print(f"  autocorrelacion lag-1 de u dentro de cliente (orden temporal): n={int(d.n)}, r={d.r:+.5f}")
d = q("""with w as (select product_id, u, lag(u) over (partition by product_id order by ts, transaction_id) u1 from v)
  select count(u1) n, corr(u, u1) r from w""").iloc[0]
print(f"  autocorrelacion lag-1 de u dentro de producto: n={int(d.n)}, r={d.r:+.5f}")

print("\n== E) Deriva temporal: media de u por anio y moneda (EE = sqrt(1/12/n))")
y = q("select yr, currency, count(*) n, avg(u) mu from v group by all order by 1,2")
y['ee'] = np.sqrt(1 / 12 / y.n); y['z'] = (y.mu - 0.5) / y.ee
print(y.to_string(index=False, float_format=lambda x: '%.5f' % x))
y2 = q("select yr, count(*) n, avg(u) mu from v group by 1 order by 1"); y2['ee'] = np.sqrt(1 / 12 / y2.n)
print(y2.to_string(index=False, float_format=lambda x: '%.5f' % x))
