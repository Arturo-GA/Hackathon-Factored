# Verificacion independiente (reintento) - Parte B: cociente, regla exacta con aritmetica entera, estabilidad temporal
import duckdb, time
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title, f'[{time.time()-t0:.0f}s]'); print(con.execute(s).df().to_string(), '\n', flush=True)

V = """(select currency, ts, amount, amount_usd,
          case currency when 'ARS' then 350 when 'COP' then 4000 end as K,
          cast(round(amount*100) as bigint) c_loc, cast(round(amount_usd*100) as bigint) c_usd
        from tx where amount_usd is not null and currency in ('ARS','COP'))"""

# B1. cociente amount/amount_usd
q('B1 cociente', f"""select currency, count(*) n, median(amount/amount_usd) med, avg(amount/amount_usd) media,
   stddev(amount/amount_usd) sd, min(amount/amount_usd) mn, max(amount/amount_usd) mx,
   quantile_cont(amount/amount_usd, 0.01) p01, quantile_cont(amount/amount_usd, 0.99) p99
   from {V} group by 1 order by 1""")

# B2. regla exacta: amount_usd == round(amount/K, 2) (float) y en aritmetica entera
#   d = c_usd*K - c_loc (entero en centavos de moneda local); |d|<=K/2 <=> redondeo correcto; |d|=K/2 => empate
q('B2 regla exacta', f"""select currency, count(*) n,
   sum((amount_usd = round(amount/K, 2))::int) n_exact_float,
   round(100.0*avg((amount_usd = round(amount/K, 2))::int), 4) pct_exact_float,
   round(100.0*avg((abs(c_usd*K - c_loc) < K/2.0)::int), 4) pct_estricto,
   sum((abs(c_usd*K - c_loc) = K/2.0)::int) n_empate_exacto,
   sum((abs(c_usd*K - c_loc) > K/2.0)::int) n_fuera_medio_centavo,
   max(abs(amount_usd - amount/K)) maxdiff
   from {V} group by 1 order by 1""")

# B3. las no exactas: son empates? y como se resuelven los empates
q('B3 no exactas', f"""select currency, count(*) n_noexact,
   sum((abs(c_usd*K - c_loc) = K/2.0)::int) de_ellas_empate,
   min(amount_usd - round(amount/K,2)) mn, max(amount_usd - round(amount/K,2)) mx
   from {V} where amount_usd <> round(amount/K,2) group by 1 order by 1""")
q('B4 empates: resolucion', f"""select currency, count(*) n_empates,
   sum((c_usd*K - c_loc > 0)::int) hacia_arriba, sum((c_usd*K - c_loc < 0)::int) hacia_abajo,
   sum((c_usd*K - c_loc > 0 and c_usd % 2 = 0)::int) arriba_a_par, sum((c_usd*K - c_loc < 0 and c_usd % 2 = 0)::int) abajo_a_par
   from {V} where (c_loc % K) = K/2 group by 1 order by 1""")

# B5. distribucion del error de redondeo (debe ser ~uniforme en [-0.005,0.005])
q('B5 error redondeo', f"""select currency, 
   round(100.0*avg((amount_usd - amount/K between -0.005 and -0.0025)::int),2) q1,
   round(100.0*avg((amount_usd - amount/K between -0.0025 and 0)::int),2) q2,
   round(100.0*avg((amount_usd - amount/K between 0 and 0.0025)::int),2) q3,
   round(100.0*avg((amount_usd - amount/K between 0.0025 and 0.005)::int),2) q4
   from {V} group by 1 order by 1""")

# B6. estabilidad temporal del K (por anio-trimestre): mediana y sd del cociente; y K fuera de rango
q('B6 cociente por trimestre', f"""select currency, year(ts) y, quarter(ts) qq, count(*) n,
   round(median(amount/amount_usd),4) med, round(avg(amount/amount_usd),4) media, round(stddev(amount/amount_usd),4) sd,
   round(100.0*avg((abs(c_usd*K - c_loc) <= K/2.0)::int),3) pct_regla
   from {V} group by all order by 1,2,3""")
