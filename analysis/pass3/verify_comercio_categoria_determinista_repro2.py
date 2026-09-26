# Verificacion independiente (reintento) del hallazgo "comercio_categoria_determinista".
# Todo se agrega en SQL; a pandas solo llegan tablas pequenas (<200 filas).
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency, chisquare

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)

def df(s):
    return con.execute(s).df()

def show(title, s):
    print('==', title)
    print(df(s).to_string(), '\n')

def cramers_v(ct):
    chi2 = chi2_contingency(ct)[0]
    n = ct.sum()
    return float(np.sqrt(chi2 / (n * (min(ct.shape) - 1))))

# ------------------------------------------------------------------
# A. Mapa comercio -> categoria (mcat).  Se mide conflicto con la moda.
# ------------------------------------------------------------------
show('A1. comercios: n categorias distintas, categoria modal, filas en conflicto', """
with c as (select merchant_name, mcat, count(*) n from tx
           where merchant_name is not null and mcat is not null group by 1,2),
r as (select *, row_number() over (partition by merchant_name order by n desc) rk,
             sum(n) over (partition by merchant_name) tot,
             count(*) over (partition by merchant_name) ncat from c)
select merchant_name, mcat as mcat_modal, ncat, tot n_con_mcat, tot - n n_conflicto
from r where rk = 1 order by mcat_modal, merchant_name""")

show('A2. resumen', """
with c as (select merchant_name, count(distinct mcat) k from tx where merchant_name is not null and mcat is not null group by 1)
select (select count(distinct merchant_name) from tx) n_comercios,
       (select count(distinct lower(trim(merchant_name))) from tx) n_comercios_normalizados,
       sum((k > 1)::int) comercios_con_mas_de_1_mcat,
       (select count(distinct mcat) from tx) n_mcat
from c""")

# Generalizacion temporal del mapa: construido con ts < 2025-01-01, evaluado en ts >= 2025-01-01
show('A3. mapa entrenado en 2023-06..2024-12, evaluado en 2025-01..2026-06', """
with m as (select merchant_name, mode(mcat) mc from tx
           where ts < timestamp '2025-01-01' and merchant_name is not null and mcat is not null group by 1)
select count(*) n_eval, sum((m.mc = t.mcat)::int) aciertos, sum((m.mc is null)::int) sin_mapa
from tx t left join m using(merchant_name)
where t.ts >= timestamp '2025-01-01' and t.merchant_name is not null and t.mcat is not null""")

# ------------------------------------------------------------------
# B. tcat vs mcat (todas las filas, no solo compras)
# ------------------------------------------------------------------
show('B1. tcat vs mcat cuando ambas existen, por ttype', """
select ttype, count(*) n_ambas, sum((tcat <> mcat)::int) n_distintas
from tx where tcat is not null and mcat is not null group by 1""")

show('B2. tcat vs categoria del mapa comercio (cuando mcat es nula pero hay comercio y tcat)', """
with m as (select merchant_name, mode(mcat) mc from tx where merchant_name is not null and mcat is not null group by 1)
select count(*) n, sum((m.mc <> t.tcat)::int) n_distintas
from tx t join m using(merchant_name) where t.mcat is null and t.tcat is not null""")

# ------------------------------------------------------------------
# C. Presencia por tipo de transaccion
# ------------------------------------------------------------------
show('C1. % no nulo por ttype', """
select ttype, count(*) n,
  round(100*avg((merchant_name is not null)::int), 3) pct_merchant,
  round(100*avg((mcat is not null)::int), 3) pct_mcat,
  round(100*avg((tcat is not null)::int), 3) pct_tcat,
  sum((merchant_name is not null)::int) n_merchant, sum((mcat is not null)::int) n_mcat, sum((tcat is not null)::int) n_tcat
from tx group by 1 order by n desc""")

# distribucion de tcat en Payment vs Purchase (para ver si tcat en Payment tiene semantica)
d = df("""select ttype, tcat, count(*) n from tx where ttype in ('Purchase','Payment') and tcat is not null group by 1,2""")
ct = d.pivot(index='tcat', columns='ttype', values='n').fillna(0)
print('== C2. distribucion de tcat en Purchase vs Payment (proporciones)')
print((ct / ct.sum()).round(4).to_string())
print('V de Cramer tcat x {Purchase,Payment} = %.4f  (n=%d)\n' % (cramers_v(ct.values), ct.values.sum()))

# ------------------------------------------------------------------
# D. Independencia de nulos en compras (merchant_name, mcat, tcat)
# ------------------------------------------------------------------
j = df("""select (merchant_name is null)::int a, (mcat is null)::int b, (tcat is null)::int c, count(*) n
          from tx where ttype='Purchase' group by 1,2,3""")
N = j.n.sum()
pa = j.loc[j.a == 1, 'n'].sum() / N; pb = j.loc[j.b == 1, 'n'].sum() / N; pc = j.loc[j.c == 1, 'n'].sum() / N
j['esperado'] = N * np.where(j.a == 1, pa, 1 - pa) * np.where(j.b == 1, pb, 1 - pb) * np.where(j.c == 1, pc, 1 - pc)
j['obs/esp'] = (j.n / j.esperado).round(3)
print('== D1. patron conjunto de nulos en compras (a=merchant nulo, b=mcat nulo, c=tcat nulo)')
print(j.sort_values(['a', 'b', 'c']).to_string())
print('N=%d  P(merchant nulo)=%.4f  P(mcat nulo)=%.4f  P(tcat nulo)=%.4f\n' % (N, pa, pb, pc))

def odds_ratio(x, y):
    t = j.groupby([x, y]).n.sum().unstack().values.astype(float)
    orr = t[1, 1] * t[0, 0] / (t[1, 0] * t[0, 1])
    se = np.sqrt((1 / t).sum())
    return orr, np.exp(np.log(orr) - 1.96 * se), np.exp(np.log(orr) + 1.96 * se)
for x, y, lab in [('a', 'b', 'merchant~mcat'), ('a', 'c', 'merchant~tcat'), ('b', 'c', 'mcat~tcat')]:
    o, lo, hi = odds_ratio(x, y)
    print('   OR nulos %-14s = %.3f  IC95 [%.3f, %.3f]' % (lab, o, lo, hi))
print()

# ------------------------------------------------------------------
# E. Imputacion de la categoria en compras (y pagos)
# ------------------------------------------------------------------
show('E1. imputacion paso a paso', """
with m as (select merchant_name, mode(mcat) mc from tx where merchant_name is not null and mcat is not null group by 1)
select t.ttype, count(*) n,
  round(100*avg((t.mcat is null)::int), 4) pct_mcat_nula,
  round(100*avg((coalesce(t.mcat, m.mc) is null)::int), 4) pct_tras_mapa,
  round(100*avg((coalesce(t.mcat, t.tcat) is null)::int), 4) pct_tras_tcat_sin_mapa,
  round(100*avg((coalesce(t.mcat, m.mc, t.tcat) is null)::int), 4) pct_tras_mapa_y_tcat,
  sum((coalesce(t.mcat, m.mc, t.tcat) is null)::int) n_sigue_nula,
  round(100*avg((t.merchant_name is null)::int), 4) pct_comercio_nulo,
  round(100*avg((t.merchant_name is not null and coalesce(t.mcat, m.mc, t.tcat) is not null)::int), 4) pct_comercio_y_categoria
from tx t left join m using(merchant_name) where t.ttype in ('Purchase','Payment') group by 1""")

# ------------------------------------------------------------------
# F. Pesos por categoria y uniformidad de comercios dentro de la categoria
# ------------------------------------------------------------------
show('F1. peso por categoria en compras (mcat observada / categoria imputada)', """
with m as (select merchant_name, mode(mcat) mc from tx where merchant_name is not null and mcat is not null group by 1),
t as (select t.mcat, coalesce(t.mcat, m.mc, t.tcat) cat from tx t left join m using(merchant_name) where t.ttype='Purchase')
select cat, count(*) n_imputada, round(100*count(*)/sum(count(*)) over (), 2) pct_imputada,
       count(mcat) n_mcat_obs, round(100*count(mcat)/sum(count(mcat)) over (), 2) pct_mcat_obs
from t where cat is not null group by 1 order by n_imputada desc""")

w = df("""select mcat, merchant_name, count(*) n from tx where merchant_name is not null and mcat is not null group by 1,2""")
print('== F2. uniformidad de comercios dentro de cada categoria')
for c, g in w.groupby('mcat'):
    s = chisquare(g.n.values)
    print('   %-14s k=%d  n=%7d  min=%6d max=%6d  max desvio vs media=%.2f%%  chi2 p=%.3g' % (
        c, len(g), g.n.sum(), g.n.min(), g.n.max(), 100 * np.max(np.abs(g.n / g.n.mean() - 1)), s.pvalue))
print()

# ------------------------------------------------------------------
# G. Canal x tipo de transaccion
# ------------------------------------------------------------------
g = df("select ttype, coalesce(channel,'(nulo)') channel, count(*) n from tx group by 1,2")
ct = g.pivot(index='ttype', columns='channel', values='n').fillna(0).astype(int)
print('== G1. conteos ttype x canal'); print(ct.to_string(), '\n')
sh = ct.div(ct.sum(1), axis=0)
print('== G2. proporcion de canal dentro de cada ttype'); print(sh.round(4).to_string(), '\n')
tot = ct.sum(0) / ct.values.sum()
print('   max |proporcion(ttype) - proporcion global| = %.4f' % float(np.abs(sh - tot).values.max()))
print('   V de Cramer ttype x canal = %.4f (N=%d)\n' % (cramers_v(ct.values), ct.values.sum()))
for tt, ch in [('Withdrawal', 'Web'), ('Withdrawal', 'App'), ('Withdrawal', 'POS'), ('Deposit', 'POS'), ('Purchase', 'ATM')]:
    print('   %s por %s: %d (%.2f%% del tipo)' % (tt, ch, ct.loc[tt, ch], 100 * sh.loc[tt, ch]))
