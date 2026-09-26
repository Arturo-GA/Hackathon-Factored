"""Verificador escéptico (reintento) de behavior_ciudad_cliente_canal_ruido.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_behavior_ciudad_cliente_canal_ruido_skeptic_r2.py <parte>
Partes: city | mismatch | nulls | foreign | channel | channel2 | branch | branch2 | latlon | latlon2
Todo agregado en SQL (DuckDB read-only)."""
import sys
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency

pd.set_option("display.width", 240); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(sql):
    return con.execute(sql).df()
def show(title, sql):
    print(f"\n### {title}", flush=True)
    print(q(sql).to_string(), flush=True)
def cramers_v(pv):
    pv = np.asarray(pv, dtype=float)
    chi2 = chi2_contingency(pv, correction=False)[0]
    return float(np.sqrt(chi2 / pv.sum() / (min(pv.shape) - 1)))

part = sys.argv[1] if len(sys.argv) > 1 else 'city'

if part == 'city':
    show("Denominadores globales", """
    SELECT count(*) n_tx, count(c.customer_id) n_join_cu, count(t.city) n_city_nn,
      avg((t.city IS NULL)::INT) p_city_null,
      avg((t.country = c.country)::INT) p_dom_norm,
      avg((t.country_raw = c.country)::INT) p_dom_exact,
      avg((t.country IS NULL)::INT) p_country_null
    FROM tx t LEFT JOIN cu c USING(customer_id)""")
    show("P(tx.city = cu.city) por tipo de domesticidad (denominador: city no nula)", """
    SELECT CASE WHEN t.country_raw = c.country THEN '1_dom_exacta'
                WHEN t.country = c.country THEN '2_dom_solo_normalizada'
                ELSE '3_extranjera' END grupo,
      count(*) n, avg((t.city = c.city)::INT) p_same_city
    FROM tx t JOIN cu c USING(customer_id) WHERE t.city IS NOT NULL GROUP BY 1 ORDER BY 1""")
    show("Idem por país del cliente", """
    SELECT c.country cu_country,
      count(*) FILTER (WHERE t.country=c.country) n_dom,
      avg((t.city=c.city)::INT) FILTER (WHERE t.country=c.country) p_same_dom_norm,
      avg((t.city=c.city)::INT) FILTER (WHERE t.country_raw=c.country) p_same_dom_exact,
      avg((t.city=c.city)::INT) p_same_all_nn
    FROM tx t JOIN cu c USING(customer_id) WHERE t.city IS NOT NULL GROUP BY 1 ORDER BY 1""")
    show("country_raw -> country (todas)", "SELECT country_raw, country, count(*) n FROM tx GROUP BY 1,2 ORDER BY 3 DESC LIMIT 40")

if part == 'mismatch':
    show("Domésticas (normalizadas) con ciudad distinta: por country_raw", """
    SELECT t.country_raw, c.country cu_country, count(*) n_dom,
      sum((t.city<>c.city)::INT) n_mis, avg((t.city<>c.city)::INT) p_mis
    FROM tx t JOIN cu c USING(customer_id)
    WHERE t.city IS NOT NULL AND t.country=c.country GROUP BY 1,2 ORDER BY 1,2""")
    show("Mismatches domésticos: ¿la ciudad de la tx es de otro país? (mapa ciudad->país de cu)", """
    WITH cm AS (SELECT city, string_agg(DISTINCT country, '|') ctry FROM cu GROUP BY 1)
    SELECT c.country cu_country, t.country_raw, coalesce(cm.ctry,'(no está en cu)') pais_de_la_ciudad, count(*) n
    FROM tx t JOIN cu c USING(customer_id) LEFT JOIN cm ON cm.city=t.city
    WHERE t.city IS NOT NULL AND t.country=c.country AND t.city<>c.city GROUP BY ALL ORDER BY n DESC LIMIT 20""")
    show("Top mismatches", """
    SELECT c.country cu_country, t.country_raw, t.city tx_city, c.city cu_city, count(*) n
    FROM tx t JOIN cu c USING(customer_id)
    WHERE t.city IS NOT NULL AND t.country=c.country AND t.city<>c.city GROUP BY ALL ORDER BY n DESC LIMIT 12""")

if part == 'nulls':
    show("Nulidad de city por fraude", "SELECT fraud, count(*) n, avg((city IS NULL)::INT) p_null FROM tx GROUP BY 1 ORDER BY 1")
    show("Nulidad de city por status", "SELECT status, count(*) n, avg((city IS NULL)::INT) p_null FROM tx GROUP BY 1 ORDER BY 1")
    show("Nulidad de city por canal / ttype", "SELECT channel, count(*) n, avg((city IS NULL)::INT) p_null FROM tx GROUP BY 1 ORDER BY 1")
    show("Nulidad city por ttype", "SELECT ttype, count(*) n, avg((city IS NULL)::INT) p_null FROM tx GROUP BY 1 ORDER BY 1")
    show("Nulidad de city por domesticidad", """
    SELECT (t.country_raw=c.country) dom_exact, (t.country=c.country) dom_norm, count(*) n, avg((t.city IS NULL)::INT) p_null
    FROM tx t JOIN cu c USING(customer_id) GROUP BY 1,2 ORDER BY 1,2""")
    show("Co-nulidad city vs lat, fscore, country, merchant", """
    SELECT (city IS NULL) city_null, count(*) n, avg((lat IS NULL)::INT) p_lat_null, avg((fscore IS NULL)::INT) p_fs_null,
      avg((country_raw IS NULL)::INT) p_ctry_null, avg((merchant_name IS NULL)::INT) p_merch_null
    FROM tx GROUP BY 1 ORDER BY 1""")
    show("Imputación: cobertura sobre city nula", """
    SELECT count(*) n_null, avg((t.country=c.country)::INT) p_imputable_norm, avg((t.country_raw=c.country)::INT) p_imputable_exact
    FROM tx t JOIN cu c USING(customer_id) WHERE t.city IS NULL""")

if part == 'foreign':
    show("Extranjeras: país tx vs país cliente", """
    SELECT c.country cu_country, t.country tx_country, count(*) n, avg((t.city IS NULL)::INT) p_city_null,
      avg((t.city=c.city)::INT) FILTER (WHERE t.city IS NOT NULL) p_city_eq_cust
    FROM tx t JOIN cu c USING(customer_id) WHERE t.country<>c.country GROUP BY 1,2 ORDER BY 1, 3 DESC""")
    show("Extranjeras: top ciudades por país de la tx", """
    SELECT t.country tx_country, t.city, count(*) n FROM tx t JOIN cu c USING(customer_id)
    WHERE t.country<>c.country AND t.city IS NOT NULL GROUP BY 1,2
    QUALIFY row_number() OVER (PARTITION BY t.country ORDER BY count(*) DESC) <= 5 ORDER BY 1, 3 DESC""")
    show("Nº de ciudades distintas: cu por país vs tx doméstica vs br", """
    SELECT a.country, a.n_city_cu, b.n_city_tx, d.n_city_br FROM
      (SELECT country, count(DISTINCT city) n_city_cu FROM cu GROUP BY 1) a
      LEFT JOIN (SELECT country, count(DISTINCT city) n_city_tx FROM tx GROUP BY 1) b USING(country)
      LEFT JOIN (SELECT country, count(DISTINCT city) n_city_br FROM br GROUP BY 1) d USING(country)
    ORDER BY 1""")
    show("¿Extranjera = misma para todo el cliente? P(cliente con >=1 extranjera) y dispersión", """
    WITH k AS (SELECT t.customer_id, count(*) n, avg((t.country<>c.country)::INT) pf FROM tx t JOIN cu c USING(customer_id) GROUP BY 1)
    SELECT count(*) n_cust, avg((pf>0)::INT) p_cust_any_foreign, avg(pf) mean_pf, stddev(pf) sd_pf, avg(n) mean_n,
      -- binomial esperado de la sd si pf~Bin(n,0.046)/n
      sqrt(avg(0.046*0.954/n)) sd_binom_esperada FROM k""")

if part == 'channel':
    m = q("SELECT ttype, channel, count(*) n FROM tx GROUP BY 1,2")
    pv = m.pivot(index='ttype', columns='channel', values='n').fillna(0)
    print("V(ttype, channel) =", round(cramers_v(pv.values), 5), " n =", int(pv.values.sum()))
    sh = pv.div(pv.sum(1), axis=0) * 100
    print((sh.round(2)).assign(n=pv.sum(1).astype(int)).to_string())
    marg = pv.sum(0) / pv.values.sum() * 100
    print("marginal:", marg.round(2).to_dict())
    print("max |p(canal|ttype)-p(canal)| (pp) =", round(float((sh - marg).abs().max().max()), 3))
    # canal vs ptype (producto)
    m = q("SELECT p.ptype, t.channel, count(*) n FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2")
    pv = m.pivot(index='ptype', columns='channel', values='n').fillna(0)
    print("\nV(ptype, channel) =", round(cramers_v(pv.values), 5))
    print((pv.div(pv.sum(1), axis=0) * 100).round(2).assign(n=pv.sum(1).astype(int)).to_string())
    for a in ['status', 'mcat', 'tcat', 'currency', 'country', 'code']:
        m = q(f"SELECT coalesce({a}::VARCHAR,'NULL') a, channel, count(*) n FROM tx GROUP BY 1,2")
        pv = m.pivot(index='a', columns='channel', values='n').fillna(0)
        print(f"V({a}, channel) = {cramers_v(pv.values):.5f}  shape={pv.shape}")
    show("Canal: fraude, rechazo, monto (mediana en USD-equivalente por moneda), presencia de comercio", """
    SELECT channel, count(*) n, 1000*avg(fraud::INT) fraud_pm, 100*avg((status='Declined')::INT) decl_pct,
      avg((merchant_name IS NOT NULL)::INT) p_merch, avg((lat IS NOT NULL)::INT) p_latlon,
      median(amount) FILTER (WHERE currency='USD') med_usd, median(amount) FILTER (WHERE currency='COP') med_cop,
      median(amount) FILTER (WHERE currency='ARS') med_ars
    FROM tx GROUP BY 1 ORDER BY 2 DESC""")

if part == 'channel2':
    # hábito por cliente: ¿el canal de una tx repite el de la anterior del mismo cliente más que por azar? (muestra 1/8 clientes)
    con.execute("CREATE TEMP TABLE s AS SELECT customer_id, ts, channel, branch_id, city FROM tx WHERE hash(customer_id) % 8 = 0")
    for col in ['channel', 'branch_id']:
        r = q(f"""WITH x AS (SELECT {col} v, lag({col}) OVER (PARTITION BY customer_id ORDER BY ts) pv FROM s WHERE {col} IS NOT NULL),
           m AS (SELECT {col} v, count(*)*1.0/sum(count(*)) OVER () p FROM s WHERE {col} IS NOT NULL GROUP BY 1)
           SELECT (SELECT avg((v=pv)::INT) FROM x WHERE pv IS NOT NULL) obs, (SELECT count(*) FROM x WHERE pv IS NOT NULL) n_pairs, (SELECT sum(p*p) FROM m) exp_iid""")
        o, n, e = r.iloc[0]
        print(f"{col:10s} P(igual a la anterior)={o:.4f} (n pares={int(n)}) esperado iid={e:.4f} ratio={o/e:.3f}")
    # canal por cliente: V(customer, channel) no es interpretable; mejor: dispersión de la proporción de POS por cliente vs binomial
    show("Dispersión por cliente de p(POS) vs binomial (clientes con >=20 tx)", """
    WITH k AS (SELECT customer_id, count(*) n, avg((channel='POS')::INT) p FROM tx GROUP BY 1 HAVING count(*)>=20),
         g AS (SELECT avg((channel='POS')::INT) pg FROM tx)
    SELECT count(*) n_cust, var_samp(p) var_obs, avg(pg*(1-pg)/n) var_binom, var_samp(p)/avg(pg*(1-pg)/n) ratio FROM k, g""")
    # canal vs atributos del cliente
    for a in ['segment', 'country', 'gender']:
        m = q(f"SELECT coalesce(c.{a}::VARCHAR,'NULL') a, t.channel, count(*) n FROM tx t JOIN cu c USING(customer_id) GROUP BY 1,2")
        pv = m.pivot(index='a', columns='channel', values='n').fillna(0)
        print(f"V(cu.{a}, channel) = {cramers_v(pv.values):.5f}")
    show("Canal vs edad del cliente (tasa de App/Web por decil de edad)", """
    WITH x AS (SELECT t.channel, date_diff('year', c.dob, t.ts::DATE) age FROM tx t JOIN cu c USING(customer_id))
    SELECT CASE WHEN age<30 THEN '<30' WHEN age<45 THEN '30-44' WHEN age<60 THEN '45-59' ELSE '60+' END edad, count(*) n,
      avg((channel IN ('App','Web'))::INT) p_digital, avg((channel='Branch')::INT) p_branch FROM x GROUP BY 1 ORDER BY 1""")
    show("Canal vs app en producto (pr.app)", """
    SELECT p.app, count(*) n, avg((t.channel='App')::INT) p_app_channel FROM tx t JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1""")

if part == 'branch':
    show("branch_id presente por canal", "SELECT channel, count(*) n, avg((branch_id IS NOT NULL)::INT) p_branch FROM tx GROUP BY 1 ORDER BY 2 DESC")
    show("Existencia en br y coincidencias (denominador: tx con branch_id)", """
    SELECT count(*) n, avg((b.branch_id IS NOT NULL)::INT) p_exists,
      avg((b.country=t.country)::INT) p_br_ctry_eq_tx, avg((b.country=c.country)::INT) p_br_ctry_eq_cust,
      avg((b.city=t.city)::INT) FILTER (WHERE t.city IS NOT NULL) p_br_city_eq_tx,
      avg((b.city=c.city)::INT) p_br_city_eq_cust,
      avg((b.city=c.city)::INT) FILTER (WHERE t.country=c.country) p_br_city_eq_cust_dom,
      avg((b.opened <= t.ts::DATE)::INT) p_opened_before_tx
    FROM tx t LEFT JOIN br b USING(branch_id) JOIN cu c USING(customer_id) WHERE t.branch_id IS NOT NULL""")
    show("País sucursal vs país cliente vs país tx", """
    SELECT (t.country=c.country) tx_dom, (b.country=c.country) br_eq_cust, (b.country=t.country) br_eq_tx, count(*) n
    FROM tx t JOIN br b USING(branch_id) JOIN cu c USING(customer_id) GROUP BY ALL ORDER BY ALL""")
    show("Baseline: P(ciudad sucursal = ciudad cliente) si la sucursal fuera aleatoria (uniforme) dentro del país del cliente", """
    WITH bc AS (SELECT country, city, count(*)*1.0/sum(count(*)) OVER (PARTITION BY country) p FROM br GROUP BY 1,2),
         tc AS (SELECT c.country, c.city, count(*) n, sum((b.city=c.city)::INT) n_same
                FROM tx t JOIN br b USING(branch_id) JOIN cu c USING(customer_id) WHERE b.country=c.country GROUP BY 1,2)
    SELECT sum(tc.n) n, sum(tc.n_same)*1.0/sum(tc.n) observed, sum(tc.n*coalesce(bc.p,0))/sum(tc.n) expected_random
    FROM tc LEFT JOIN bc USING(country, city)""")
    show("Idem por país del cliente", """
    WITH bc AS (SELECT country, city, count(*)*1.0/sum(count(*)) OVER (PARTITION BY country) p FROM br GROUP BY 1,2),
         tc AS (SELECT c.country, c.city, count(*) n, sum((b.city=c.city)::INT) n_same
                FROM tx t JOIN br b USING(branch_id) JOIN cu c USING(customer_id) WHERE b.country=c.country GROUP BY 1,2)
    SELECT country, sum(tc.n) n, sum(tc.n_same)*1.0/sum(tc.n) observed, sum(tc.n*coalesce(bc.p,0))/sum(tc.n) expected_random
    FROM tc LEFT JOIN bc USING(country, city) GROUP BY 1 ORDER BY 1""")
    show("Distribución de sucursales usadas vs sucursales del país (¿uniforme?): top y cola", """
    WITH u AS (SELECT b.country, t.branch_id, count(*) n FROM tx t JOIN br b USING(branch_id) GROUP BY 1,2),
         s AS (SELECT country, count(*) n_br_used, sum(n) n_tx, min(n) mn, max(n) mx, stddev(n)/avg(n) cv FROM u GROUP BY 1),
         a AS (SELECT country, count(*) n_br_total FROM br GROUP BY 1)
    SELECT * FROM s JOIN a USING(country) ORDER BY 1""")

if part == 'branch2':
    show("tx.branch_id = sucursal de apertura del producto (pr.opening_branch_id)", """
    SELECT count(*) n, avg((t.branch_id = p.opening_branch_id)::INT) p_eq_opening,
      avg((p.opening_branch_id IS NOT NULL)::INT) p_opening_nn,
      avg((ob.branch_id IS NOT NULL)::INT) p_opening_exists
    FROM tx t JOIN pr p USING(product_id) LEFT JOIN br ob ON ob.branch_id=p.opening_branch_id WHERE t.branch_id IS NOT NULL""")
    show("tx.branch_id = registration_branch_id del cliente", """
    SELECT count(*) n, avg((t.branch_id = c.registration_branch_id)::INT) p_eq_reg FROM tx t JOIN cu c USING(customer_id) WHERE t.branch_id IS NOT NULL""")
    show("Reuso de sucursal por cliente (clientes con >=4 tx con sucursal): distintas/total vs esperado aleatorio", """
    WITH x AS (SELECT t.customer_id, c.country, count(*) n, count(DISTINCT t.branch_id) nb
               FROM tx t JOIN cu c USING(customer_id) WHERE t.branch_id IS NOT NULL GROUP BY 1,2 HAVING count(*)>=4)
    SELECT country, count(*) n_cust, avg(n) avg_n, avg(nb*1.0/n) ratio_distinct_obs FROM x GROUP BY 1 ORDER BY 1""")
    show("Nº sucursales por país (para el esperado aleatorio)", "SELECT country, count(*) n_br FROM br GROUP BY 1 ORDER BY 1")
    show("branch_type / branch_status de sucursales usadas, por canal", """
    SELECT t.channel, b.branch_type, b.branch_status, count(*) n FROM tx t JOIN br b USING(branch_id) GROUP BY ALL ORDER BY 1, 4 DESC""")
    show("ATM en sucursal sin cajeros (has_atms=false / atm_count=0)", """
    SELECT t.channel, count(*) n, avg((NOT b.has_atms)::INT) p_no_atms, avg((b.atm_count=0)::INT) p_atm0,
      avg((b.branch_status<>'Active')::INT) p_br_not_active
    FROM tx t JOIN br b USING(branch_id) GROUP BY 1 ORDER BY 1""")
    show("branch_id en canales no físicos y sin branch_id en ATM/Branch: ¿se asocia con algo? (fraude/estado)", """
    SELECT channel, (branch_id IS NULL) br_null, count(*) n, 1000*avg(fraud::INT) fraud_pm, 100*avg((status='Declined')::INT) decl_pct,
      avg((city IS NULL)::INT) p_city_null
    FROM tx WHERE channel IN ('ATM','Branch') GROUP BY 1,2 ORDER BY 1,2""")

if part == 'latlon':
    show("Nulidad lat/lon", """
    SELECT count(*) n, avg((lat IS NULL)::INT) p_lat_null, avg((lon IS NULL)::INT) p_lon_null,
      avg(((lat IS NULL)<>(lon IS NULL))::INT) p_xor FROM tx""")
    show("lat/lon presente por canal, fraude, status", """
    SELECT 'channel' k, channel v, count(*) n, avg((lat IS NOT NULL)::INT) p_ll FROM tx GROUP BY 1,2
    UNION ALL SELECT 'fraud', fraud::VARCHAR, count(*), avg((lat IS NOT NULL)::INT) FROM tx GROUP BY 1,2
    UNION ALL SELECT 'status', status, count(*), avg((lat IS NOT NULL)::INT) FROM tx GROUP BY 1,2
    UNION ALL SELECT 'ttype', ttype, count(*), avg((lat IS NOT NULL)::INT) FROM tx GROUP BY 1,2 ORDER BY 1,2""")
    show("Centro y rango por país de la TX (lat/lon no nulos)", """
    SELECT country tx_country, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(min(lat),3) minlat, round(max(lat),3) maxlat,
      round(min(lon),3) minlon, round(max(lon),3) maxlon FROM tx WHERE lat IS NOT NULL AND lon IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
    show("Centro y rango por (país cliente, país tx)", """
    SELECT c.country cu_country, t.country tx_country, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon,
      round(min(t.lat),2) minlat, round(max(t.lat),2) maxlat, round(min(t.lon),2) minlon, round(max(t.lon),2) maxlon
    FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL GROUP BY 1,2 ORDER BY 1, 3 DESC""")

if part == 'latlon2':
    show("¿Cambia el centro con la ciudad del cliente? (medias por ciudad, lat/lon no nulos)", """
    SELECT c.country, c.city, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon, round(stddev(t.lat),3) sdlat, round(stddev(t.lon),3) sdlon
    FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL GROUP BY 1,2 ORDER BY 1, 3 DESC""")
    show("Coordenadas reales de sucursales por país (br)", """
    SELECT country, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(min(lat),2) minlat, round(max(lat),2) maxlat FROM br GROUP BY 1 ORDER BY 1""")
    show("Distancia tx - sucursal (grados L1) cuando hay ambas", """
    SELECT t.channel, count(*) n, round(median(abs(t.lat-b.lat)+abs(t.lon-b.lon)),2) med_l1,
      avg((abs(t.lat-b.lat)<0.1 AND abs(t.lon-b.lon)<0.1)::INT) p_near
    FROM tx t JOIN br b USING(branch_id) WHERE t.lat IS NOT NULL GROUP BY 1""")
    show("Uniformidad: lat - centro por deciles (clientes CO y AR, tx doméstica)", """
    SELECT c.country, floor((t.lat - CASE c.country WHEN 'Colombia' THEN 4.711 ELSE -34.6037 END + 1)*5)::INT bin, count(*) n
    FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND c.country IN ('Colombia','Argentina') AND t.country=c.country
    GROUP BY 1,2 ORDER BY 1,2""")
    show("Dispersión dentro de cliente vs global (clientes con >=5 tx con lat)", """
    WITH k AS (SELECT t.customer_id, c.country, count(*) n, stddev(t.lat) s FROM tx t JOIN cu c USING(customer_id)
               WHERE t.lat IS NOT NULL GROUP BY 1,2 HAVING count(*)>=5),
         g AS (SELECT c.country, stddev(t.lat) sg FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL GROUP BY 1)
    SELECT k.country, count(*) n_cust, avg(s) mean_within_sd, any_value(sg) global_sd FROM k JOIN g USING(country) GROUP BY 1 ORDER BY 1""")
    show("Mexico: ¿(0,0) o centro real?", """
    SELECT c.country cu_country, t.country_raw, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon
    FROM tx t JOIN cu c USING(customer_id) WHERE t.lat IS NOT NULL AND c.country LIKE 'M%' GROUP BY 1,2 ORDER BY 3 DESC""")
