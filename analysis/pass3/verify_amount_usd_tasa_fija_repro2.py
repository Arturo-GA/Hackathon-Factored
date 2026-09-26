# Verificacion independiente (reintento) del hallazgo amount_usd_tasa_fija
# Parte A: esquema, nulos por moneda, cociente amount/amount_usd, regla exacta, desempates
import duckdb, time
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title, f'[{time.time()-t0:.0f}s]'); print(con.execute(s).df().to_string(), '\n', flush=True)

q('tipos', "select column_name, data_type from information_schema.columns where table_name='tx' and column_name in ('amount','amount_usd','currency','ts','process_date','fraud','fscore')")
q('fx tipos', "select column_name, data_type from information_schema.columns where table_name='fx'")

# A1. nulos por moneda
q('A1 nulos por moneda', """select currency, count(*) n, count(amount_usd) n_notnull, count(*)-count(amount_usd) n_null,
   round(100.0*(count(*)-count(amount_usd))/count(*),3) pct_null from tx group by 1 order by 1""")
q('A1b nulos global', "select count(*) n, count(*)-count(amount_usd) n_null, round(100.0*(count(*)-count(amount_usd))/count(*),3) pct_null from tx")

# A2. decimales de amount y amount_usd, signo, ceros
q('A2 decimales/signo', """select currency, min(amount) mn, max(amount) mx,
   avg((abs(amount*100 - round(amount*100))<1e-6)::int) amt_2dec,
   avg((abs(amount_usd*100 - round(amount_usd*100))<1e-6)::int) usd_2dec,
   sum((amount<0)::int) n_neg, sum((amount_usd=0)::int) n_usd_cero, min(amount_usd) mn_usd, max(amount_usd) mx_usd
   from tx group by 1 order by 1""")
