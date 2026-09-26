# Verificacion independiente (reintento) - Parte E: moneda por pais/producto; Parte F: desempates con round() de Python
import duckdb, time
from decimal import Decimal
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title, f'[{time.time()-t0:.0f}s]'); print(con.execute(s).df().to_string(), '\n', flush=True)

q('E1 productos: pais del cliente x moneda', """select cu.country, pr.currency, count(*) n,
   round(100.0*count(*)/sum(count(*)) over (partition by cu.country),2) pct
   from pr join cu using(customer_id) group by 1,2 order by 1,2""")
q('E1b productos sin cliente', "select count(*) from pr anti join cu using(customer_id)")
q('E2 tx: pais del cliente x moneda', """select cu.country, tx.currency, count(*) n,
   round(100.0*count(*)/sum(count(*)) over (partition by cu.country),2) pct
   from tx join cu using(customer_id) group by 1,2 order by 1,2""")
q('E3 tx.currency = pr.currency', """select count(*) n, sum((tx.currency = pr.currency)::int) iguales,
   sum((pr.product_id is null)::int) sin_producto from tx left join pr using(product_id)""")
q('E4 productos con >1 moneda en tx', "select count(*) from (select product_id from tx group by 1 having count(distinct currency)>1)")
q('E5 clientes AR/CO con productos en ambas monedas', """select cu.country, count(*) n_clientes,
   sum((nloc>0 and nusd>0)::int) ambas, sum((nloc=0)::int) solo_usd
   from (select customer_id, sum((currency<>'USD')::int) nloc, sum((currency='USD')::int) nusd from pr group by 1) p
   join cu using(customer_id) where cu.country in ('Argentina','Colombia') group by 1""")

# F. desempates: amount_usd reproduce round(amount/K, 2) de Python (float) al 100%?
df = con.execute("""select currency, amount, amount_usd from tx where amount_usd is not null and currency in ('ARS','COP')
   and (cast(round(amount*100) as bigint) % (case currency when 'ARS' then 350 else 4000 end)) = (case currency when 'ARS' then 175 else 2000 end)""").df()
K = {'ARS': 350.0, 'COP': 4000.0}
df['py_round'] = [round(a / K[c], 2) for a, c in zip(df.amount, df.currency)]
df['ok_py'] = (df.py_round - df.amount_usd).abs() < 1e-9
# direccion "real" de la division en coma flotante respecto del empate exacto
df['float_above_tie'] = [Decimal(a / K[c]) > (Decimal(round(a * 100)) / Decimal(int(K[c]))) / 100 for a, c in zip(df.amount, df.currency)]
df['up'] = [ (u*100 - int(round(a*100))/K[c]) > 0 for a, u, c in zip(df.amount, df.amount_usd, df.currency)]
print('== F1 empates exactos: coincidencia con round() de Python')
print(df.groupby('currency').agg(n=('ok_py','size'), coincide_py=('ok_py','mean'), float_sobre_empate=('float_above_tie','mean'), dataset_arriba=('up','mean')).to_string(), '\n')
print(pd.crosstab([df.currency, df.float_above_tie], df.up).to_string() if False else '', flush=True)
import pandas as pd
print(pd.crosstab([df.currency, df.float_above_tie], df.up).to_string())

# F2. muestra aleatoria general (300k) con round() de Python
s = con.execute("select currency, amount, amount_usd from tx where amount_usd is not null and currency in ('ARS','COP') using sample 300000 rows").df()
s['ok_py'] = [abs(round(a / K[c], 2) - u) < 1e-9 for a, u, c in zip(s.amount, s.amount_usd, s.currency)]
print('\n== F2 muestra 300k: coincidencia exacta con round(amount/K,2) de Python')
print(s.groupby('currency').ok_py.agg(['size','mean']).to_string())
