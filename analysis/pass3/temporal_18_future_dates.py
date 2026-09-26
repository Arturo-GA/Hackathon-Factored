"""H23: fechas en el futuro respecto al fin de datos (2026-06-18 06:00) y orden de fechas de ciclo de vida."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2")
END = "TIMESTAMP '2026-06-18 06:00:00'"
print(con.execute(f"""SELECT count(*) n, avg((last_updated > {END})::INT) pr_lastupd_future, avg((last_tx > last_updated)::INT) lasttx_after_lastupd,
  avg((opened > last_updated)::INT) opened_after_lastupd, avg((last_tx < opened)::INT) lasttx_before_opened, avg((expires < opened)::INT) exp_before_open,
  quantile_cont(date_diff('day', opened, expires)/365.25, [0.0,0.5,1.0]) life_years FROM pr""").fetchdf().T.to_string())
print(con.execute(f"""SELECT count(*) n, avg((last_updated > {END})::INT) cu_lastupd_future, avg((last_updated < registration_date)::INT) lastupd_before_reg,
   quantile_cont(date_diff('day', registration_date, last_updated), [0.0, 0.5, 1.0]) d FROM cu""").fetchdf().T.to_string())
print(con.execute("""SELECT pstatus, avg((expires < TIMESTAMP '2026-06-17')::INT) expired_by_end, count(*) n FROM pr GROUP BY 1""").fetchdf().to_string(index=False))
