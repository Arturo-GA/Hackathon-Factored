"""Vigencia: tx vs fecha de apertura/vencimiento del producto por cohorte; codigo 54 vs vencido; 51 vs saldo."""
import duckdb, pandas as pd, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250)
print(q("""select year(p.opened) y_open, count(*) n, avg(case when t.ts<p.opened then 1 else 0 end) tx_antes_apertura,
  min(p.opened) mn, max(p.opened) mx from tx t join pr p using(product_id) group by 1 order by 1""").to_string())
print(q("""select coalesce(t.code,'NA') code, t.status='Approved' aprob, count(*) n, avg(case when t.ts>p.expires then 1 else 0 end) vencido,
 avg(case when t.amount>p.bal then 1 else 0 end) monto_gt_saldo, avg(case when t.ts<p.opened then 1 else 0 end) antes_apertura
 from tx t join pr p using(product_id) group by 1,2 order by 2,1""").round(4).to_string())
# rango temporal de tx por cliente vs registro
print(q("""select min(ts), max(ts) from tx""").to_string())
