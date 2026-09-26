# Verificador esceptico parte 2: nivel cliente e independencia
import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
print(q("select count(*) activos_con_0tx from pr p where pstatus='Active' and not exists (select 1 from tx t where t.product_id=p.product_id)").to_string())
con.execute("""create temp table c as
 select cu.customer_id, cu.segment, cu.cstatus, cu.income, cu.credit_score,
   coalesce(a.n_act,0) n_act, coalesce(a.n_pr,0) n_pr, coalesce(t.n_tx,0) n_tx, coalesce(t.n_dec,0) n_dec, coalesce(t.n_fr,0) n_fr,
   coalesce(k.n_cc,0) n_cc, coalesce(k.n_tr,0) n_trx, coalesce(cp.n_cp,0) n_cp, coalesce(s.n_cs,0) n_cs, coalesce(sv.n_sv,0) n_sv
 from cu
 left join (select customer_id, sum((pstatus='Active')::int) n_act, count(*) n_pr from pr group by 1) a using(customer_id)
 left join (select customer_id, count(*) n_tx, sum((status='Declined')::int) n_dec, sum(fraud::int) n_fr from tx group by 1) t using(customer_id)
 left join (select customer_id, count(*) n_cc, sum((cat='Transaccional')::int) n_tr from cc group by 1) k using(customer_id)
 left join (select customer_id, count(*) n_cp from cp group by 1) cp using(customer_id)
 left join (select customer_id, count(*) n_cs from cs group by 1) s using(customer_id)
 left join (select customer_id, count(*) n_sv from sv group by 1) sv using(customer_id)""")
df = q("select * from c")
print("clientes", len(df))
y=df.n_tx.values.astype(float); x=df.n_act.values.astype(float)
b=(x*y).sum()/(x*x).sum(); r2=1-((y-b*x)**2).sum()/((y-y.mean())**2).sum()
print(f"b={b:.4f} R2_origen={r2:.4f}  R2_max_teorico_Poisson={1-(b*x).mean()/y.var():.4f}")
res = y-b*x
print(f"residuo var/(b*x) medio: {(res**2).sum()/(b*x).sum():.4f}  (1 => Poisson puro)")
z = df[df.n_act==0]
print(f"sin activos: {len(z)} ({len(z)/len(df):.4f}); con tx: {(z.n_tx>0).sum()}; n_pr==0: {(df.n_pr==0).sum()}")
lam_act = x.mean()
print(f"n_act media {lam_act:.3f} var/mean {x.var()/lam_act:.3f}; P(0) Poisson esperado {np.exp(-lam_act):.4f}")
print(f"cc medio sin activos {z.n_cc.mean():.3f} vs con activos {df[df.n_act>0].n_cc.mean():.3f}")
# bootstrap IC de spearman / correlacion
rng=np.random.default_rng(0)
def ci(a,bb,B=200):
    n=len(a); vals=[]
    for _ in range(B):
        i=rng.integers(0,n,n); vals.append(stats.spearmanr(a[i],bb[i]).correlation)
    return np.percentile(vals,[2.5,97.5])
for col in ['n_cc','n_trx','n_cp','n_cs','n_sv']:
    v=df[col].values
    r=stats.spearmanr(v,y).correlation; r2c=np.corrcoef(v,y)[0,1]**2
    lo,hi=ci(v,y,100)
    print(f"{col}: media {v.mean():.3f} var/mean {v.var()/v.mean():.3f} spearman_vs_ntx {r:.4f} IC95[{lo:.4f},{hi:.4f}] R2 {r2c:.6f} spearman_vs_npr {stats.spearmanr(v,df.n_pr).correlation:.4f}")
# rechazos/fraude del cliente vs contactos (solo clientes con tx)
w=df[df.n_tx>0]
for col in ['n_dec','n_fr']:
    for tgt in ['n_cc','n_trx','n_cp']:
        print(f"{col} vs {tgt}: spearman {stats.spearmanr(w[col],w[tgt]).correlation:.4f}")
# tasa de contacto: clientes con >=1 fraude vs sin
g=w.assign(f=w.n_fr>0).groupby('f')[['n_cc','n_trx','n_cp']].mean(); print(g.round(3).to_string())
print(df.groupby('segment')[['n_tx','n_act']].mean().assign(tx_per_act=lambda g:g.n_tx/g.n_act).round(3).to_string())
print(df.groupby('cstatus')[['n_tx','n_act','n_cc']].mean().round(3).to_string())
