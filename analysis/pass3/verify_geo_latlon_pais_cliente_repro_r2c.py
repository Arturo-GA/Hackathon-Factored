# Verificacion independiente (ronda 2) del hallazgo geo_latlon_pais_cliente.
# Parte 3: la rama "otro pais" excluye el pais propio por texto exacto? (AR/CO vs MX),
# origen de los desajustes de ciudad, listas de ciudades internacionales, fechas de apertura de br.
import duckdb
from scipy import stats

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    df = con.execute(s).df()
    print('==', t); print(df.to_string(), '\n')
    return df

d = q('J1 tasa foranea y tasa de la rama internacional por pais del cliente', """select cu.country cc, count(*) n,
  sum((t.country<>cu.country)::int) n_foranea, round(avg((t.country<>cu.country)::int),5) p_foranea,
  sum((t.country_raw in ('USA','Spain','Brazil'))::int) n_usa_esp_bra,
  round(avg((t.country_raw in ('USA','Spain','Brazil'))::int)/3,5) p_por_valor,
  sum((t.country_raw='Mexico' and cu.country='México')::int) n_propio_visible
  from tx t join cu using(customer_id) group by 1 order by 1""")
# test: razon de p_por_valor AR/CO vs MX (6/5 = 1.2 si AR/CO excluyen el propio y MX no)
mx = d.set_index('cc').loc['México'];
for cc in ['Argentina', 'Colombia']:
    r = d.set_index('cc').loc[cc]
    print(f'J2 razon p_por_valor {cc}/México = {r.p_por_valor/mx.p_por_valor:.3f} (6/5=1.200); '
          f'razon p_foranea = {r.p_foranea/mx.p_foranea:.3f}')
    # prueba de proporciones: por valor, AR/CO vs MX
    tab = [[int(r.n_usa_esp_bra), int(r.n) * 3 - int(r.n_usa_esp_bra)], [int(mx.n_usa_esp_bra), int(mx.n) * 3 - int(mx.n_usa_esp_bra)]]
    print('    chi2 p =', stats.chi2_contingency(tab)[1])
print()
q('J3 desajustes ciudad tx vs ciudad cliente en filas domesticas, por pais cliente y raw', """select cu.country cc, t.country_raw, count(*) n_city_no_nula,
  sum((t.city<>cu.city)::int) n_distinta from tx t join cu using(customer_id)
  where t.country=cu.country and t.city is not null group by all order by 1,2""")
q('J4 ciudades usadas en la rama internacional por pais de destino', """select t.country_raw, string_agg(distinct t.city, ', ' order by t.city) ciudades, count(distinct t.city) k
  from tx t join cu using(customer_id) where t.country<>cu.country or t.country_raw='Mexico' group by 1 order by 1""")
q('J5 filas AR/CO domesticas con ciudad fuera de la ciudad del cliente pero en la lista internacional', """select cu.country cc, count(*) n
  from tx t join cu using(customer_id) where t.country=cu.country and t.city is not null and t.city<>cu.city and cu.country<>'México' group by 1""")
q('J6 fechas de apertura de br vs ventana de tx', """select min(opened) min_opened, max(opened) max_opened,
  (select min(ts) from tx) min_ts, (select max(ts) from tx) max_ts, sum((opened > date '2023-06-17')::int) n_abiertas_en_ventana from br""")
q('J7 modelo 30% x (1-5%) de nulos: p_any/p_lat/p_both en canales geo', """select count(*) n,
  round(avg((lat is not null or lon is not null)::int),4) p_any, round(avg((lat is not null)::int),4) p_lat,
  round(avg((lat is not null and lon is not null)::int),4) p_both,
  round(avg((lat is not null)::int)/avg((lat is not null or lon is not null)::int),4) p_lat_dado_any
  from tx where channel in ('POS','ATM','Branch')""")
