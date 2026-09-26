# ids_16: imputación de la sucursal de registro rota: usar pr.opening_branch_id del primer producto (mismo país 100%). ¿misma ciudad/estado? cobertura?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select count(*) n, avg((b.city=c.city)::int) same_city, avg((b.state=c.state)::int) same_state,
   avg((p.opened >= c.registration_date::date)::int) opened_after_reg, avg((b.opened <= p.opened)::int) branch_open_before_product
   from pr p join br b on b.branch_id=p.opening_branch_id join cu c using(customer_id)"""))
# expectativa si la sucursal fuese uniforme dentro del país
print(q("""with b0 as (select replace(country,'Mexico','México') ctry, city, count(*) k from br group by 1,2),
   bc as (select ctry, city, k*1.0/sum(k) over (partition by ctry) s from b0),
   c0 as (select replace(country,'Mexico','México') ctry, city, count(*) n from cu group by 1,2)
   select sum(bc.s*c0.n)/150000 exp_same_city_uniform_in_country from bc join c0 using(ctry, city)"""))
# cuantas sucursales distintas por cliente
print(q("""select avg(nb) avg_branches, avg((nb=1)::int) single_branch from (select customer_id, count(distinct opening_branch_id) nb, count(*) np from pr group by 1 having count(*)>1)"""))
print(q("""select opening_channel, count(*) n from pr group by 1 order by 2 desc"""))
