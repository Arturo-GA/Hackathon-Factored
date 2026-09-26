# H7: lat/lon de tx vs ciudad/pais: centroides y bug de coordenadas
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("create temp table s as select * from tx where lat is not null using sample 300000")
print(q("""select country, round(lat) rl, round(lon) rlo, count(*) n from s group by 1,2,3 having count(*)>1500 order by 1,4 desc"""))
print(q("select br.country, round(avg(lat),2), round(avg(lon),2), round(stddev(lat),2), round(stddev(lon),2), min(lat),max(lat), min(lon), max(lon) from br group by 1"))
print(q("select city, country, round(avg(lat),2) la, round(avg(lon),2) lo, round(stddev(lat),3) sla, count(*) from br group by 1,2 order by 2,1"))
