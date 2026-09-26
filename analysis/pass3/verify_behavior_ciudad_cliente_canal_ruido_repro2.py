"""Verificación independiente (reintento) de behavior_ciudad_cliente_canal_ruido.
Uso: python verify_behavior_ciudad_cliente_canal_ruido_repro2.py <parte>
  schema | city | citymis | impute | channel | branch | latlon | nulls
Todas las agregaciones en SQL (DuckDB read-only)."""
import sys
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def show(title, sql):
    print(f"\n### {title}", flush=True)
    print(con.execute(sql).df().to_string(), flush=True)

part = sys.argv[1] if len(sys.argv) > 1 else 'schema'

if part == 'schema':
    for t in ['tx', 'cu', 'br']:
        d = con.execute(f"DESCRIBE {t}").df()
        print(t, ', '.join(f"{a}:{b}" for a, b in d[['column_name', 'column_type']].values))
    show("cu: países y nulos", "SELECT country, count(*) n, count(city) city_nn, count(DISTINCT city) ncity FROM cu GROUP BY 1 ORDER BY 2 DESC")
    show("tx: country_raw -> country", "SELECT country_raw, country, count(*) n FROM tx GROUP BY 1,2 ORDER BY 3 DESC")
    show("br: países", "SELECT country, count(*) n, count(DISTINCT city) ncity FROM br GROUP BY 1 ORDER BY 2 DESC")

if part == 'city':
    # Tabla base agregada: país cliente x country_raw x (city nula) x (city = ciudad cliente)
    show("cruce país del cliente x country_raw de la tx (n, % city nula, % city=cu.city entre city no nula)", """
      SELECT c.country cu_country, t.country_raw, count(*) n,
             round(100*avg((t.city IS NULL)::INT),2) pct_city_null,
             round(100*avg(CASE WHEN t.city IS NOT NULL THEN (t.city=c.city)::INT END),3) pct_same_city_nn
      FROM tx t JOIN cu c USING(customer_id) GROUP BY 1,2 ORDER BY 1,3 DESC""")
    show("totales: denominadores y tasas", """
      SELECT count(*) n_tx,
        count(*) FILTER (WHERE c.customer_id IS NULL) n_sin_cliente,
        round(100*avg((t.city IS NULL)::INT),3) pct_city_null,
        round(100*avg((t.country=c.country)::INT),3) pct_domestic_norm,
        round(100*avg((t.country_raw=c.country)::INT),3) pct_domestic_raw,
        count(*) FILTER (WHERE t.city IS NOT NULL) n_city_nn,
        round(100*avg(CASE WHEN t.city IS NOT NULL THEN (t.city=c.city)::INT END),3) pct_same_city_all_nn,
        round(100*avg(CASE WHEN t.city IS NULL THEN 0 ELSE (t.city=c.city)::INT END),3) pct_same_city_all_incl_null,
        count(*) FILTER (WHERE t.city IS NOT NULL AND t.country=c.country) n_dom_nn,
        round(100*avg(CASE WHEN t.city IS NOT NULL AND t.country=c.country THEN (t.city=c.city)::INT END),3) pct_same_city_dom_norm,
        count(*) FILTER (WHERE t.city IS NOT NULL AND t.country_raw=c.country) n_domraw_nn,
        round(100*avg(CASE WHEN t.city IS NOT NULL AND t.country_raw=c.country THEN (t.city=c.city)::INT END),4) pct_same_city_dom_raw,
        count(*) FILTER (WHERE t.city IS NOT NULL AND t.country_raw=c.country AND t.city<>c.city) n_mismatch_dom_raw,
        round(100*avg(CASE WHEN t.city IS NOT NULL AND t.country<>c.country THEN (t.city=c.city)::INT END),3) pct_same_city_foreign
      FROM tx t LEFT JOIN cu c USING(customer_id)""")

if part == 'citymis':
    show("tx 'Mexico' (sin acento) de clientes mexicanos: ¿ciudad aleatoria entre ciudades MX?", """
      SELECT t.city, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct,
             round(100*avg((t.city=c.city)::INT),2) pct_eq_cu_city
      FROM tx t JOIN cu c USING(customer_id) WHERE t.country_raw='Mexico' AND c.country='México' GROUP BY 1 ORDER BY 2 DESC""")
    show("distribución de ciudades de clientes MX (para comparar con azar)", """
      SELECT city, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct FROM cu WHERE country='México' GROUP BY 1 ORDER BY 2 DESC""")
    show("esperado por azar P(ciudad tx = ciudad cliente) si ciudad uniforme sobre las ciudades vistas en 'Mexico' raw", """
      WITH tc AS (SELECT city, count(*)*1.0/sum(count(*)) OVER () p FROM tx WHERE country_raw='Mexico' AND city IS NOT NULL GROUP BY 1),
           cc AS (SELECT city, count(*)*1.0/sum(count(*)) OVER () q FROM cu WHERE country='México' GROUP BY 1)
      SELECT sum(p*q) expected_match FROM tc JOIN cc USING(city)""")
    show("extranjeras (país tx ≠ país cliente, normalizado): ciudades top por país de la tx", """
      SELECT t.country, t.city, count(*) n FROM tx t JOIN cu c USING(customer_id)
      WHERE t.country<>c.country GROUP BY 1,2
      QUALIFY row_number() OVER (PARTITION BY t.country ORDER BY count(*) DESC) <= 6 ORDER BY 1, 3 DESC""")
    show("nº ciudades distintas por país de la tx", "SELECT country, count(DISTINCT city) ncity FROM tx GROUP BY 1 ORDER BY 1")
    show("mismatches domésticos (normalizado): ¿cuántos vienen de country_raw='Mexico'?", """
      SELECT t.country_raw, count(*) n_mismatch FROM tx t JOIN cu c USING(customer_id)
      WHERE t.city IS NOT NULL AND t.country=c.country AND t.city<>c.city GROUP BY 1 ORDER BY 2 DESC""")

if part == 'impute':
    show("city nula: cobertura imputable (norm vs raw) y precisión simulada en city no nula", """
      SELECT
        count(*) FILTER (WHERE t.city IS NULL) n_null,
        round(100*avg(CASE WHEN t.city IS NULL THEN (t.country=c.country)::INT END),3) pct_null_dom_norm,
        round(100*avg(CASE WHEN t.city IS NULL THEN (t.country_raw=c.country)::INT END),3) pct_null_dom_raw,
        round(100*avg(CASE WHEN t.city IS NULL THEN (t.country=c.country)::INT END)*avg((t.city IS NULL)::INT),3) pct_all_tx_imputable_norm,
        round(100*avg(CASE WHEN t.city IS NOT NULL AND t.country=c.country THEN (t.city=c.city)::INT END),3) acc_norm,
        round(100*avg(CASE WHEN t.city IS NOT NULL AND t.country_raw=c.country THEN (t.city=c.city)::INT END),3) acc_raw
      FROM tx t JOIN cu c USING(customer_id)""")

if part == 'nulls':
    show("city nula por fraude", "SELECT fraud, count(*) n, round(100*avg((city IS NULL)::INT),3) pct_city_null FROM tx GROUP BY 1 ORDER BY 1")
    show("city nula por status", "SELECT status, count(*) n, round(100*avg((city IS NULL)::INT),3) pct_city_null FROM tx GROUP BY 1 ORDER BY 1")
    show("city nula por canal y ttype", "SELECT channel, count(*) n, round(100*avg((city IS NULL)::INT),3) pct_city_null FROM tx GROUP BY 1 ORDER BY 1")
    show("city nula por ttype", "SELECT ttype, count(*) n, round(100*avg((city IS NULL)::INT),3) pct_city_null FROM tx GROUP BY 1 ORDER BY 1")
    show("city nula vs lat nula (¿nulos correlacionados?)", """
      SELECT (city IS NULL) city_null, count(*) n, round(100*avg((lat IS NULL)::INT),3) pct_lat_null,
             round(100*avg((fscore IS NULL)::INT),3) pct_fscore_null, round(100*avg((branch_id IS NULL)::INT),3) pct_branch_null
      FROM tx GROUP BY 1 ORDER BY 1""")

def cramers_v(tab):
    tab = np.asarray(tab, dtype=float)
    chi2 = chi2_contingency(tab, correction=False)[0]
    n = tab.sum(); r, k = tab.shape
    v = np.sqrt(chi2 / n / (min(r, k) - 1))
    # V corregido por sesgo (Bergsma 2013)
    phi2c = max(0.0, chi2 / n - (k - 1) * (r - 1) / (n - 1))
    rc = r - (r - 1) ** 2 / (n - 1); kc = k - (k - 1) ** 2 / (n - 1)
    vc = np.sqrt(phi2c / min(kc - 1, rc - 1))
    return float(v), float(vc), float(chi2)

if part == 'channel':
    show("nulos de channel/ttype", "SELECT count(*) n, count(channel) ch_nn, count(ttype) tt_nn FROM tx")
    m = con.execute("SELECT coalesce(ttype,'NULL') ttype, coalesce(channel,'NULL') channel, count(*) n FROM tx GROUP BY 1,2").df()
    pv = m.pivot(index='ttype', columns='channel', values='n').fillna(0)
    v, vc, chi2 = cramers_v(pv.values)
    print(f"\nV(ttype, channel) = {v:.5f}  V_corr = {vc:.5f}  chi2 = {chi2:.1f}  gl = {(pv.shape[0]-1)*(pv.shape[1]-1)}  n = {int(pv.values.sum())}")
    pct = pv.div(pv.sum(1), axis=0) * 100
    print("\n% de canal dentro de cada ttype:")
    print(pct.round(2).assign(n=pv.sum(1).astype(int)).to_string())
    marg = pv.sum(0) / pv.values.sum() * 100
    print("\nmarginal canal %:"); print(marg.round(3).to_string())
    dev = (pct - marg).abs()
    print(f"\nmáx |p(canal|ttype) - p(canal)| = {dev.values.max():.3f} pp ; ratio máx p(canal|ttype)/p(canal) = {(pct/marg).values.max():.4f} ; min = {(pct/marg).values.min():.4f}")
    # ¿el canal depende de algo más? status, tcat, fraude, país extranjero, mcat
    for a, b in [('status', 'channel'), ('tcat', 'channel'), ('mcat', 'channel'), ('currency', 'channel')]:
        mm = con.execute(f"SELECT coalesce({a},'NULL') a, coalesce({b},'NULL') b, count(*) n FROM tx GROUP BY 1,2").df()
        pv2 = mm.pivot(index='a', columns='b', values='n').fillna(0)
        v2, vc2, _ = cramers_v(pv2.values)
        print(f"V({a},{b}) = {v2:.4f}  V_corr = {vc2:.4f}  shape={pv2.shape}")
    show("canal: tasas de fraude/rechazo y extranjera", """
      SELECT t.channel, count(*) n, round(1000*avg(t.fraud::INT),3) fraud_pm, round(100*avg((t.status='Declined')::INT),3) decl_pct,
             round(100*avg((t.country<>c.country)::INT),3) foreign_pct, round(100*avg((t.merchant_name IS NOT NULL)::INT),2) merch_pct
      FROM tx t JOIN cu c USING(customer_id) GROUP BY 1 ORDER BY 2 DESC""")
    show("ejemplos incoherentes: depósitos por POS, retiros por Web/App, compras por ATM (conteos)", """
      SELECT ttype, channel, count(*) n FROM tx
      WHERE (ttype='Deposit' AND channel='POS') OR (ttype='Withdrawal' AND channel IN ('Web','App')) OR (ttype='Purchase' AND channel='ATM')
      GROUP BY 1,2 ORDER BY 1,2""")

if part == 'branch':
    show("branch_id presente por canal", """
      SELECT channel, count(*) n, count(branch_id) n_branch, round(100*avg((branch_id IS NOT NULL)::INT),3) pct_branch FROM tx GROUP BY 1 ORDER BY 2 DESC""")
    show("tx con branch_id: existencia en br, país/ciudad de la sucursal vs tx y vs cliente", """
      SELECT count(*) n_con_branch,
        round(100*avg((b.branch_id IS NOT NULL)::INT),3) pct_existe_br,
        round(100*avg((b.country=t.country)::INT),3) pct_brctry_eq_txctry,
        round(100*avg((b.country=c.country)::INT),3) pct_brctry_eq_cuctry,
        round(100*avg(CASE WHEN t.city IS NOT NULL THEN (b.city=t.city)::INT END),3) pct_brcity_eq_txcity_nn,
        round(100*avg((b.city=c.city)::INT),3) pct_brcity_eq_cucity,
        round(100*avg(CASE WHEN t.city IS NOT NULL AND t.country_raw=c.country THEN (b.city=t.city)::INT END),3) pct_brcity_eq_txcity_dom_raw,
        round(100*avg(CASE WHEN t.country_raw<>c.country THEN (b.country=t.country)::INT END),3) pct_foreign_brctry_eq_txctry,
        round(100*avg(CASE WHEN t.country_raw<>c.country THEN (b.country=c.country)::INT END),3) pct_foreign_brctry_eq_cuctry
      FROM tx t LEFT JOIN br b USING(branch_id) JOIN cu c USING(customer_id) WHERE t.branch_id IS NOT NULL""")
    show("baseline azar: P(ciudad sucursal = ciudad cliente) si la sucursal fuera aleatoria (ponderada por nº sucursales) dentro del país del cliente", """
      WITH bc AS (SELECT country, city, count(*)*1.0/sum(count(*)) OVER (PARTITION BY country) p FROM br GROUP BY 1,2),
           tc AS (SELECT c.country, c.city, count(*) n FROM tx t JOIN cu c USING(customer_id) WHERE t.branch_id IS NOT NULL GROUP BY 1,2)
      SELECT sum(tc.n*coalesce(bc.p,0))/sum(tc.n) expected_same_city_random_branch FROM tc LEFT JOIN bc USING(country, city)""")
    show("baseline alternativo: sucursal elegida por ciudad uniforme dentro del país del cliente", """
      WITH bc AS (SELECT country, city, 1.0/count(*) OVER (PARTITION BY country) p FROM (SELECT DISTINCT country, city FROM br)),
           tc AS (SELECT c.country, c.city, count(*) n FROM tx t JOIN cu c USING(customer_id) WHERE t.branch_id IS NOT NULL GROUP BY 1,2)
      SELECT sum(tc.n*coalesce(bc.p,0))/sum(tc.n) expected_same_city_uniform_city FROM tc LEFT JOIN bc USING(country, city)""")
    show("P(ciudad sucursal = ciudad cliente) por ciudad del cliente vs cuota de sucursales de esa ciudad en su país", """
      WITH bc AS (SELECT country, city, count(*) nb, count(*)*1.0/sum(count(*)) OVER (PARTITION BY country) shr FROM br GROUP BY 1,2)
      SELECT c.country, c.city, count(*) n, round(100*avg((b.city=c.city)::INT),2) pct_same, round(100*any_value(bc.shr),2) pct_branches_share
      FROM tx t JOIN br b USING(branch_id) JOIN cu c USING(customer_id) LEFT JOIN bc ON bc.country=c.country AND bc.city=c.city
      WHERE t.country_raw=c.country GROUP BY 1,2 ORDER BY 1,2""")
    show("sucursales por país/ciudad (br)", "SELECT country, city, count(*) n FROM br GROUP BY 1,2 ORDER BY 1,3 DESC")
    show("país de sucursal ≠ país tx: ¿de dónde viene?", """
      SELECT (t.country_raw=c.country) dom_raw, b.country=t.country br_eq_tx, b.country=c.country br_eq_cu, count(*) n
      FROM tx t JOIN br b USING(branch_id) JOIN cu c USING(customer_id) GROUP BY 1,2,3 ORDER BY 1,2,3""")
    show("¿cliente usa siempre la misma sucursal? (clientes con ≥5 tx con sucursal)", """
      WITH x AS (SELECT customer_id, count(*) n, count(DISTINCT branch_id) nb FROM tx WHERE branch_id IS NOT NULL GROUP BY 1 HAVING count(*)>=5)
      SELECT count(*) ncust, round(avg(n),2) avg_n, round(avg(nb*1.0/n),4) ratio_distinct FROM x""")
    show("branch_status / abierta antes de la tx", """
      SELECT b.branch_type, b.branch_status, count(*) n, round(100*avg((b.opened <= t.ts::DATE)::INT),2) pct_abierta_antes
      FROM tx t JOIN br b USING(branch_id) GROUP BY 1,2 ORDER BY 3 DESC""")

if part == 'latlon':
    show("nulidad lat/lon", """
      SELECT count(*) n, round(100*avg((lat IS NULL)::INT),3) pct_lat_null, round(100*avg((lon IS NULL)::INT),3) pct_lon_null,
             round(100*avg(((lat IS NULL)<>(lon IS NULL))::INT),4) pct_solo_uno_nulo FROM tx""")
    show("lat no nula por canal / fraude / status", """
      SELECT 'channel' k, channel v, count(*) n, round(100*avg((lat IS NOT NULL)::INT),3) pct_lat_nn FROM tx GROUP BY 1,2
      UNION ALL SELECT 'fraud', fraud::VARCHAR, count(*), round(100*avg((lat IS NOT NULL)::INT),3) FROM tx GROUP BY 1,2
      UNION ALL SELECT 'status', status, count(*), round(100*avg((lat IS NOT NULL)::INT),3) FROM tx GROUP BY 1,2 ORDER BY 1,2""")
    show("medias/rango por país de la TX (lat no nula)", """
      SELECT country tx_country, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon,
             round(min(lat),3) minlat, round(max(lat),3) maxlat, round(min(lon),3) minlon, round(max(lon),3) maxlon
      FROM tx WHERE lat IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
    show("medias/rango por país del CLIENTE x doméstica(raw) (lat no nula)", """
      SELECT c.country cu_country, (t.country_raw=c.country) dom_raw, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon,
             round(min(t.lat),3) minlat, round(max(t.lat),3) maxlat, round(min(t.lon),3) minlon, round(max(t.lon),3) maxlon,
             round(stddev(t.lat),4) sdlat, round(stddev(t.lon),4) sdlon
      FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""")
    show("extranjeras: coordenadas por país de la tx (clientes MX/CO/AR)", """
      SELECT c.country cu_country, t.country_raw, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon,
             round(min(t.lat),2) minlat, round(max(t.lat),2) maxlat
      FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND t.country_raw<>c.country GROUP BY 1,2 ORDER BY 1,2""")
    show("¿la ciudad mueve el centro? medias por (país cliente, ciudad tx) en domésticas raw", """
      SELECT c.country cu_country, coalesce(t.city,'NULL') tx_city, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon,
             round(stddev(t.lat),3) sdlat, round(stddev(t.lon),3) sdlon
      FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND t.country_raw=c.country GROUP BY 1,2 ORDER BY 1,2""")
    show("coordenadas de sucursales (br) por ciudad, para comparar", """
      SELECT country, city, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(stddev(lat),3) sdlat FROM br GROUP BY 1,2 ORDER BY 1,2""")
    show("distribución de lat - 4.711 para clientes CO domésticos (bins de 0.2°)", """
      SELECT floor((t.lat-4.711)/0.2)*0.2 bin, count(*) n FROM tx t JOIN cu c USING(customer_id)
      WHERE t.lat IS NOT NULL AND c.country='Colombia' AND t.country_raw='Colombia' GROUP BY 1 ORDER BY 1""")
    show("distancia tx-sucursal (L1 grados) cuando hay ambas", """
      SELECT count(*) n, round(median(abs(t.lat-b.lat)+abs(t.lon-b.lon)),3) med_l1,
             round(100*avg((abs(t.lat-b.lat)<0.05 AND abs(t.lon-b.lon)<0.05)::INT),3) pct_cerca_005
      FROM tx t JOIN br b USING(branch_id) WHERE t.lat IS NOT NULL""")

if part == 'extra':
    show("medianas por país de la TX (¿de ahí salen (4.69,-74.05) y (-34.55,-58.38)?)", """
      SELECT country tx_country, count(*) n, round(median(lat),3) medlat, round(median(lon),3) medlon
      FROM tx WHERE lat IS NOT NULL AND lon IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
    show("centro exacto (punto medio del rango) por país del CLIENTE", """
      SELECT c.country cu_country, count(*) n, round((min(t.lat)+max(t.lat))/2,4) clat, round((min(t.lon)+max(t.lon))/2,4) clon
      FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL GROUP BY 1 ORDER BY 1""")
    show("% dentro de ±1° del centro del país del CLIENTE vs del país de la TX (lat y lon no nulas)", """
      WITH k AS (SELECT * FROM (VALUES ('Argentina', -34.6037, -58.3816), ('Colombia', 4.7110, -74.0721), ('México', 0.0, 0.0)) v(country, clat, clon))
      SELECT count(*) n,
        round(100*avg((abs(t.lat-kc.clat)<=1.0001 AND abs(t.lon-kc.clon)<=1.0001)::INT),3) pct_en_centro_pais_cliente,
        round(100*avg(coalesce((abs(t.lat-kt.clat)<=1.0001 AND abs(t.lon-kt.clon)<=1.0001)::INT,0)),3) pct_en_centro_pais_tx,
        count(*) FILTER (WHERE t.country_raw<>c.country) n_foreign,
        round(100*avg(CASE WHEN t.country_raw<>c.country THEN (abs(t.lat-kc.clat)<=1.0001 AND abs(t.lon-kc.clon)<=1.0001)::INT END),3) pct_foreign_en_centro_cliente
      FROM tx t JOIN cu c USING(customer_id) JOIN k kc ON kc.country=c.country LEFT JOIN k kt ON kt.country=t.country
      WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL""")
    show("nulidad conjunta lat/lon en canales físicos (POS/ATM/Branch)", """
      SELECT (lat IS NULL) lat_null, (lon IS NULL) lon_null, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),3) pct
      FROM tx WHERE channel IN ('POS','ATM','Branch') GROUP BY 1,2 ORDER BY 1,2""")
    show("distribución de lon - (-74.0721) para clientes CO (bins 0.2°)", """
      SELECT floor((t.lon+74.0721)/0.2)*0.2 bin, count(*) n FROM tx t JOIN cu c USING(customer_id)
      WHERE t.lon IS NOT NULL AND c.country='Colombia' GROUP BY 1 ORDER BY 1""")
    show("¿coordenadas fijas por cliente? sd de lat dentro de cliente (≥5 tx con lat) vs global 0.577", """
      WITH k AS (SELECT customer_id, count(*) n, stddev(lat) s FROM tx WHERE lat IS NOT NULL GROUP BY 1 HAVING count(*)>=5)
      SELECT count(*) ncust, round(avg(s),4) mean_within_sd FROM k""")
    show("foreign share por país del cliente (raw)", """
      SELECT c.country, count(*) n, round(100*avg((t.country_raw<>c.country)::INT),3) pct_foreign_raw, round(100*avg((t.country<>c.country)::INT),3) pct_foreign_norm
      FROM tx t JOIN cu c USING(customer_id) GROUP BY 1 ORDER BY 1""")
