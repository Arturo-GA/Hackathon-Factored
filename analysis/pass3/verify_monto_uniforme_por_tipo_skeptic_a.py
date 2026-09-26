# Verificador escéptico: monto_uniforme_por_tipo. Parte A: límites exactos, granularidad y uniformidad fina (datos completos)
import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
K="(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
LO="(case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)"
HI="(case ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Transfer' then 10000 when 'Payment' then 2000 when 'Deposit' then 5000 else 1000 end)"
print('== valores de tcat / mcat (top) ==')
q("select ttype, tcat, count(*) n from tx group by all order by 1, n desc limit 40")
q("select count(distinct mcat) n_mcat, count(distinct merchant_name) n_merch, count(distinct city) n_city, count(distinct branch_id) n_br, avg((amount is null)::int) amt_null, min(amount) mn_amt from tx")
print('== limites exactos por ttype x moneda (a = amount/K) ==')
q(f"""select ttype, currency, count(*) n, min(amount/{K}) mn, max(amount/{K}) mx, {LO} lo, {HI} hi,
 sum((amount/{K} < {LO})::int) below_lo, sum((amount/{K} > {HI})::int) above_hi,
 sum((amount/{K} < {LO}-0.01)::int) below_lo_tol, sum((amount/{K} > {HI}+0.01)::int) above_hi_tol
 from tx group by all order by 1,2""")
print('== granularidad: decimales del monto ==')
q(f"""select currency, count(*) n,
 avg((abs(amount*100-round(amount*100))<1e-6)::int) max2dec,
 avg((abs(amount-round(amount))<1e-9)::int) entero,
 avg((abs((amount/{K})*100-round((amount/{K})*100))<1e-6)::int) usd_2dec,
 avg((abs(amount/40-round(amount/40))<1e-9)::int) mult40,
 avg((abs(amount/3.5-round(amount/3.5))<1e-9)::int) mult3_5
 from tx group by 1""")
