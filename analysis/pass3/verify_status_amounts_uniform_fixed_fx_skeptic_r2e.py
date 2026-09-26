# Verificador escéptico r2e: los desajustes con round() de DuckDB, ¿son empates de medio centavo?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("""with t as (select currency, amount, amount_usd, amount/(case currency when 'COP' then 4000.0 else 350.0 end) raw
   from tx where amount_usd is not null)
   select currency, count(*) desajustes,
     sum((abs(abs(amount_usd - raw) - 0.005) < 1e-6)::int) empates_medio_centavo,
     sum((abs(amount_usd*100 - round(amount_usd*100)) < 1e-9 and ((amount_usd*100)::bigint % 2 = 0))::int) redondeo_a_par
   from t where abs(amount_usd - round(raw,2)) > 1e-9 group by 1""").df().to_string())
