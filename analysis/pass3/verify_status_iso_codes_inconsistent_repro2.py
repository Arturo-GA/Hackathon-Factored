import duckdb, pandas as pd, numpy as np
from scipy.stats import chi2_contingency
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
def cramer(df, r, c):
    ct = df.pivot_table(index=r, columns=c, values='n', aggfunc='sum').fillna(0)
    chi2 = chi2_contingency(ct.values, correction=False)[0]; n = ct.values.sum()
    return np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
for col in ['ttype','channel']:
    d = q(f"select {col}, coalesce(code,'NA') code, count(*) n from tx where status<>'Approved' group by 1,2")
    print(f"V(code incl NA x {col}) =", round(cramer(d, col, 'code'), 4))
print(q("""select sum(case when p.bal is null then 1 else 0 end) bal_null, count(*) n from pr p""").to_string())
print(q("""select coalesce(t.code,'NA') code, t.status='Approved' aprob, avg(case when t.amount>p.bal then 1 else 0 end) m
 from tx t join pr p using(product_id) group by 1,2 order by 2,1""").round(4).to_string())
# subconjunto estricto: 14/54 en prestamos/inversion/seguro (sin tarjeta posible)
print(q("""select p.ptype, t.code, count(*) n from tx t join pr p using(product_id)
 where t.status<>'Approved' and t.code in ('14','54') and p.ptype not like 'Tarjeta%' group by 1,2 order by 1,2""").pivot(index='ptype',columns='code',values='n').to_string())
print(q("""select count(*) n from tx t join pr p using(product_id)
 where t.status<>'Approved' and t.code in ('14','54') and p.ptype in ('Préstamo Personal','Préstamo Hipotecario','Inversión','Seguro')""").to_string())
# canal de las 14/54 en cuentas
print(q("""select t.channel, count(*) n from tx t join pr p using(product_id)
 where t.status<>'Approved' and t.code in ('14','54') and p.ptype like 'Cuenta%' group by 1 order by 2 desc""").to_string())
