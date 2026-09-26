"""H21: tiempos encuesta vs interacción: ¿sv.ts = cc.ts + resp_hours? ¿o se ancla a otra referencia (process_date+8h)?"""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("""SELECT count(*) n,
  quantile_cont(date_diff('second', c.ts, s.ts)/3600.0 - s.resp_hours, [0.01,0.25,0.5,0.75,0.99]) q_diff_vs_cc,
  quantile_cont(date_diff('second', c.ts + INTERVAL (c.dur) SECOND, s.ts)/3600.0 - s.resp_hours, [0.01,0.5,0.99]) q_diff_vs_cc_end,
  quantile_cont(s.resp_hours, [0,0.5,1]) q_resp, quantile_cont(date_diff('second', c.ts, s.ts)/3600.0, [0,0.5,1]) q_gap
  FROM sv s JOIN cc c USING(interaction_id) WHERE c.dur IS NOT NULL""").fetchdf().T.to_string())
