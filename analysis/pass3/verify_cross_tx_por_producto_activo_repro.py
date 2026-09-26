# Verificacion independiente: cross_tx_por_producto_activo
import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
P = lambda s: print(q(s).to_string(), flush=True)

# 1) Tx por producto, incluyendo productos con 0 tx
con.execute("""create temp table tp as
  select p.product_id, p.customer_id, p.ptype, p.pstatus, p.opened, p.expires,
         coalesce(t.n,0) n, t.cust_mismatch
  from pr p left join (select product_id, count(*) n, max(customer_id) cm, count(distinct customer_id) cust_mismatch
                        from tx group by 1) t using(product_id)""")
print("== tx por pstatus ==")
P("""select pstatus, count(*) nprod, sum(n) ntx, round(avg(n),3) mean, round(var_samp(n)/avg(n),3) disp,
      min(n) mn, median(n) med, max(n) mx, sum((n=0)::int) zeros from tp group by 1 order by 1""")
print("== tx huerfanas / mismatch de cliente ==")
P("""select count(*) ntx, sum((p.product_id is null)::int) orphan, sum((p.customer_id<>t.customer_id)::int) cust_diff
     from tx t left join pr p using(product_id)""")
print("== Active por ptype ==")
P("""select ptype, count(*) nprod, round(avg(n),3) mean, round(var_samp(n)/avg(n),3) disp, min(n) mn, max(n) mx
     from tp where pstatus='Active' group by 1 order by 1""")
# chequeo Poisson: fraccion observada vs esperada en colas
d = q("select n from tp where pstatus='Active'")['n'].values
lam = d.mean()
print(f"Active: N={len(d)} mean={lam:.4f} var/mean={d.var(ddof=1)/lam:.4f} P(n=0) obs={np.mean(d==0):.2e} exp={stats.poisson.pmf(0,lam):.2e} "
      f"expected zeros={len(d)*stats.poisson.pmf(0,lam):.2f}")
vals, cnts = np.unique(d, return_counts=True)
exp = len(d)*stats.poisson.pmf(vals, lam)
m = exp >= 5
print("chi2 GOF (bins exp>=5):", stats.chisquare(cnts[m], exp[m]*cnts[m].sum()/exp[m].sum()))
# depende de opened? (vida del producto en la ventana)
print("== Active: tx por anio de apertura ==")
P("""select case when opened < date '2023-06-17' then 'antes_ventana' else cast(year(opened) as varchar) end g,
     count(*) nprod, round(avg(n),3) mean from tp where pstatus='Active' group by 1 order by 1""")
print("== Active: tx por expira antes/despues de fin de ventana ==")
P("""select (expires < date '2026-06-17') exp_antes_fin, (expires < date '2023-06-17') exp_antes_ini, count(*) nprod, round(avg(n),3) mean
     from tp where pstatus='Active' group by 1,2 order by 1,2""")

# 2) Nivel cliente
con.execute("""create temp table c as
 select cu.customer_id, cu.segment, cu.cstatus, cu.income, cu.credit_score,
   coalesce(a.n_act,0) n_act, coalesce(a.n_pr,0) n_pr, coalesce(t.n_tx,0) n_tx,
   coalesce(k.n_cc,0) n_cc, coalesce(cp.n_cp,0) n_cp, coalesce(s.n_cs,0) n_cs, coalesce(e.n_de,0) n_de
 from cu
 left join (select customer_id, sum((pstatus='Active')::int) n_act, count(*) n_pr from pr group by 1) a using(customer_id)
 left join (select customer_id, count(*) n_tx from tx group by 1) t using(customer_id)
 left join (select customer_id, count(*) n_cc from cc group by 1) k using(customer_id)
 left join (select customer_id, count(*) n_cp from cp group by 1) cp using(customer_id)
 left join (select customer_id, count(*) n_cs from cs group by 1) s using(customer_id)
 left join (select customer_id, count(*) n_de from de where customer_id is not null group by 1) e using(customer_id)""")
df = q("select * from c")
print("clientes:", len(df))
y = df.n_tx.values.astype(float); x = df.n_act.values.astype(float)
b = (x*y).sum()/(x*x).sum()
r2_origin = 1 - ((y-b*x)**2).sum()/((y-y.mean())**2).sum()
r = np.corrcoef(x, y)[0,1]
print(f"n_tx ~ b*n_act sin intercepto: b={b:.4f} R2={r2_origin:.4f}; R2 OLS con intercepto={r**2:.4f}")
# R2 esperado si Poisson(13*n_act) puro
print(f"R2 maximo teorico si Poisson: 1 - mean(lam*n_act)/var(y) = {1 - (b*x).mean()/y.var():.4f}")
sin = df[df.n_act==0]; con_ = df[df.n_act>0]
print(f"sin activos: {len(sin)} ({len(sin)/len(df):.4f}); con tx>0: {(sin.n_tx>0).sum()}; cc medio {sin.n_cc.mean():.3f} vs con activos {con_.n_cc.mean():.3f}")
print(f"clientes con 0 productos: {(df.n_pr==0).sum()}")
for col in ['n_cc','n_cp','n_cs','n_de','n_pr','n_act','n_tx']:
    v = df[col]
    print(f"{col}: mean={v.mean():.3f} var/mean={v.var()/v.mean():.3f} spearman_vs_ntx={stats.spearmanr(v, df.n_tx).correlation:.4f} "
          f"spearman_vs_nact={stats.spearmanr(v, df.n_act).correlation:.4f}")
r_cc = np.corrcoef(df.n_cc, df.n_tx)[0,1]
print(f"R2 n_cc~n_tx = {r_cc**2:.6f}")
# residuo de n_tx tras n_act vs otras variables
df['res'] = df.n_tx - b*df.n_act
for col in ['income','credit_score','n_cc','n_cp','n_cs','n_de']:
    s = df[[col,'res']].dropna()
    print(f"residuo n_tx vs {col}: spearman={stats.spearmanr(s[col], s.res).correlation:.4f}")
print(df.groupby('segment').agg(n=('n_tx','size'), ntx=('n_tx','mean'), nact=('n_act','mean'), tx_per_act=('n_tx', 'sum')).assign(tx_per_act=lambda g: g.tx_per_act/ (df.groupby('segment').n_act.sum())).round(3).to_string())
print(df.groupby('cstatus').agg(n=('n_tx','size'), ntx=('n_tx','mean'), nact=('n_act','mean'), ncc=('n_cc','mean')).round(3).to_string())
