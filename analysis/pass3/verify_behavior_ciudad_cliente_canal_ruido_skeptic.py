"""Verificador escéptico: behavior_ciudad_cliente_canal_ruido.
Parte 1: esquema y cifras base (ciudad tx vs ciudad cliente, nulos)."""
import duckdb, sys
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: print(con.execute(s).df().to_string(), '\n', flush=True)
part = sys.argv[1] if len(sys.argv) > 1 else 'all'

if part in ('schema', 'all'):
    for t in ['tx', 'cu', 'br', 'pr']:
        cols = con.execute(f"DESCRIBE {t}").df()[['column_name', 'column_type']]
        print(t, ', '.join(f"{a}:{b}" for a, b in cols.values), '\n')

if part in ('city', 'all'):
    # Denominadores explícitos
    q("""SELECT count(*) n_tx,
      avg((t.city IS NULL)::INT) city_null,
      avg((t.country IS NULL)::INT) country_null,
      avg((t.city IS NULL AND t.country IS NULL)::INT) both_null,
      count(c.customer_id) n_joined
    FROM tx t LEFT JOIN cu c USING(customer_id)""")
    # tasas sobre city no nula
    q("""SELECT count(*) n_city_nn,
      avg((t.city=c.city)::INT) same_city_all,
      avg((t.country=c.country)::INT) same_country,
      count(*) FILTER (WHERE t.country=c.country) n_dom,
      avg(CASE WHEN t.country=c.country THEN (t.city=c.city)::INT END) same_city_dom,
      avg(CASE WHEN t.country<>c.country THEN (t.city=c.city)::INT END) same_city_foreign,
      count(*) FILTER (WHERE t.country<>c.country) n_foreign,
      count(*) FILTER (WHERE t.country IS NULL) n_country_null
    FROM tx t JOIN cu c USING(customer_id) WHERE t.city IS NOT NULL""")

if part in ('city2', 'all'):
    # ¿Qué son el 0.37% de domésticas con ciudad distinta?
    q("""SELECT t.country, t.city tx_city, c.city cu_city, count(*) n
    FROM tx t JOIN cu c USING(customer_id)
    WHERE t.city IS NOT NULL AND t.country=c.country AND t.city<>c.city
    GROUP BY ALL ORDER BY n DESC LIMIT 15""")
    q("""SELECT count(DISTINCT t.customer_id) n_cust_mismatch, count(*) n_tx_mismatch
    FROM tx t JOIN cu c USING(customer_id)
    WHERE t.city IS NOT NULL AND t.country=c.country AND t.city<>c.city""")
    # ¿los mismatches se concentran en pocos clientes? (cliente siempre mismatch vs tx sueltas)
    q("""WITH d AS (SELECT t.customer_id, avg((t.city<>c.city)::INT) r, count(*) n FROM tx t JOIN cu c USING(customer_id)
         WHERE t.city IS NOT NULL AND t.country=c.country GROUP BY 1)
    SELECT CASE WHEN r=0 THEN '0' WHEN r=1 THEN '1' WHEN r<0.1 THEN '<0.1' ELSE '0.1-1' END bucket, count(*) n_cust, sum(n) n_tx, sum(n*r) n_mis FROM d GROUP BY 1 ORDER BY 1""")
    # Ciudades de cliente vs ciudades en tx por país
    q("""SELECT country, count(DISTINCT city) n_city_cu FROM cu GROUP BY 1""")
    q("""SELECT country, count(DISTINCT city) n_city_tx, count(*) n FROM tx GROUP BY 1 ORDER BY n DESC""")
    q("""SELECT country_raw, country, count(*) n FROM tx GROUP BY ALL ORDER BY n DESC LIMIT 30""")

if part in ('foreign', 'all'):
    q("""SELECT c.country cu_country, t.country tx_country, count(*) n, avg((t.city IS NULL)::INT) city_null
    FROM tx t JOIN cu c USING(customer_id) GROUP BY ALL ORDER BY 1, n DESC""")
    # Para tx extranjeras: ¿la ciudad pertenece al país de la tx? (mapa ciudad->país desde las tx domésticas y cu)
    q("""WITH cm AS (SELECT DISTINCT city, country FROM cu UNION SELECT DISTINCT city, country FROM tx WHERE country IN ('USA','Spain','Brazil') AND city IS NOT NULL)
    SELECT c.country cu_country, t.country tx_country,
       count(*) n, avg((EXISTS (SELECT 1 FROM cm WHERE cm.city=t.city AND cm.country=t.country))::INT) city_in_tx_country,
       avg((EXISTS (SELECT 1 FROM cm WHERE cm.city=t.city AND cm.country=c.country))::INT) city_in_cu_country
    FROM tx t JOIN cu c USING(customer_id) WHERE t.city IS NOT NULL AND t.country<>c.country GROUP BY ALL ORDER BY 1,2""")
    q("""SELECT country, city, count(*) n FROM tx WHERE country IN ('USA','Spain','Brazil') GROUP BY ALL ORDER BY 1, n DESC""")
    # Nulidad de city: ¿depende de doméstica/extranjera, canal, ttype, status, fraude?
    q("""SELECT (t.country=c.country) domestic, count(*) n, avg((t.city IS NULL)::INT) city_null FROM tx t JOIN cu c USING(customer_id) GROUP BY 1""")
    q("""SELECT status, count(*) n, avg((city IS NULL)::INT) city_null FROM tx GROUP BY 1 ORDER BY 1""")
    q("""SELECT fraud, count(*) n, avg((city IS NULL)::INT) city_null FROM tx GROUP BY 1 ORDER BY 1""")
    q("""SELECT channel, count(*) n, avg((city IS NULL)::INT) city_null, avg((lat IS NULL)::INT) latnull FROM tx GROUP BY 1 ORDER BY 1""")

if part in ('latlon', 'all'):
    CL = """CASE WHEN abs(lat+34.6037)<=1.01 AND abs(lon+58.3816)<=1.01 THEN 'BuenosAires'
                 WHEN abs(lat-4.711)<=1.01 AND abs(lon+74.0721)<=1.01 THEN 'Bogota'
                 WHEN abs(lat)<=1.01 AND abs(lon)<=1.01 THEN 'Cero' ELSE 'Otro' END"""
    q(f"""SELECT avg((lat IS NULL)::INT) lat_null, avg((lon IS NULL)::INT) lon_null, avg(((lat IS NULL)<>(lon IS NULL))::INT) only_one_null FROM tx""")
    # centro por país de la tx vs país del cliente
    q(f"""SELECT c.country cu_country, t.country tx_country, {CL} centro, count(*) n
    FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL
    GROUP BY ALL ORDER BY 1,2, n DESC""")

if part in ('latlon2', 'all'):
    q("""SELECT (lat IS NULL) latn, (lon IS NULL) lonn, count(*) n FROM tx GROUP BY ALL ORDER BY ALL""")
    # con ambas presentes: ¿100% en el centro del país del cliente?
    q("""SELECT c.country cu_country, count(*) n,
       avg((abs(t.lat - CASE c.country WHEN 'Argentina' THEN -34.6037 WHEN 'Colombia' THEN 4.711 ELSE 0 END)<=1.0001
        AND abs(t.lon - CASE c.country WHEN 'Argentina' THEN -58.3816 WHEN 'Colombia' THEN -74.0721 ELSE 0 END)<=1.0001)::INT) in_cu_center,
       avg((abs(t.lat - CASE t.country WHEN 'Argentina' THEN -34.6037 WHEN 'Colombia' THEN 4.711 WHEN 'México' THEN 0 ELSE 999 END)<=1.0001
        AND abs(t.lon - CASE t.country WHEN 'Argentina' THEN -58.3816 WHEN 'Colombia' THEN -74.0721 WHEN 'México' THEN 0 ELSE 999 END)<=1.0001)::INT) in_tx_center,
       avg(t.lat) mlat, avg(t.lon) mlon, stddev(t.lat) sdlat
    FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL GROUP BY 1""")
    # Promedios por país de la TX (como en el hallazgo) -> para ver de dónde salen (4.69,-74.05) etc.
    q("""SELECT country tx_country, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon FROM tx WHERE lat IS NOT NULL AND lon IS NOT NULL GROUP BY 1 ORDER BY n DESC""")
    # ¿La ciudad (del cliente) mueve las coordenadas dentro de un país? medias por ciudad del cliente
    q("""SELECT c.country, c.city, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon, round(stddev(t.lat),3) sdlat
    FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL GROUP BY ALL ORDER BY 1,2""")
    # ¿coordenadas fijas por cliente? (desviación dentro de cliente vs global)
    q("""WITH k AS (SELECT customer_id, count(*) n, stddev(lat) s FROM tx WHERE lat IS NOT NULL AND lon IS NOT NULL GROUP BY 1 HAVING count(*)>=5)
    SELECT count(*) n_cust, avg(s) mean_within_sd FROM k""")
