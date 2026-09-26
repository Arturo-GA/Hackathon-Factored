# Verificacion independiente (reintento) de "monto_uniforme_por_tipo" - parte 3: modelo held-out agrupado por cliente
import os
os.environ.setdefault('OMP_NUM_THREADS', '2')
import duckdb, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
LO = {'Purchase': 5, 'Withdrawal': 20, 'Payment': 50, 'Adjustment': 10, 'Deposit': 50, 'Transfer': 100}
HI = {'Purchase': 500, 'Withdrawal': 500, 'Payment': 2000, 'Adjustment': 1000, 'Deposit': 5000, 'Transfer': 10000}
K = lambda c: f"(case {c} when 'ARS' then 350.0 when 'COP' then 4000.0 when 'USD' then 1.0 end)"
LOs = "(case ttype " + " ".join(f"when '{k}' then {v}" for k, v in LO.items()) + " end)"
HIs = "(case ttype " + " ".join(f"when '{k}' then {v}" for k, v in HI.items()) + " end)"

# u de TODAS las tx (para rasgos leave-one-out del mismo cliente/producto y el u de la tx previa del cliente)
con.execute(f"""create temp table uu as select transaction_id, customer_id, product_id, ts, (amount/{K('currency')} - {LOs})/({HIs}-{LOs}) u from tx""")
con.execute("""create temp table cagg as select customer_id, count(*) cn, sum(u) cs from uu group by 1""")
con.execute("""create temp table pagg as select product_id, count(*) pn, sum(u) ps from uu group by 1""")
con.execute("""create temp table samp as select * from tx using sample 250000 rows (reservoir, 2026)""")
con.execute("""create temp table lagu as select l.transaction_id, l.u_prev from (select transaction_id, lag(u) over (partition by customer_id order by ts, transaction_id) u_prev from uu) l
  semi join samp s on s.transaction_id=l.transaction_id""")
df = con.execute(f"""select t.customer_id, t.ttype, t.channel, t.status, coalesce(t.code,'NA') code, t.country, t.country_raw, t.currency, t.city,
  coalesce(t.mcat,'NA') mcat, coalesce(t.tcat,'NA') tcat, coalesce(t.merchant_name,'NA') merchant, (t.branch_id is null)::int no_branch,
  hour(t.ts) h, dayofweek(t.ts) dow, day(t.ts) dom, month(t.ts) m, year(t.ts) y, datediff('day', t.ts::date, t.process_date) lagd,
  t.fscore, t.fraud::int fraud, t.lat, t.lon,
  cu.segment, cu.income/(case cu.country when 'Argentina' then 350.0 when 'Colombia' then 4000.0 else 17.0 end) inc_usd, cu.credit_score,
  cu.cstatus, cu.occupation, cu.education_level, cu.gender, cu.marital_status, cu.mkt::int mkt, datediff('year', cu.dob, t.ts::date) age,
  datediff('day', cu.registration_date::date, t.ts::date) tenure, (cu.country <> t.country)::int foreign_tx,
  p.ptype, p.pstatus, p.opening_channel, p.app::int app, p.bal/{K('p.currency')} bal_usd, p.credit_limit/{K('p.currency')} lim_usd, p.rate prate, p.dpd,
  datediff('day', p.opened, t.ts::date) prod_age,
  c.cn - 1 cust_ntx_otros, (c.cs - (t.amount/{K('t.currency')} - {LOs.replace('ttype', 't.ttype')})/({HIs.replace('ttype', 't.ttype')}-{LOs.replace('ttype', 't.ttype')}))/nullif(c.cn-1,0) cust_u_loo,
  (pa.ps - (t.amount/{K('t.currency')} - {LOs.replace('ttype', 't.ttype')})/({HIs.replace('ttype', 't.ttype')}-{LOs.replace('ttype', 't.ttype')}))/nullif(pa.pn-1,0) prod_u_loo,
  lg.u_prev,
  t.amount/{K('t.currency')} a
  from samp t left join cu using(customer_id) left join pr p on p.product_id=t.product_id
  left join cagg c on c.customer_id=t.customer_id left join pagg pa on pa.product_id=t.product_id
  left join lagu lg on lg.transaction_id=t.transaction_id""").df()
print("filas muestra:", len(df), " clientes:", df.customer_id.nunique())
df['u'] = (df.a - df.ttype.map(LO)) / (df.ttype.map(HI) - df.ttype.map(LO))
df['la'] = np.log(df.a)
cats = ['ttype', 'channel', 'status', 'code', 'country', 'country_raw', 'currency', 'city', 'mcat', 'tcat', 'merchant', 'segment', 'cstatus',
        'occupation', 'education_level', 'gender', 'marital_status', 'ptype', 'pstatus', 'opening_channel']
for c in cats:
    df[c] = df[c].astype('category').cat.codes.astype('int16')
base = [c for c in df.columns if c not in ('customer_id', 'a', 'u', 'la', 'cust_ntx_otros', 'cust_u_loo', 'prod_u_loo', 'u_prev')]
hist = ['cust_ntx_otros', 'cust_u_loo', 'prod_u_loo', 'u_prev']
print("n rasgos base:", len(base), "| rasgos historicos (LOO cliente/producto, u previo):", hist)

gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=123)
tr, te = next(gss.split(df, groups=df.customer_id))
te_groups = df.customer_id.values[te]
ug, inv = np.unique(te_groups, return_inverse=True)
rng = np.random.default_rng(1)
# bootstrap por conglomerados (cliente) sobre el conjunto de prueba
boot_idx = []
order = np.argsort(inv); starts = np.searchsorted(inv[order], np.arange(len(ug)))
ends = np.append(starts[1:], len(inv))
for _ in range(300):
    pick = rng.integers(0, len(ug), len(ug))
    boot_idx.append(np.concatenate([order[starts[g]:ends[g]] for g in pick]))

def fit_eval(target, feats, label):
    catmask = [c in cats for c in feats]
    m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=50,
                                      categorical_features=catmask if any(catmask) else None,
                                      early_stopping=True, validation_fraction=0.1, n_iter_no_change=20, random_state=0)
    m.fit(df.iloc[tr][feats], df.iloc[tr][target])
    p = m.predict(df.iloc[te][feats]); y = df.iloc[te][target].values
    r = r2_score(y, p)
    bs = [r2_score(y[i], p[i]) for i in boot_idx]
    print(f"  {label:55s} R2={r:+.4f}  IC95 cluster-bootstrap=[{np.percentile(bs, 2.5):+.4f}, {np.percentile(bs, 97.5):+.4f}]  iter={m.n_iter_}")
    return r

print("\n== Modelos (train 70% / test 30% agrupado por cliente)")
fit_eval('la', ['ttype'], 'log(monto USD-eq) ~ solo ttype')
fit_eval('la', base, f'log(monto USD-eq) ~ {len(base)} rasgos (incl. ttype)')
fit_eval('la', base + hist, f'log(monto USD-eq) ~ {len(base)+len(hist)} rasgos (+historia cliente/producto)')
fit_eval('u', [f for f in base if f != 'ttype'], f'u (posicion en rango) ~ {len(base)-1} rasgos sin ttype')
fit_eval('u', base + hist, f'u ~ {len(base)+len(hist)} rasgos (+LOO cliente, LOO producto, u previo)')
fit_eval('u', hist, 'u ~ solo historia (LOO cliente/producto, u previo)')

# R2 teorico de log(monto) | ttype bajo el modelo uniforme con la mezcla de ttype observada
def mom(lo, hi):
    f1 = lambda x: x * np.log(x) - x
    f2 = lambda x: x * (np.log(x) ** 2 - 2 * np.log(x) + 2)
    e1 = (f1(hi) - f1(lo)) / (hi - lo); e2 = (f2(hi) - f2(lo)) / (hi - lo)
    return e1, e2 - e1 ** 2
mix = con.execute("select ttype, count(*)::double / (select count(*) from tx) w from tx group by 1").df().set_index('ttype').w
E = {t: mom(LO[t], HI[t]) for t in LO}
gm = sum(mix[t] * E[t][0] for t in LO)
vb = sum(mix[t] * (E[t][0] - gm) ** 2 for t in LO); vw = sum(mix[t] * E[t][1] for t in LO)
print(f"\nR2 teorico de log(monto)|ttype bajo Uniforme(lo,hi) con la mezcla real: {vb/(vb+vw):.4f}")
# R2 empirico (todas las filas) de log(a) con medias por ttype
d = con.execute(f"""with v as (select ttype, ln(amount/{K('currency')}) la from tx), s as (select ttype, count(*) n, avg(la) m, var_pop(la) vv from v group by 1)
  select sum(n*vv)/sum(n) vwithin, (select var_pop(la) from v) vtotal from s""").df().iloc[0]
print(f"R2 empirico (4.4M filas) de log(monto) explicado por ttype: {1 - d.vwithin/d.vtotal:.4f}")
print("medias de rasgos historicos en test: corr(u, cust_u_loo)=%.4f corr(u, prod_u_loo)=%.4f corr(u,u_prev)=%.4f" % (
    df.u.corr(df.cust_u_loo), df.u.corr(df.prod_u_loo), df.u.corr(df.u_prev)))
