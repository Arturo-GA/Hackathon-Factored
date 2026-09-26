import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("""
with a as (select customer_id, count(*) n_pr, sum((pstatus='Active')::int) n_act from pr group by 1),
k as (select customer_id, count(*) n_cp from cp group by 1),
s as (select customer_id, count(*) n_cs from cs group by 1),
c as (select customer_id, count(*) n_cc from cc group by 1)
select least(coalesce(a.n_act,0),6) nact, count(*) n, round(avg(coalesce(n_cp,0)),4) cp, round(avg(coalesce(n_cs,0)),3) cs, round(avg(coalesce(n_cc,0)),3) cc
from cu left join a using(customer_id) left join k using(customer_id) left join s using(customer_id) left join c using(customer_id)
group by 1 order by 1""").fetchdf().to_string())
