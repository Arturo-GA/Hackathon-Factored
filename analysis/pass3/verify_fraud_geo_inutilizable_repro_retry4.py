"""Verificación independiente (reintento) de 'fraud_geo_inutilizable'.
Parte 4: distancia a la tx previa (definición del original y variante 'previa con coordenadas'),
esperado bajo ruido U(-1,1) independiente, y AUC de features geográficas de fraude (IC95 bootstrap por cliente).
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_fraud_geo_inutilizable_repro_retry4.py
"""
import duckdb, pandas as pd, numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

def show(title, sql):
    d = con.execute(sql).df()
    print('##', title); print(d.to_string(index=False)); print()
    return d

BASE = con.execute("select avg(fraud::int) from tx").fetchone()[0]
EQ = lambda a: f"111*sqrt(pow(lat-{a}lat,2)+pow((lon-{a}lon)*cos(radians(lat)),2))"
HV = lambda a: f"2*6371*asin(sqrt(pow(sin(radians({a}lat-lat)/2),2)+cos(radians(lat))*cos(radians({a}lat))*pow(sin(radians({a}lon-lon)/2),2)))"

# ---------------------------------------------------------------- 1. tx previa inmediata (cualquier canal), como el original
con.execute("""create temp table s as
select customer_id, fraud, lat, lon, lag(lat) over w plat, lag(lon) over w plon
from (select customer_id, ts, transaction_id, fraud, lat, lon from tx)
window w as (partition by customer_id order by ts, transaction_id)""")
con.execute("delete from s where lat is null or plat is null")   # solo pares con lat en ambas (tabla temporal propia)
show('1a tx previa inmediata del cliente (lat en ambas): pares, <10 km y fraudes', f"""
select count(*) n_pares_lat, count(*) filter (where lon is not null and plon is not null) n_pares_ambas,
  count(*) filter (where {EQ('p')}<10) n_lt10_eqr, count(*) filter (where {EQ('p')}<10 and fraud) f_lt10_eqr,
  count(*) filter (where {HV('p')}<10) n_lt10_hav, count(*) filter (where {HV('p')}<10 and fraud) f_lt10_hav,
  sum(fraud::int) f_total_pares
from s""")
r = show('1b fraude por tramo de distancia a la previa inmediata (pares con lat y lon en ambas)', f"""
with x as (select fraud, {HV('p')} km from s where lon is not null and plon is not null)
select case when km<10 then 'a<10' when km<50 then 'b<50' when km<100 then 'c<100' when km<200 then 'd<200' else 'e>=200' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from x group by 1 order by 1""")
# esperado bajo ruido U(-1,1) independiente en lat y lon, mismo ancla (el cliente no cambia de país ancla)
rng = np.random.default_rng(0)
m = 2_000_000
exp_p = {}
for name, alat in [('México', 0.0), ('Colombia', 4.711), ('Argentina', -34.6037)]:
    la1, la2 = alat+rng.uniform(-1, 1, m), alat+rng.uniform(-1, 1, m)
    dlo = rng.uniform(-1, 1, m)-rng.uniform(-1, 1, m)
    p1, p2 = np.radians(la1), np.radians(la2)
    dd = 2*6371*np.arcsin(np.sqrt(np.sin((p2-p1)/2)**2+np.cos(p1)*np.cos(p2)*np.sin(np.radians(dlo)/2)**2))
    exp_p[name] = np.mean(dd < 10)
npairs = con.execute("""select cu.country cc, count(*) n from s join cu using(customer_id) where lon is not null and plon is not null group by 1""").df()
npairs['p_lt10_sim'] = npairs.cc.map(exp_p); npairs['esperado_lt10'] = npairs.n*npairs.p_lt10_sim
print('## 1c esperado de pares <10 km si lat/lon = ancla + U(-1,1) independiente'); print(npairs.round(5).to_string(index=False))
print(f'   total esperado = {npairs.esperado_lt10.sum():.0f}; fraudes esperados entre <10 km a tasa base = {r.n.iloc[0]*BASE:.2f}\n')

# ---------------------------------------------------------------- 2. features con ancla del cliente y previa/siguiente CON coordenadas
con.execute("""create temp table anc as
select cu.country cc, (min(t.lat)+max(t.lat))/2 alat, (min(t.lon)+max(t.lon))/2 alon
from tx t join cu using(customer_id) where t.lat is not null group by 1""")
con.execute(f"""create temp table g as
with base as (
  select t.customer_id, t.transaction_id, t.ts, t.fraud, t.channel, cu.country cc, t.lat, t.lon, t.lat-a.alat dlat, t.lon-a.alon dlon
  from tx t join cu using(customer_id) join anc a on a.cc=cu.country where t.lat is not null and t.lon is not null),
w as (select *, lag(lat) over v plat, lag(lon) over v plon, lead(lat) over v nlat, lead(lon) over v nlon
      from base window v as (partition by customer_id order by ts, transaction_id))
select customer_id, fraud, channel, cc, year(ts) yr, dlat, dlon, {HV('p')} dprev, {HV('n')} dnext from w""")
show('2a tamaño', "select count(*) n, sum(fraud::int) f, count(dprev) n_dprev, sum(fraud::int) filter (where dprev is not null) f_dprev from g")
show('2b |dlat| y |dlon| respecto al ancla: fraude vs legítima (esperado U(0,1): media 0.5)', """
select fraud, count(*) n, round(avg(abs(dlat)),4) m_adlat, round(avg(abs(dlon)),4) m_adlon, round(stddev(dlat),4) sd_dlat, round(stddev(dlon),4) sd_dlon
from g group by 1 order by 1""")
show('2c fraude por tramo de distancia a la previa CON coordenadas', """
select case when dprev<10 then 'a<10' when dprev<50 then 'b<50' when dprev<100 then 'c<100' when dprev<200 then 'd<200' else 'e>=200' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from g where dprev is not null group by 1 order by 1""")

# muestra para pandas: todas las filas fraude + legítimas de ~25% de clientes (por hash)
df = con.execute("""select customer_id, fraud::int y, cc, channel, yr, abs(dlat) adlat, abs(dlon) adlon, dprev, dnext
  from g where fraud or hash(customer_id)%4=0""").df()
print(f'muestra: {len(df)} filas, {df.y.sum()} fraudes, {df.customer_id.nunique()} clientes\n')
f = df[df.y == 1]
for c in ['adlat', 'adlon']:
    ks = stats.kstest(f[c], 'uniform')
    print(f'## 2d KS {c} de fraude vs U(0,1): media={f[c].mean():.4f} (ee {0.2887/np.sqrt(len(f)):.4f}), D={ks.statistic:.4f}, p={ks.pvalue:.4g}')
print()

def auc_ci(y, s, g, B=400, seed=0):
    a = roc_auc_score(y, s)
    ug, inv = np.unique(g, return_inverse=True)
    order = np.argsort(inv, kind='stable'); starts = np.searchsorted(inv[order], np.arange(len(ug)+1))
    r = np.random.default_rng(seed); out = []
    for _ in range(B):
        pick = r.integers(0, len(ug), len(ug))
        ii = np.concatenate([order[starts[p]:starts[p+1]] for p in pick])
        if 0 < y[ii].sum() < len(ii): out.append(roc_auc_score(y[ii], s[ii]))
    return a, np.percentile(out, 2.5), np.percentile(out, 97.5)

y = df.y.values; gid = df.customer_id.values
feats = {'-|dlat|': -df.adlat.values, '-|dlon|': -df.adlon.values,
         '-dist_ancla': -np.hypot(df.adlat.values, df.adlon.values)}
for k, s in feats.items():
    a, lo, hi = auc_ci(y, s, gid); print(f'## 2e AUC {k}: {a:.4f} [{lo:.4f}, {hi:.4f}]')
for col in ['dprev', 'dnext']:
    mk = df[col].notna().values
    a, lo, hi = auc_ci(y[mk], -df.loc[mk, col].values, gid[mk]); print(f'## 2e AUC -{col}: {a:.4f} [{lo:.4f}, {hi:.4f}] (fraudes {y[mk].sum()})')
print()
# réplica por mitades independientes: por año y por mitad de clientes
df['half'] = (pd.util.hash_pandas_object(df.customer_id, index=False) % 2).values
for grp in ['half', 'cc', 'channel']:
    rows = []
    for k, gg in df.groupby(grp):
        m2 = gg.dprev.notna()
        rows.append(f'{grp}={k}: fraudes={gg.y.sum()} media|dlon| fraude={gg.adlon[gg.y == 1].mean():.3f} '
                    f'AUC -|dlon|={roc_auc_score(gg.y, -gg.adlon):.3f} AUC -dprev={roc_auc_score(gg.y[m2], -gg.dprev[m2]):.3f}')
    print('## 2f réplica por', grp); [print('    ', x) for x in rows]
print()
# ---------------------------------------------------------------- 3. modelo combinado fuera de muestra (GroupKFold por cliente)
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression
X = pd.DataFrame({'adlat': df.adlat, 'adlon': df.adlon, 'dprev': df.dprev.fillna(df.dprev.median()), 'dprev_na': df.dprev.isna().astype(int),
                  'dnext': df.dnext.fillna(df.dnext.median()), 'dnext_na': df.dnext.isna().astype(int),
                  'ar': (df.cc == 'Argentina').astype(int), 'co': (df.cc == 'Colombia').astype(int)}).values
oof = np.zeros(len(y))
for tr, te in GroupKFold(5).split(X, y, gid):
    mu, sd = X[tr].mean(0), X[tr].std(0)+1e-9
    mdl = LogisticRegression(max_iter=2000, class_weight='balanced').fit((X[tr]-mu)/sd, y[tr])
    oof[te] = mdl.predict_proba((X[te]-mu)/sd)[:, 1]
a, lo, hi = auc_ci(y, oof, gid)
print(f'## 3 logística con todas las features geo, AUC fuera de muestra (GroupKFold por cliente) = {a:.4f} [{lo:.4f}, {hi:.4f}]')
