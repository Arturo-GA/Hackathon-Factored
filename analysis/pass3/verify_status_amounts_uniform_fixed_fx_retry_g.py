"""Verificacion (retry) status_amounts_uniform_fixed_fx. Parte G: utilidad del tope como validador de montos reclamados (cp.claimed)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
K = "(case currency when 'COP' then 4000 when 'ARS' then 350 when 'MXN' then 17 else 1 end)"
for r in con.execute(f"""select currency, count(*) n, count(claimed) n_claimed, round(min(claimed/{K}),2) mn_usd, round(median(claimed/{K}),2) med_usd, round(max(claimed/{K}),2) mx_usd,
  round(100.0*avg(case when claimed/{K} > 10000 then 1 else 0 end),2) pct_sobre_tope_global,
  round(100.0*avg(case when claimed/{K} > 500 then 1 else 0 end),2) pct_sobre_500
  from cp group by 1 order by 1""").fetchall(): print(r)
