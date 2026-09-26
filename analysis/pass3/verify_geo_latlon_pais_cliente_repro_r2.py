# Verificacion independiente (ronda 2) del hallazgo geo_latlon_pais_cliente.
# Parte 1: presencia de coordenadas, centro empirico (midrange) por pais del cliente,
# regla +-1 grado, uniformidad del ruido, independencia respecto de ciudad/cliente/tx.
import duckdb, numpy as np
from scipy import stats

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    df = con.execute(s).df()
    print('==', t); print(df.to_string(), '\n')
    return df

# ---------- A. presencia de coordenadas / branch_id por canal ----------
q('A1 presencia global', """select count(*) n, count(lat) n_lat, count(lon) n_lon,
  count(*) filter (where lat is not null and lon is not null) n_both,
  count(*) filter (where lat is not null and lon is null) n_lat_only,
  count(*) filter (where lat is null and lon is not null) n_lon_only,
  round(1 - (count(*) filter (where lat is not null and lon is not null))::double / count(lat), 4) p_lonnull_given_lat,
  round(1 - (count(*) filter (where lat is not null and lon is not null))::double / count(lon), 4) p_latnull_given_lon
  from tx""")
q('A2 por canal', """select channel, count(*) n, round(avg((lat is not null)::int),4) p_lat, round(avg((lon is not null)::int),4) p_lon,
  round(avg((lat is not null and lon is not null)::int),4) p_both, round(avg((branch_id is not null)::int),4) p_branch,
  round(avg((merchant_name is not null)::int),4) p_merchant
  from tx group by 1 order by 1""")
q('A3 p_lat en POS/ATM/Branch por ttype (plano?)', """select channel, ttype, count(*) n, round(avg((lat is not null)::int),4) p_lat
  from tx where channel in ('POS','ATM','Branch') group by all order by 1,2""")
q('A4 p_lat por status y fraude (canales geo)', """select status, fraud, count(*) n, round(avg((lat is not null)::int),4) p_lat
  from tx where channel in ('POS','ATM','Branch') group by all order by 1,2""")

# ---------- B. centro empirico por pais del cliente ----------
B = q('B1 rangos lat/lon por pais del cliente (filas con la coordenada)', """select cu.country cc,
  count(t.lat) n_lat, min(t.lat) lat_min, max(t.lat) lat_max, (min(t.lat)+max(t.lat))/2 lat_mid, avg(t.lat) lat_mean, stddev(t.lat) lat_sd,
  count(t.lon) n_lon, min(t.lon) lon_min, max(t.lon) lon_max, (min(t.lon)+max(t.lon))/2 lon_mid, avg(t.lon) lon_mean, stddev(t.lon) lon_sd
  from tx t join cu using(customer_id) where t.lat is not null or t.lon is not null group by 1 order by 1""")

CLAT = "case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.7110 when 'México' then 0.0 end"
CLON = "case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 when 'México' then 0.0 end"
V = f"""(select t.transaction_id, t.customer_id, t.channel, t.ttype, t.status, t.fraud, t.country tcountry, t.city tcity, t.country_raw,
   cu.country cc, cu.city ccity, t.lat, t.lon, t.lat - ({CLAT}) dlat, t.lon - ({CLON}) dlon
   from tx t join cu using(customer_id) where t.lat is not null or t.lon is not null)"""
EPS = 1e-9
q('B2 regla |lat-c|<=1 y |lon-c|<=1 (filas con ambas) por pais cliente', f"""select cc, count(*) n_both,
  sum((abs(dlat)<=1+{EPS} and abs(dlon)<=1+{EPS})::int) ok, round(avg((abs(dlat)<=1+{EPS} and abs(dlon)<=1+{EPS})::int),6) p_ok,
  round(min(dlat),5) mn_dlat, round(max(dlat),5) mx_dlat, round(min(dlon),5) mn_dlon, round(max(dlon),5) mx_dlon
  from {V} where lat is not null and lon is not null group by rollup(cc) order by 1""")
q('B3 regla en filas con una sola coordenada', f"""select cc,
  count(*) filter (where lon is null) n_lat_only, avg((abs(dlat)<=1+{EPS})::int) filter (where lon is null) ok_lat_only,
  count(*) filter (where lat is null) n_lon_only, avg((abs(dlon)<=1+{EPS})::int) filter (where lat is null) ok_lon_only
  from {V} group by 1 order by 1""")
q('B4 regla alternativa: centro del pais de la TX (solo tx en AR/CO/MX)', f"""select (tcountry<>cc) foranea, count(*) n,
  round(avg((abs(lat - case tcountry when 'Argentina' then -34.6037 when 'Colombia' then 4.711 when 'México' then 0 end)<=1+{EPS})::int),4) ok_centro_pais_tx,
  round(avg((abs(dlat)<=1+{EPS})::int),4) ok_centro_pais_cliente
  from {V} where lat is not null and tcountry in ('Argentina','Colombia','México') group by 1 order by 1""")

# ---------- C. independencia del desvio respecto de ciudad, canal, cliente ----------
q('C1 desvio medio por ciudad del CLIENTE (si el centro fuera la ciudad, se veria aqui)', f"""select cc, ccity, count(*) n, round(avg(dlat),4) m_dlat, round(avg(dlon),4) m_dlon
  from {V} where lat is not null and lon is not null group by all order by 1,2""")
q('C2 desvio medio por ciudad de la TX (top 20 por n)', f"""select cc, tcountry, tcity, count(*) n, round(avg(dlat),4) m_dlat, round(avg(dlon),4) m_dlon
  from {V} where lat is not null and lon is not null group by all order by n desc limit 20""")
q('C3 desvio medio por canal / foranea', f"""select channel, (tcountry<>cc) foranea, count(*) n, round(avg(dlat),4) m_dlat, round(stddev(dlat),4) sd_dlat, round(avg(dlon),4) m_dlon
  from {V} where lat is not null and lon is not null group by all order by 1,2""")
q('C4 efecto cliente: F aprox = mean(n_i*(m_i-m)^2)/s2 (=1 bajo H0) y sd intra-cliente', f"""with g as (select avg(dlat) m, var_samp(dlat) s2 from {V} where lat is not null),
  c as (select customer_id, count(*) n, avg(dlat) mi, stddev(dlat) si from {V} where lat is not null group by 1 having count(*)>=5)
  select count(*) n_cust, round(avg(n),2) n_medio, round(avg(si),4) sd_intra_medio, round(sqrt(any_value(g.s2)),4) sd_global,
    round(avg(n*(mi-g.m)*(mi-g.m))/any_value(g.s2),4) F_aprox from c, g""")

# ---------- D. forma del ruido: uniforme(-1,1)? ----------
q('D1 10 bins de dlat y dlon (filas con la coordenada)', f"""select b, sum(nlat) n_dlat, sum(nlon) n_dlon from (
  select least(floor((dlat+1)*5),9)::int b, 1 nlat, 0 nlon from {V} where lat is not null
  union all select least(floor((dlon+1)*5),9)::int b, 0, 1 from {V} where lon is not null) group by 1 order by 1""")
m = q('D2 momentos', f"""select round(stddev(dlat),5) sd_dlat, round(stddev(dlon),5) sd_dlon, round(1/sqrt(3),5) sd_teorica,
  round(kurtosis(dlat),4) exkurt_dlat, round(kurtosis(dlon),4) exkurt_dlon, round(corr(dlat,dlon),5) corr_dlat_dlon,
  round(avg(dlat),5) m_dlat, round(avg(dlon),5) m_dlon from {V} where lat is not null and lon is not null""")
bins = con.execute(f"""select least(floor((dlat+1)*50),99)::int b, count(*) n from {V} where lat is not null group by 1 order by 1""").df()
chi = stats.chisquare(bins['n'].values)
print('D3 chi2 100 bins dlat: chi2=%.1f p=%.3f (k=%d, n=%d)' % (chi.statistic, chi.pvalue, len(bins), bins['n'].sum()))
bins = con.execute(f"""select least(floor((dlon+1)*50),99)::int b, count(*) n from {V} where lon is not null group by 1 order by 1""").df()
chi = stats.chisquare(bins['n'].values)
print('D3 chi2 100 bins dlon: chi2=%.1f p=%.3f (k=%d, n=%d)' % (chi.statistic, chi.pvalue, len(bins), bins['n'].sum()))
s = con.execute(f"""select dlat, dlon, cc from (select * from {V} where lat is not null and lon is not null) using sample reservoir(150000 rows) repeatable (7)""").df()
for c in ['dlat', 'dlon']:
    ks = stats.kstest(s[c].values, stats.uniform(loc=-1, scale=2).cdf)
    print('D4 KS %s vs U(-1,1): D=%.5f p=%.3f n=%d' % (c, ks.statistic, ks.pvalue, len(s)))
for cc, g in s.groupby('cc'):
    ks = stats.kstest(g['dlat'].values, stats.uniform(loc=-1, scale=2).cdf)
    print('   KS dlat %s: D=%.5f p=%.3f n=%d' % (cc, ks.statistic, ks.pvalue, len(g)))
q('D5 decimales de lat (resolucion)', """select round(avg((round(lat,4)=lat)::int),4) p_4dec, round(avg((round(lat,6)=lat)::int),4) p_6dec,
  count(distinct lat) n_distinct, count(lat) n from tx where lat is not null""")
