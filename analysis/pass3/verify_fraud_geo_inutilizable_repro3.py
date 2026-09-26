"""Verificación independiente de 'fraud_geo_inutilizable' (parte 3: distancia tx-sucursal y fraude)."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    d = con.execute(s).df(); print('==', t); print(d.to_string(index=False), '\n'); return d

q('sucursales: coords por país', """
select country, count(*) n, count(lat) n_lat, round(avg(lat),2) mlat, round(stddev(lat),2) sdlat, round(min(lat),2) minlat, round(max(lat),2) maxlat,
  round(avg(lon),2) mlon, round(min(lon),2) minlon, round(max(lon),2) maxlon, count(distinct city) ncity
from br group by 1 order by 2 desc""")

q('tx con branch_id: país sucursal vs país tx vs país cliente', """
select round(100*avg((b.country=t.country)::int),2) pct_br_eq_txc, round(100*avg((b.country=cu.country)::int),2) pct_br_eq_cc,
  round(100*avg((b.city=t.city)::int),2) pct_br_city_eq_txcity, count(*) n, count(b.branch_id) n_join
from tx t left join br b using(branch_id) join cu using(customer_id) where t.branch_id is not null""")

# haversine distance
HAV = "2*6371*asin(sqrt(pow(sin(radians(b.lat-t.lat)/2),2)+cos(radians(t.lat))*cos(radians(b.lat))*pow(sin(radians(b.lon-t.lon)/2),2)))"
con.execute(f"""create temp table d as
select t.transaction_id, t.customer_id, t.fraud, t.fscore, t.channel, t.country tc, cu.country cc, b.country bc, {HAV} km
from tx t join br b using(branch_id) join cu using(customer_id)
where t.lat is not null and t.lon is not null and b.lat is not null and b.lon is not null""")

q('distancia tx-sucursal: % >50 km (legítimas y fraude)', """
select fraud, count(*) n, round(100*avg((km>50)::int),2) pct_gt50, round(100*avg((km>100)::int),2) pct_gt100,
  round(median(km),0) med_km, round(quantile_cont(km,0.05),0) p05, round(quantile_cont(km,0.95),0) p95
from d group by 1 order by 1""")

q('distancia por país cliente (legítimas) y fraude', """
select cc, fraud, count(*) n, round(100*avg((km>50)::int),2) pct_gt50, round(median(km),0) med_km, round(avg(km),0) mean_km
from d group by all order by 1,2""")

base = con.execute("select avg(fraud::int) from tx").fetchone()[0]
base_d = con.execute("select avg(fraud::int) from d").fetchone()[0]
print('tasa base fraude global', base, ' en subconjunto con distancia', base_d, '\n')
r = q('fraude por tramo de distancia (mismos cortes del original)', """
select case when km<100 then 'a<100' when km<500 then 'b<500' when km<1000 then 'c<1000' when km<3000 then 'd<3000' when km<6000 then 'e<6000' else 'f>=6000' end bin,
  count(*) n, sum(fraud::int) f from d group by 1 order by 1""")
r['rate_pm'] = 1e3*r.f/r.n; r['rr_vs_global'] = (r.f/r.n)/base; r['rr_vs_subset'] = (r.f/r.n)/base_d
# 95% CI for rate ratio vs rest (log method)
tot_n, tot_f = r.n.sum(), r.f.sum()
lo, hi = [], []
for _, x in r.iterrows():
    n1, f1 = x.n, x.f; n0, f0 = tot_n-n1, tot_f-f1
    rr = (f1/n1)/(f0/n0); se = np.sqrt(1/f1 - 1/n1 + 1/f0 - 1/n0)
    lo.append(rr*np.exp(-1.96*se)); hi.append(rr*np.exp(1.96*se))
r['rr_vs_rest_lo'] = lo; r['rr_vs_rest_hi'] = hi
print(r.round(3).to_string(index=False), '\n')

r2 = q('fraude por tramo de distancia DENTRO de cada país cliente', """
select cc, case when km<50 then 'a<50' when km<100 then 'b<100' when km<200 then 'c<200' when km<500 then 'd<500' else 'e>=500' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from d group by all order by 1,2""")

# the "bimodal mixture": median by fraud within cc
q('mediana km por fraude dentro de país cliente', """
select cc, fraud, count(*) n, round(median(km),1) med_km from d group by all order by 1,2""")
q('mezcla: % de cada país cliente entre legítimas vs fraude', """
select fraud, round(100*avg((cc='México')::int),2) pct_mx, round(100*avg((cc='Colombia')::int),2) pct_co, round(100*avg((cc='Argentina')::int),2) pct_ar, count(*) n
from d group by 1""")
