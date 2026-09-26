"""Complemento: coordenadas de tx en ATM/Branch vs coordenadas de la sucursal (contexto para la explotacion 'ubicacion')."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("""select t.channel, count(*) n,
  avg((abs(t.lat-b.lat)<0.01 and abs(t.lon-b.lon)<0.01)::int) pct_mismo_punto,
  median(sqrt(power(t.lat-b.lat,2)+power(t.lon-b.lon,2))) med_dist_grados,
  avg((t.country=b.country)::int) mismo_pais, avg((t.city=b.city)::int) misma_ciudad
 from tx t join br b on t.branch_id=b.branch_id where t.lat is not null and t.lon is not null group by 1 order by 1""").fetchdf().round(4).to_string())
# esperado de misma_ciudad si la sucursal fuera aleatoria dentro del pais: suma de p(ciudad)^2 por pais aprox
print(con.execute("""with tb as (select t.country, t.city tc, b.city bc from tx t join br b on t.branch_id=b.branch_id where t.country=b.country)
 select count(*) n, avg((tc=bc)::int) obs from tb""").fetchdf().round(4).to_string())
