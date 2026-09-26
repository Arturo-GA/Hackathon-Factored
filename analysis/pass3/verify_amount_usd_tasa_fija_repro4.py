# Verificacion independiente (reintento) - Parte C: tabla fx vs amount_usd
import duckdb, time
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title, f'[{time.time()-t0:.0f}s]'); print(con.execute(s).df().to_string(), '\n', flush=True)

q('C0 fx pares', """select src, dst, count(*) n, min(date) d0, max(date) d1, round(avg(rate),4) media, round(stddev(rate)/avg(rate)*100,3) cv_pct,
   round(min(rate),4) mn, round(max(rate),4) mx, count(distinct source) nsrc from fx group by 1,2 order by 1,2""")
q('C0b fx primer dia', """select date, src, dst, rate, buy, sell from fx where src='USD' and dst in ('ARS','COP') order by date limit 4""")
# autocorrelacion (paseo aleatorio vs ruido iid)
q('C0c fx autocorr', """with u as (select src,dst,date, rate, lag(rate) over (partition by src,dst order by date) pr from fx)
   select src,dst, round(corr(rate,pr),4) ac1 from u where src='USD' and dst in ('ARS','COP') group by 1,2""")

for c, K in [('ARS', 350.0), ('COP', 4000.0)]:
    base = f"(select cast(ts as date) d, process_date pd, amount, amount_usd, amount/amount_usd ratio from tx where currency='{c}' and amount_usd is not null)"
    for lab, dexpr in [('ts', 't.d'), ('process_date', 't.pd'), ('ts-1', 't.d - 1'), ('ts+1', 't.d + 1')]:
        q(f'C1 {c} fecha={lab}', f"""select count(*) n_join,
          round(corr(t.ratio, f.rate),5) corr_cociente_rate,
          round(100*median(abs(t.amount/f.rate/t.amount_usd - 1)),4) mre_usd2x_rate,
          round(100*median(abs(t.amount/f.buy /t.amount_usd - 1)),4) mre_usd2x_buy,
          round(100*median(abs(t.amount/f.sell/t.amount_usd - 1)),4) mre_usd2x_sell,
          round(100*median(abs(t.amount*g.rate/t.amount_usd - 1)),4) mre_x2usd_rate,
          round(100*median(abs(t.amount*g.buy /t.amount_usd - 1)),4) mre_x2usd_buy,
          round(100*median(abs(t.amount*g.sell/t.amount_usd - 1)),4) mre_x2usd_sell,
          round(100*avg((abs(round(t.amount/f.rate,2) - t.amount_usd) < 0.00001)::int),4) pct_exact_fx,
          round(100*median(abs(t.amount/{K}/t.amount_usd - 1)),6) mre_K
          from {base} t join fx f on f.date = {dexpr} and f.src='USD' and f.dst='{c}'
                        join fx g on g.date = {dexpr} and g.src='{c}' and g.dst='USD'""")
    # K vs promedio de fx en el periodo
    q(f'C2 {c} K vs fx promedio', f"""select round(100*median(abs(t.amount/(select avg(rate) from fx where src='USD' and dst='{c}')/t.amount_usd - 1)),4) mre_fx_media_global
          from {base} t""")
