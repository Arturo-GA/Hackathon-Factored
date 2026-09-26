# H15: conteos por cliente entre tablas (tx, cc, cp, de, cs, sv, pr): hay un factor latente de actividad?
import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df = con.execute("""
 select c.customer_id, c.segment, c.cstatus, c.country, c.registration_date,
  coalesce(t.n,0) n_tx, coalesce(t.nfr,0) n_fraud, coalesce(t.ndec,0) n_decl, coalesce(t.napp,0) n_appweb,
  coalesce(k.n,0) n_cc, coalesce(k.nt,0) n_cc_tx, coalesce(p.n,0) n_cp, coalesce(d.n,0) n_de, coalesce(s.n,0) n_cs, coalesce(r.n,0) n_pr, coalesce(r.nact,0) n_pr_act
 from cu c
 left join (select customer_id, count(*) n, sum(fraud::int) nfr, sum((status='Declined')::int) ndec, sum((channel in ('App','Web'))::int) napp from tx group by 1) t using(customer_id)
 left join (select customer_id, count(*) n, sum((cat='Transaccional')::int) nt from cc group by 1) k using(customer_id)
 left join (select customer_id, count(*) n from cp group by 1) p using(customer_id)
 left join (select customer_id, count(*) n from de where customer_id is not null group by 1) d using(customer_id)
 left join (select customer_id, count(*) n from cs group by 1) s using(customer_id)
 left join (select customer_id, count(*) n, sum((pstatus='Active')::int) nact from pr group by 1) r using(customer_id)
""").fetchdf()
cols = ['n_tx','n_fraud','n_decl','n_appweb','n_cc','n_cc_tx','n_cp','n_de','n_cs','n_pr','n_pr_act']
print(df[cols].describe().T[['mean','std','50%','max']].round(2))
for c in cols: print(c, 'var/mean', round(df[c].var()/df[c].mean(),2))
print(df[cols].corr(method='spearman').round(3))
# partial: n_tx vs n_cc controlando n_pr_act
import scipy.stats as st
g = df.groupby('n_pr_act').agg(n=('n_tx','size'), tx=('n_tx','mean'), cc=('n_cc','mean'), cp=('n_cp','mean'), de=('n_de','mean'), cs=('n_cs','mean'))
print(g.round(2))
g2 = df.groupby('segment')[cols].mean().round(2); print(g2)
g3 = df.groupby('cstatus')[cols].mean().round(2); print(g3)
