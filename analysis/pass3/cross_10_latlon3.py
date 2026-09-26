# H7c: coordenadas de tx = uno de 3 centros (0,0 / Bogota / Buenos Aires) + ruido uniforme +-1 grado
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table s as select t.*, c.city ccity, c.country ccountry,
  case when abs(lat)<=1.001 and abs(lon)<=1.001 then 'cero(0,0)'
       when abs(lat-4.711)<=1.01 and abs(lon+74.072)<=1.01 then 'Bogota'
       when abs(lat+34.604)<=1.01 and abs(lon+58.382)<=1.01 then 'BuenosAires' else 'otro' end centro
  from (select * from tx where lat is not null) t join cu c using(customer_id)""")
print(q("select centro, count(*) n, round(100.0*count(*)/sum(count(*)) over(),2) pct from s group by 1 order by 2 desc"))
print(q("""select ccountry, ccity, centro, count(*) n from s group by 1,2,3 qualify row_number() over (partition by ccountry, ccity order by count(*) desc)<=2 order by 1,2,4 desc"""))
# consistency centro determined by customer city?
print(q("""with m as (select ccity, centro, count(*) n, sum(count(*)) over (partition by ccity) tot from s group by 1,2)
  select sum(n) filter (where rk=1)*1.0/sum(n) consist from (select *, row_number() over(partition by ccity order by n desc) rk from m)"""))
print(q("""with m as (select city, centro, count(*) n from s group by 1,2)
  select sum(n) filter (where rk=1)*1.0/sum(n) consist_txcity from (select *, row_number() over(partition by city order by n desc) rk from m)"""))
