# H16: numero de tx por producto activo y su distribucion temporal (relacion con opened/expires)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table a as select product_id, count(*) n, min(ts) f, max(ts) l,
   count(distinct ttype) nt, count(distinct channel) nch from tx group by 1""")
print(q("select min(n), quantile_cont(n,[0.01,0.1,0.5,0.9,0.99]) q, max(n), avg(n), var_samp(n)/avg(n) disp from a"))
print(q("select n, count(*) c from a group by 1 order by 1 limit 40"))
print(q("""select p.ptype, count(*) np, round(avg(a.n),2) mean_n, round(var_samp(a.n)/avg(a.n),2) disp from pr p join a using(product_id) group by 1"""))
# tiempo: tx por producto uniformes en ventana global? fraccion de tx en cada anio
print(q("select year(ts) y, count(*) from tx group by 1 order by 1"))
# posicion relativa de tx dentro de [opened, expires]
print(q("""select round(avg((t.ts < p.opened)::int),3) before_open, round(avg((t.ts > p.expires)::int),3) after_exp,
   round(avg((p.opened > date '2023-06-17')::int),3) opened_in_window, count(*) n
   from (select * from tx using sample 200000) t join pr p using(product_id)"""))
print(q("""select case when p.opened > date '2026-06-17' then 'opened_future' when p.opened > date '2023-06-17' then 'opened_in_window' else 'opened_before' end g,
   count(*) n, round(avg((t.ts < p.opened)::int),3) before_open from (select * from tx using sample 200000) t join pr p using(product_id) group by 1"""))
print(q("select min(opened), max(opened), min(expires), max(expires) from pr"))
