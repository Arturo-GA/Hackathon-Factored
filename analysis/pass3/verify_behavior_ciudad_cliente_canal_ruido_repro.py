"""Verificación independiente de behavior_ciudad_cliente_canal_ruido.
Parte A: ciudad de la tx vs ciudad del cliente, nulidad de city, imputación."""
import sys
import duckdb, numpy as np, pandas as pd
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
part = sys.argv[1] if len(sys.argv) > 1 else 'A'

if part == 'A':
    print("== cu.city / cu.country nulos")
    print(q("select count(*) n, count(city) city_nn, count(country) ctry_nn, count(distinct city) ncity from cu"))
    print("== tx: nulidad de city/country y domesticidad (denominador = todas las tx)")
    print(q("""select count(*) n,
        sum((t.city is null)::int) city_null, avg((t.city is null)::int) p_city_null,
        sum((c.customer_id is null)::int) no_cust,
        avg((t.country = c.country)::int) p_domestic,
        -- entre city no nula
        count(*) filter (where t.city is not null) n_city_nn,
        avg((t.city = c.city)::int) filter (where t.city is not null) p_samecity_all_nn,
        avg((t.city = c.city)::int) filter (where t.city is not null and t.country = c.country) p_samecity_domestic,
        count(*) filter (where t.city is not null and t.country = c.country) n_dom_nn,
        avg((t.city = c.city)::int) filter (where t.city is not null and t.country <> c.country) p_samecity_foreign,
        count(*) filter (where t.city is not null and t.country <> c.country) n_for_nn
      from tx t left join cu c using(customer_id)"""))
    print("== por país del cliente: p(domestic), p(misma ciudad | doméstica, city no nula)")
    print(q("""select c.country cc, count(*) n, avg((t.country=c.country)::int) p_dom,
        avg((t.city=c.city)::int) filter (where t.city is not null and t.country=c.country) p_same_dom,
        avg((t.city is null)::int) p_city_null
      from tx t join cu c using(customer_id) group by 1 order by 2 desc"""))
    print("== doméstico con ciudad distinta: top pares (tx.city, cu.city)")
    print(q("""select t.country, t.city tcity, c.city ccity, count(*) n from tx t join cu c using(customer_id)
       where t.city is not null and t.country=c.country and t.city<>c.city group by all order by n desc limit 15"""))
    print("== doméstico con ciudad distinta: ¿concentrado en pocos clientes?")
    print(q("""with d as (select t.customer_id, count(*) n, sum((t.city<>c.city)::int) nd from tx t join cu c using(customer_id)
         where t.city is not null and t.country=c.country group by 1)
       select count(*) ncust, sum((nd>0)::int) cust_with_diff, sum(nd) tot_diff, sum(n) tot,
         sum(nd) filter (where nd=n) diff_in_all_diff_customers, sum((nd=n and nd>0)::int) cust_all_diff,
         quantile_cont(nd*1.0/n, 0.99) p99_share from d"""))
if part in ('A2',):
    print("== country_raw: misma ciudad | tx.country=cu.country, por country_raw (city no nula)")
    print(q("""select c.country cc, t.country_raw, count(*) n, avg((t.city=c.city)::int) p_same
       from tx t join cu c using(customer_id) where t.city is not null and t.country=c.country group by 1,2 order by 1,2"""))
    print("== ¿todas las mismatches domésticas vienen de country_raw sin acento?")
    print(q("""select t.country_raw, count(*) n_mismatch from tx t join cu c using(customer_id)
       where t.city is not null and t.country=c.country and t.city<>c.city group by 1"""))
    print("== ciudad de tx con country_raw='Mexico' (clientes MX): distribución (¿aleatoria entre ciudades MX?)")
    print(q("""select t.city, count(*) n, round(100.0*count(*)/sum(count(*)) over(),2) pct from tx t join cu c using(customer_id)
       where t.country_raw='Mexico' and t.city is not null group by 1 order by 2 desc"""))
    print(q("""select c.country cc, count(*) n from tx t join cu c using(customer_id) where t.country_raw='Mexico' group by 1"""))
    print("== extranjeras: ciudad de la tx (top) por país de la tx")
    print(q("""select t.country, t.city, count(*) n from tx t join cu c using(customer_id)
       where t.country<>c.country group by t.country, t.city qualify row_number() over (partition by t.country order by count(*) desc)<=4 order by 1, 3 desc"""))
    print("== ¿la ciudad de tx extranjeras pertenece al conjunto de ciudades de clientes de ese país? ")
    print(q("""with cc as (select distinct country, city from cu)
       select t.country, count(*) n, avg((cc.city is not null)::int) city_in_cu_country
       from (select * from tx where city is not null) t left join cc on cc.country=t.country and cc.city=t.city group by 1 order by 2 desc"""))
    print("== nº ciudades distintas en tx por país")
    print(q("select country, count(distinct city) ncity from tx group by 1 order by 1"))
    print("== nulidad de city por fraude, estado, domesticidad, canal")
    print(q("select fraud, count(*) n, avg((city is null)::int) p_null from tx group by 1"))
    print(q("select status, count(*) n, avg((city is null)::int) p_null from tx group by 1 order by 2 desc"))
    print(q("""select (t.country=c.country) dom, count(*) n, avg((t.city is null)::int) p_null from tx t join cu c using(customer_id) group by 1"""))
    print(q("select channel, count(*) n, avg((city is null)::int) p_null from tx group by 1 order by 2 desc"))
    print("== imputación: de las city nulas, cuántas son domésticas (imputables)")
    print(q("""select count(*) n_null, avg((t.country=c.country)::int) p_dom_imputable from tx t join cu c using(customer_id) where t.city is null"""))

def cramers_v(tab):
    from scipy.stats import chi2_contingency
    tab = np.asarray(tab, dtype=float)
    chi2 = chi2_contingency(tab, correction=False)[0]
    n = tab.sum(); r, k = tab.shape
    return float(np.sqrt(chi2 / n / (min(r, k) - 1))), float(chi2)

if part == 'B':
    print("== channel / ttype nulos")
    print(q("select count(*) n, count(channel) ch_nn, count(ttype) tt_nn from tx"))
    m = q("select ttype, channel, count(*) n from tx group by 1,2")
    pv = m.pivot(index='ttype', columns='channel', values='n').fillna(0)
    v, chi2 = cramers_v(pv.values)
    print(f"Cramér V(ttype, channel) = {v:.5f}  chi2={chi2:.1f}  shape={pv.shape}")
    print("== % de canal dentro de cada ttype (filas suman 100)")
    print((pv.div(pv.sum(1), axis=0) * 100).round(2).assign(n=pv.sum(1).astype(int)))
    print("== marginal canal %")
    print((pv.sum(0) / pv.values.sum() * 100).round(2))
    # max desviación absoluta frente a la marginal
    dev = (pv.div(pv.sum(1), axis=0) - pv.sum(0) / pv.values.sum()).abs().max().max()
    print(f"max |p(canal|ttype) - p(canal)| = {dev*100:.3f} pp")
    # V con otras variables relevantes para ver si canal aporta algo
    for a, b in [('status', 'channel'), ('channel', 'mcat'), ('ttype', 'tcat')]:
        m = q(f"select coalesce({a},'NULL') a, coalesce({b},'NULL') b, count(*) n from tx group by 1,2")
        pv2 = m.pivot(index='a', columns='b', values='n').fillna(0)
        print(f"V({a},{b}) = {cramers_v(pv2.values)[0]:.4f}  shape={pv2.shape}")
    print("== fraude y rechazo por canal (tasas)")
    print(q("select channel, count(*) n, avg(fraud::int)*1000 fraud_pm, avg((status='Declined')::int)*100 decl_pct from tx group by 1 order by 2 desc"))
    print("== merchant_name / mcat presencia por canal y ttype")
    print(q("select channel, avg((merchant_name is not null)::int) p_merch, avg((mcat is not null)::int) p_mcat from tx group by 1 order by 1"))
    print(q("select ttype, avg((merchant_name is not null)::int) p_merch, avg((mcat is not null)::int) p_mcat from tx group by 1 order by 1"))

if part == 'C':
    print("== branch_id presente por canal")
    print(q("select channel, count(*) n, avg((branch_id is not null)::int) p_branch from tx group by 1 order by 2 desc"))
    print("== existencia en br y coincidencia de ciudad/país (denominador: tx con branch_id; ciudad: tx con city no nula)")
    print(q("""select t.channel, count(*) n, avg((b.branch_id is not null)::int) p_exists,
        avg((b.city=t.city)::int) filter (where t.city is not null) p_brcity_eq_txcity,
        avg((b.country=t.country)::int) p_brctry_eq_txctry,
        avg((b.country=c.country)::int) p_brctry_eq_custctry,
        avg((b.city=c.city)::int) p_brcity_eq_custcity
      from tx t left join br b using(branch_id) join cu c using(customer_id) where t.branch_id is not null group by 1"""))
    print(q("""select count(*) n, avg((b.city=t.city)::int) filter (where t.city is not null) p_brcity_eq_txcity,
        avg((b.country=t.country)::int) p_brctry_eq_txctry, avg((b.country=c.country)::int) p_brctry_eq_custctry,
        avg((b.city=c.city)::int) p_brcity_eq_custcity,
        avg((b.city=t.city)::int) filter (where t.city is not null and t.country_raw=c.country) p_brcity_eq_txcity_dom
      from tx t join br b using(branch_id) join cu c using(customer_id)"""))
    print("== ¿cuándo el país de la sucursal ≠ país del cliente?")
    print(q("""select (t.country_raw=c.country) dom_exact, (b.country=c.country) br_eq_cust, count(*) n
      from tx t join br b using(branch_id) join cu c using(customer_id) group by 1,2 order by 1,2"""))
    print("== baseline azar: P(ciudad sucursal = ciudad cliente) si la sucursal fuera aleatoria dentro del país del cliente")
    print(q("""with bc as (select country, city, count(*)*1.0/sum(count(*)) over (partition by country) p from br group by 1,2),
       tc as (select c.country, c.city, count(*) n from tx t join br b using(branch_id) join cu c using(customer_id) group by 1,2)
       select sum(tc.n*coalesce(bc.p,0))/sum(tc.n) expected_same_city_random from tc left join bc using(country, city)"""))
    print("== ciudades de br por país")
    print(q("select country, city, count(*) n from br group by 1,2 order by 1,3 desc"))
    print("== ciudades de cu por país")
    print(q("select country, city, count(*) n from cu group by 1,2 order by 1,3 desc"))
    print("== branch_type / branch_status de las sucursales usadas, y ¿abierta antes de la tx?")
    print(q("""select b.branch_type, b.branch_status, count(*) n, avg((b.opened <= t.ts::date)::int) p_opened_before
      from tx t join br b using(branch_id) group by 1,2 order by 3 desc"""))
    print("== ¿sucursal repetida por cliente? (nº sucursales distintas / nº tx con sucursal)")
    print(q("""with x as (select customer_id, count(*) n, count(distinct branch_id) nb from tx where branch_id is not null group by 1 having count(*)>=5)
       select count(*) ncust, avg(nb*1.0/n) ratio_distinct, avg(n) avg_n from x"""))

if part == 'D':
    print("== nulidad lat/lon")
    print(q("""select count(*) n, avg((lat is null)::int) p_lat_null, avg((lon is null)::int) p_lon_null,
        avg((lat is null and lon is null)::int) p_both_null, avg(((lat is null) <> (lon is null))::int) p_xor from tx"""))
    print(q("select channel, count(*) n, avg((lat is not null)::int) p_lat_nn from tx group by 1 order by 2 desc"))
    print(q("select fraud, count(*) n, avg((lat is null)::int) p_lat_null from tx group by 1"))
    print(q("select status, count(*) n, avg((lat is null)::int) p_lat_null from tx group by 1 order by 2 desc"))
    print("== centro y rango por país de la TX (lat no nula)")
    print(q("""select country, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(min(lat),3) minlat, round(max(lat),3) maxlat,
        round(min(lon),3) minlon, round(max(lon),3) maxlon from tx where lat is not null group by 1 order by 2 desc"""))
    print("== centro y rango por país del CLIENTE (lat no nula)")
    print(q("""select c.country cc, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon, round(min(t.lat),3) minlat, round(max(t.lat),3) maxlat,
        round(min(t.lon),3) minlon, round(max(t.lon),3) maxlon, round(stddev(t.lat),3) sdlat, round(stddev(t.lon),3) sdlon
      from tx t join cu c using(customer_id) where t.lat is not null group by 1 order by 2 desc"""))
    # Regla: dentro de ±1° de un centro definido por país del cliente vs país de la tx
    centers = "case {c} when 'Argentina' then -34.6037 when 'Colombia' then 4.711 when 'México' then 0 end"
    centers_lon = "case {c} when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 when 'México' then 0 end"
    print("== % dentro de ±1.0° (lat y lon) del centro según país del CLIENTE vs país de la TX")
    print(q(f"""select c.country cc, (t.country_raw=c.country) dom_exact, count(*) n,
        avg((abs(t.lat-({centers.format(c='c.country')}))<=1.0001 and abs(t.lon-({centers_lon.format(c='c.country')}))<=1.0001)::int) p_in_cust_center,
        avg((abs(t.lat-({centers.format(c='t.country')}))<=1.0001 and abs(t.lon-({centers_lon.format(c='t.country')}))<=1.0001)::int) p_in_tx_center,
        avg((abs(t.lat-({centers.format(c='c.country')}))<=1.0001)::int) p_lat_in_cust,
        avg((abs(t.lon-({centers_lon.format(c='c.country')}))<=1.0001)::int) p_lon_in_cust
      from tx t join cu c using(customer_id) where t.lat is not null and t.lon is not null group by 1,2 order by 1,2"""))
    print("== ¿cambia el centro con la ciudad? medias por (país cliente, ciudad tx) — lat no nula")
    print(q("""select c.country cc, coalesce(t.city,'NULL') city, count(*) n, round(avg(t.lat),3) mlat, round(avg(t.lon),3) mlon,
        round(stddev(t.lat),3) sdlat from tx t join cu c using(customer_id) where t.lat is not null group by 1,2 order by 1,2"""))
    print("== coordenadas reales de sucursales por ciudad (br) para comparar")
    print(q("select country, city, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(stddev(lat),3) sdlat from br group by 1,2 order by 1,2"))
    print("== casos fuera de todo centro (lat no nula)")
    print(q(f"""select c.country cc, count(*) n_out, round(min(t.lat),2) minlat, round(max(t.lat),2) maxlat, round(min(t.lon),2) minlon, round(max(t.lon),2) maxlon
       from tx t join cu c using(customer_id) where t.lat is not null and not (abs(t.lat-({centers.format(c='c.country')}))<=1.0001 and abs(t.lon-({centers_lon.format(c='c.country')}))<=1.0001)
       group by 1"""))
    print("== distancia tx-sucursal (grados) cuando hay ambas")
    print(q("""select count(*) n, round(median(abs(t.lat-b.lat)+abs(t.lon-b.lon)),2) med_l1, avg((abs(t.lat-b.lat)<0.1 and abs(t.lon-b.lon)<0.1)::int) p_near
       from tx t join br b using(branch_id) where t.lat is not null"""))
    print("== distribución de lat - centro (¿uniforme ±1?) para Colombia (clientes CO)")
    print(q("""select floor((t.lat-4.711+1)*5)::int b, count(*) n from tx t join cu c using(customer_id)
       where t.lat is not null and c.country='Colombia' group by 1 order by 1"""))

if part == 'E':
    print("== imputación de city nula: cobertura por regla normalizada vs exacta (country_raw = cu.country)")
    print(q("""select count(*) n_null,
        avg((t.country=c.country)::int) cov_norm, avg((t.country_raw=c.country)::int) cov_exact
      from tx t join cu c using(customer_id) where t.city is null"""))
    print("== precisión de la imputación simulada sobre city NO nula")
    print(q("""select
        avg((t.city=c.city)::int) filter (where t.country=c.country) acc_norm, count(*) filter (where t.country=c.country) n_norm,
        avg((t.city=c.city)::int) filter (where t.country_raw=c.country) acc_exact, count(*) filter (where t.country_raw=c.country) n_exact,
        count(*) n_nn
      from tx t join cu c using(customer_id) where t.city is not null"""))
    print("== presencia de branch_id y lat por ttype (¿dependen del ttype o solo del canal?)")
    print(q("""select ttype, count(*) n, avg((branch_id is not null)::int) p_branch, avg((lat is not null)::int) p_lat,
        avg((lat is not null)::int) filter (where channel in ('POS','ATM','Branch')) p_lat_physical
      from tx group by 1 order by 1"""))
    print("== foreign (country_raw<>cu.country) por país de la tx y por país del cliente")
    print(q("""select c.country cc, t.country_raw, count(*) n from tx t join cu c using(customer_id) where t.country_raw<>c.country group by 1,2 order by 1,3 desc"""))
