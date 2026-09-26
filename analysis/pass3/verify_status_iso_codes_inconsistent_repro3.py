"""Verificacion independiente (intento 3): status_iso_codes_inconsistent.
Parte 1: universo de valores, cobertura del join y reparto codigo x status."""
import duckdb, pandas as pd, warnings
warnings.filterwarnings('ignore')
pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== ptype en pr ==")
print(q("select ptype, count(*) n, sum(case when expires is null then 1 else 0 end) exp_null, "
        "sum(case when credit_limit is null then 1 else 0 end) cl_null, "
        "sum(case when bal is null then 1 else 0 end) bal_null from pr group by 1 order by 2 desc").to_string())

print("== cobertura del join tx->pr ==")
print(q("""select count(*) n_tx, count(p.product_id) n_join,
  sum(case when t.product_id is null then 1 else 0 end) tx_pid_null
  from tx t left join pr p on t.product_id = p.product_id""").to_string())

print("== status x code (todas las tx) ==")
d = q("select status, coalesce(code,'NA') code, count(*) n from tx group by 1,2")
print(d.pivot(index='status', columns='code', values='n').fillna(0).astype(int).to_string())

print("== ttype x status ==")
d = q("select ttype, status, count(*) n from tx group by 1,2")
print(d.pivot(index='ttype', columns='status', values='n').fillna(0).astype(int).to_string())

print("== ptype x ttype (todas las tx) ==")
d = q("select p.ptype, t.ttype, count(*) n from tx t join pr p on t.product_id=p.product_id group by 1,2")
print(d.pivot(index='ptype', columns='ttype', values='n').fillna(0).astype(int).to_string())

print("== ptype x channel (todas las tx) ==")
d = q("select p.ptype, t.channel, count(*) n from tx t join pr p on t.product_id=p.product_id group by 1,2")
print(d.pivot(index='ptype', columns='channel', values='n').fillna(0).astype(int).to_string())
