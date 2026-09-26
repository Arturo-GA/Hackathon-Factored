"""Verificador escéptico (reintento), checks complementarios de behavior_ciudad_cliente_canal_ruido:
imputación simulada (regla normalizada vs exacta), nulidad parcial lat/lon, esperado aleatorio de branch = sucursal de apertura,
tx.country_raw 'Mexico' (sin tilde) por país del cliente y conjunto de ciudades extranjeras."""
import duckdb, pandas as pd
pd.set_option("display.width", 240); pd.set_option("display.max_columns", 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def show(title, sql):
    print(f"\n### {title}", flush=True)
    print(con.execute(sql).df().to_string(), flush=True)

show("Imputación simulada sobre city NO nula: precisión y cobertura según regla", """
SELECT 'norm: country=cu.country' regla, count(*) FILTER (WHERE t.country=c.country) n_cubre,
  count(*) FILTER (WHERE t.country=c.country)*1.0/count(*) cobertura,
  avg((t.city=c.city)::INT) FILTER (WHERE t.country=c.country) precision_imp,
  count(*) FILTER (WHERE t.country=c.country AND t.city<>c.city) n_errores
FROM tx t JOIN cu c USING(customer_id) WHERE t.city IS NOT NULL
UNION ALL
SELECT 'exacta: country_raw=cu.country', count(*) FILTER (WHERE t.country_raw=c.country),
  count(*) FILTER (WHERE t.country_raw=c.country)*1.0/count(*),
  avg((t.city=c.city)::INT) FILTER (WHERE t.country_raw=c.country),
  count(*) FILTER (WHERE t.country_raw=c.country AND t.city<>c.city)
FROM tx t JOIN cu c USING(customer_id) WHERE t.city IS NOT NULL""")

show("country_raw='Mexico' (sin tilde) por país del cliente; ciudades usadas", """
SELECT c.country cu_country, count(*) n, count(DISTINCT t.city) n_ciudades, string_agg(DISTINCT t.city, ', ') ciudades
FROM tx t JOIN cu c USING(customer_id) WHERE t.country_raw='Mexico' GROUP BY 1 ORDER BY 1""")
show("Conjunto de ciudades por country_raw en tx extranjeras (country_raw<>cu.country)", """
SELECT t.country_raw, count(DISTINCT t.city) n_ciudades, string_agg(DISTINCT t.city, ', ') ciudades, count(*) n
FROM tx t JOIN cu c USING(customer_id) WHERE t.country_raw<>c.country GROUP BY 1 ORDER BY 1""")

show("Nulidad parcial de lat/lon en canales físicos (POS/ATM/Branch)", """
SELECT count(*) n,
  avg((lat IS NOT NULL AND lon IS NOT NULL)::INT) p_ambas, avg((lat IS NOT NULL AND lon IS NULL)::INT) p_solo_lat,
  avg((lat IS NULL AND lon IS NOT NULL)::INT) p_solo_lon, avg((lat IS NULL AND lon IS NULL)::INT) p_ninguna
FROM tx WHERE channel IN ('POS','ATM','Branch')""")

show("Sucursal de apertura del producto: ¿en el país del cliente? y esperado aleatorio de tx.branch_id = opening_branch_id", """
WITH nb AS (SELECT country, count(*) n_br FROM br GROUP BY 1)
SELECT count(*) n, avg((ob.country=c.country)::INT) p_opening_en_pais_cliente,
  avg((t.branch_id=p.opening_branch_id)::INT) observado,
  avg(CASE WHEN ob.country=c.country THEN 1.0/nb.n_br ELSE 0 END) esperado_azar
FROM tx t JOIN pr p USING(product_id) JOIN cu c ON c.customer_id=t.customer_id JOIN br ob ON ob.branch_id=p.opening_branch_id
JOIN nb ON nb.country=c.country WHERE t.branch_id IS NOT NULL""")

show("Coordenadas de br: ¿también en (0,0)? (sucursales con |lat|<=1.1 y |lon|<=1.1)", """
SELECT country, count(*) n_br, sum((abs(lat)<=1.1 AND abs(lon)<=1.1)::INT) n_null_island, round(median(lat),2) med_lat, round(median(lon),2) med_lon
FROM br GROUP BY 1 ORDER BY 1""")
