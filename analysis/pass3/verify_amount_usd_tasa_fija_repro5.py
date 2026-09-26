# Verificacion independiente (reintento) - Parte D: nulos de amount_usd en ARS/COP (MCAR?)
import duckdb, time
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title, f'[{time.time()-t0:.0f}s]'); print(con.execute(s).df().to_string(), '\n', flush=True)

LOC = "(select *, (amount_usd is null)::int nul from tx where currency in ('ARS','COP'))"
groups = [('fraud', 'fraud::varchar'), ('fscore_nulo', '(fscore is null)::varchar'), ('lat_nula', '(lat is null)::varchar'),
          ('merchant_nulo', '(merchant_name is null)::varchar'), ('status', 'status'), ('code', "coalesce(code,'NULL')"),
          ('channel', 'channel'), ('ttype', 'ttype'), ('moneda', 'currency'), ('pais_tx', 'coalesce(country,\'NULL\')'),
          ('anio', 'year(ts)::varchar'), ('dia_semana', 'dayofweek(ts)::varchar'), ('hora_bloque', '(hour(ts)//6)::varchar'),
          ('decil_monto', "least(9, floor((amount/(case currency when 'ARS' then 350 else 4000 end) - 5)/999.5))::int::varchar")]
rows = []
for lab, g in groups:
    df = con.execute(f"select {g} g, count(*) n, avg(nul) p from {LOC} group by 1 order by 1").df()
    df = df[df.n >= 500]
    rows.append((lab, len(df), int(df.n.min()), round(100*df.p.min(),2), round(100*df.p.max(),2), round(df.p.max()/df.p.min(),3)))
    if lab in ('fraud','status','channel','fscore_nulo'):
        print(lab, df.assign(pct=lambda d: (100*d.p).round(2)).drop(columns='p').to_string(index=False))
import pandas as pd
print('\n== D1 tasa de nulos (ARS/COP) por grupo: min/max y razon de tasas (grupos con n>=500)')
print(pd.DataFrame(rows, columns=['variable','n_grupos','n_min','pct_min','pct_max','razon_max_min']).to_string(index=False), '\n', flush=True)

q('D2 nulos globales (incl. USD) por trimestre', """select year(ts) y, quarter(ts) qq, count(*) n, round(100*avg((amount_usd is null)::int),2) pct_null
   from tx group by 1,2 order by 1,2""")
q('D2b rango', """select min(p) mn, max(p) mx from (select round(100*avg((amount_usd is null)::int),2) p, count(*) n from tx group by year(ts), quarter(ts) having count(*)>100000)""")

# D3. sobredispersion por cliente y por producto (test de dispersion binomial)
for unit in ['customer_id', 'product_id']:
    q(f'D3 dispersion por {unit}', f"""with p as (select avg(nul) p from {LOC}),
       c as (select {unit}, count(*) n, sum(nul) x from {LOC} group by 1)
       select count(*) n_unidades, round(avg(n),1) n_medio,
         round(var_pop(x*1.0/n) filter (where n>=5), 6) var_obs_n5, round(avg(p.p*(1-p.p)/n) filter (where n>=5), 6) var_esp_n5,
         round(sum(power(x - n*p.p,2)/(n*p.p*(1-p.p))) / (count(*)-1), 4) indice_dispersion,
         sum((x=0)::int) n_sin_nulos, round(sum(power(1-p.p, n)),0) esperado_sin_nulos,
         sum((x=n)::int) n_todo_nulo
       from c, p""")
q('D4 fraude x moneda', f"select currency, fraud, count(*) n, round(100*avg(nul),2) pct_null from {LOC} group by 1,2 order by 1,2")
