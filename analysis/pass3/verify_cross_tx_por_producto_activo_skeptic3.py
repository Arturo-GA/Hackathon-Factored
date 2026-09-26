# parte 3: la pequena correlacion cp/cs con n_pr viene de clientes sin productos?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("""
with a as (select customer_id, count(*) n_pr from pr group by 1),
 k as (select customer_id, count(*) n_cp from cp group by 1),
 s as (select customer_id, count(*) n_cs from cs group by 1),
 e as (select customer_id, count(*) n_de from de where customer_id is not null group by 1)
select least(coalesce(a.n_pr,0),6) npr, count(*) nc, round(avg(coalesce(k.n_cp,0)),3) cp, round(avg(coalesce(s.n_cs,0)),3) cs,
  round(avg(coalesce(e.n_de,0)),2) de, round(var_samp(coalesce(e.n_de,0))/avg(coalesce(e.n_de,0)),2) de_disp
from cu left join a using(customer_id) left join k using(customer_id) left join s using(customer_id) left join e using(customer_id)
group by 1 order by 1""").fetchdf().to_string())
