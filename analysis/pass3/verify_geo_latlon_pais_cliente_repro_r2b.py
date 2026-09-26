# Verificacion independiente (ronda 2) del hallazgo geo_latlon_pais_cliente.
# Parte 2: tx foraneas, country_raw, city, branch_id y coordenadas de br.
import duckdb, numpy as np, pandas as pd
from scipy import stats

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    df = con.execute(s).df()
    print('==', t); print(df.to_string(), '\n')
    return df
def cramers_v(tab):
    tab = np.asarray(tab, dtype=float)
    chi2 = stats.chi2_contingency(tab, correction=False)[0]
    n = tab.sum(); k = min(tab.shape) - 1
    return np.sqrt(chi2 / (n * k)), chi2

CLAT = "case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.7110 when 'México' then 0.0 end"
CLON = "case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 when 'México' then 0.0 end"

# ---------- E. tx foraneas ----------
q('E1 foraneas: total, con coords, regla de casa', f"""select count(*) n_foraneas,
  count(t.lat) con_lat, count(*) filter (where t.lat is not null and t.lon is not null) con_ambas,
  sum((abs(t.lat-({CLAT}))<=1+1e-9)::int) lat_en_casa, sum((abs(t.lon-({CLON}))<=1+1e-9)::int) lon_en_casa
  from tx t join cu using(customer_id) where t.country<>cu.country""")
q('E2 tasa foranea por canal', """select t.channel, count(*) n, round(avg((t.country<>cu.country)::int),4) p_foranea
  from tx t join cu using(customer_id) group by 1 order by 1""")
q('E3 tasa foranea por ttype', """select t.ttype, count(*) n, round(avg((t.country<>cu.country)::int),4) p_foranea
  from tx t join cu using(customer_id) group by 1 order by 1""")

# ---------- F. country_raw ----------
pv = q('F1 country_raw x pais cliente', """pivot (select t.country_raw, cu.country cc from tx t join cu using(customer_id))
  on cc using count(*) group by country_raw order by country_raw""").set_index('country_raw')
tot = pv.sum()
print('F2 uniformidad de la rama "otro pais" por pais del cliente:')
for cc in pv.columns:
    own = {'Argentina': 'Argentina', 'Colombia': 'Colombia', 'México': 'México'}[cc]
    vals = pv[cc].drop(index=own).drop(index=[i for i in pv.index if pv.loc[i, cc] == 0], errors='ignore')
    chi = stats.chisquare(vals.values)
    print(f'  {cc}: n_tx={int(tot[cc])} valores={dict(vals.astype(int))} media={vals.mean():.0f} '
          f'min/max={vals.min()/vals.mean():.3f}/{vals.max()/vals.mean():.3f} chi2={chi.statistic:.1f} p={chi.pvalue:.3f} '
          f'p_por_valor={vals.mean()/tot[cc]:.5f} -> p_rama(6 valores)={6*vals.mean()/tot[cc]:.4f}')
print()
q('F3 country_raw por canal (rama otro-pais plana por canal?)', """select t.channel,
  round(avg((t.country_raw in ('USA','Spain','Brazil'))::int)/3,5) p_por_pais_extra,
  round(avg((t.country_raw='Mexico')::int),5) p_Mexico_sin_tilde, count(*) n
  from tx t join cu using(customer_id) group by 1 order by 1""")

# ---------- G. city ----------
q('G1 city: nulos y coincidencia con ciudad del cliente, por tipo de fila', """select cu.country cc,
  case when t.country<>cu.country then 'foranea' when t.country_raw='Mexico' then 'domestica_raw_Mexico' else 'domestica_raw_propio' end tipo,
  count(*) n, round(avg((t.city is null)::int),4) p_city_null,
  round(avg((t.city=cu.city)::int) filter (where t.city is not null),4) p_city_eq_cliente,
  count(distinct t.city) n_ciudades
  from tx t join cu using(customer_id) group by all order by 1,2""")
q('G2 domesticas con city no nula: city = ciudad cliente (global)', """select count(*) n, sum((t.city<>cu.city)::int) n_distinta,
  round(avg((t.city=cu.city)::int),4) p_igual from tx t join cu using(customer_id) where t.country=cu.country and t.city is not null""")
q('G3 ciudades en tx foraneas (top 12) y ciudades de raw Mexico', """select t.country_raw, t.country, t.city, count(*) n from tx t join cu using(customer_id)
  where t.country_raw in ('USA','Spain','Brazil','Mexico') group by all order by 1, 4 desc limit 30""")

# ---------- H. branch_id ----------
q('H1 cobertura del join branch_id -> br', """select t.channel, count(*) n_con_branch, count(b.branch_id) n_en_br
  from tx t left join br b on b.branch_id=t.branch_id where t.branch_id is not null group by 1 order by 1""")
q('H2 pais de la sucursal vs pais cliente / pais tx', """select (t.country<>cu.country) foranea, count(*) n,
  round(avg((b.country=cu.country)::int),5) br_en_pais_cliente, round(avg((b.country=t.country)::int),5) br_en_pais_tx
  from tx t join cu using(customer_id) join br b on b.branch_id=t.branch_id group by 1 order by 1""")
tab = con.execute("""select b.country, cu.city ccity, b.city bcity, count(*) n from tx t join cu using(customer_id) join br b on b.branch_id=t.branch_id
  group by all""").df()
print('H3 ciudad sucursal vs ciudad cliente (misma ciudad; V de Cramer):')
for c, g in tab.groupby('country'):
    ct = g.pivot_table(index='ccity', columns='bcity', values='n', aggfunc='sum', fill_value=0)
    same = sum(ct.loc[x, x] for x in ct.index if x in ct.columns) / ct.values.sum()
    pc = ct.sum(axis=1) / ct.values.sum(); pb = ct.sum(axis=0) / ct.values.sum()
    exp_ind = sum(pc[x] * pb[x] for x in pc.index if x in pb.index)
    v, chi2 = cramers_v(ct.values)
    print(f'  {c}: n={int(ct.values.sum())} misma_ciudad={same:.4f} esperado_indep={exp_ind:.4f} 1/K={1/ct.shape[1]:.4f} V={v:.4f}')
print()
q('H4 uso por sucursal dentro del pais (uniforme? indice de dispersion var/media ~1)', """with u as (select b.country, b.branch_id, b.branch_status, count(t.transaction_id) n
    from br b left join tx t on t.branch_id=b.branch_id group by all)
  select country, count(*) n_suc, sum((n>0)::int) n_usadas, round(avg(n),1) media, round(stddev(n),1) sd,
    round(var_samp(n)/avg(n),3) disp_idx, min(n) mn, max(n) mx,
    round(avg(n) filter (where branch_status<>'Active'),1) media_cerradas_temp
  from u group by 1 order by 1""")
q('H5 sucursal por tx: prob. de que 2 tx del mismo cliente compartan sucursal vs 1/B', """with cb as (select cu.country cc, t.customer_id, t.branch_id, count(*) n
     from tx t join cu using(customer_id) where t.branch_id is not null group by all),
  c as (select cc, customer_id, sum(n) n, sum(n*(n-1)) pares_mismo from cb group by all having sum(n)>=2),
  nb as (select country, count(*) B from br group by 1)
  select cc, count(*) n_clientes, round(sum(pares_mismo)/sum(n*(n-1)),5) p_mismo_par, round(1.0/any_value(nb.B),5) inv_B, any_value(nb.B) B
  from c join nb on nb.country=c.cc group by 1 order by 1""")
q('H6 sucursal abierta despues de la tx (fecha opened > ts)', """select count(*) n, round(avg((b.opened > t.ts::date)::int),4) p_sucursal_no_abierta_aun
  from tx t join br b on b.branch_id=t.branch_id""")
q('H7 distancia coords tx vs coords sucursal (misma tx)', f"""select cu.country cc, count(*) n,
  round(avg((abs(t.lat-b.lat)<=1 and abs(t.lon-b.lon)<=1)::int),4) p_tx_a_1grado_de_sucursal,
  round(avg((abs(b.lat)<=0.1 and abs(b.lon)<=0.1)::int),4) p_sucursal_en_00
  from tx t join cu using(customer_id) join br b on b.branch_id=t.branch_id where t.lat is not null and t.lon is not null group by 1 order by 1""")

# ---------- I. coordenadas de br ----------
q('I1 br cerca de (0,0)', """select count(*) n, sum((lat=0 and lon=0)::int) exacto_00,
  sum((abs(lat)<=0.1 and abs(lon)<=0.1)::int) dentro_01, round(max(abs(lat)) filter (where abs(lat)<1),4) max_abs_lat_cerca0,
  string_agg(distinct case when abs(lat)<1 and abs(lon)<1 then city end, ', ') ciudades from br""")
q('I2 por ciudad: todas o ninguna en (0,0)', """select country, city, count(*) n, sum((abs(lat)<1 and abs(lon)<1)::int) cerca00,
  round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(max(lat)-min(lat),3) rango_lat from br group by all order by 1,2""")
