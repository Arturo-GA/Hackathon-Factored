"""H17: 'Cargo no reconocido' (cp) — población completa. ¿Hay una tx del cliente en los 7/30 días previos más que en placebo?
¿el monto reclamado coincide con alguna tx del cliente (±1%, misma moneda)? ¿la tx coincidente es anterior y cercana?
Compara contra 'Cobro indebido' y 'Problema con app'."""
import duckdb, pandas as pd
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
T1 = "TIMESTAMP '2026-06-18 06:00:00'"
off = "to_days(CAST(60 + hash(complaint_id) % 340 AS INTEGER))"
con.execute(f"""CREATE TEMP TABLE e AS
  SELECT complaint_id, customer_id, ts, subcategory grp, claimed, currency, 'obs' kind FROM cp WHERE subcategory IN ('Cargo no reconocido','Cobro indebido','Problema con app')
  UNION ALL
  SELECT complaint_id, customer_id, CASE WHEN ts + {off} < {T1} THEN ts + {off} ELSE ts + {off} - INTERVAL 1096 DAY END, subcategory, claimed, currency, 'placebo'
  FROM cp WHERE subcategory IN ('Cargo no reconocido','Cobro indebido','Problema con app')""")
con.execute("CREATE TEMP TABLE t AS SELECT customer_id, ts, amount, currency, status, fraud, fscore FROM tx WHERE customer_id IN (SELECT DISTINCT customer_id FROM cp)")
print(con.execute("""SELECT grp, kind, count(*) n,
  avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e.customer_id AND t.ts BETWEEN e.ts - INTERVAL 7 DAY AND e.ts))::INT) b7d,
  avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e.customer_id AND t.ts BETWEEN e.ts - INTERVAL 30 DAY AND e.ts))::INT) b30d,
  avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e.customer_id AND t.ts BETWEEN e.ts - INTERVAL 30 DAY AND e.ts AND t.fraud))::INT) b30d_fraud,
  avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e.customer_id AND t.ts BETWEEN e.ts - INTERVAL 30 DAY AND e.ts AND t.fscore>=50))::INT) b30d_fs50
  FROM e GROUP BY ALL ORDER BY 1,2""").fetchdf().round(4).to_string(index=False))
print(con.execute("""SELECT grp, count(*) n, avg((claimed IS NOT NULL)::INT) has_claim,
  avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e.customer_id AND abs(t.amount - e.claimed) <= 0.01*e.claimed))::INT) any_match_1pct,
  avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e.customer_id AND round(t.amount,2) = round(e.claimed,2)))::INT) exact_match,
  avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e.customer_id AND t.ts < e.ts AND abs(t.amount - e.claimed) <= 0.01*e.claimed AND t.ts > e.ts - INTERVAL 60 DAY))::INT) match_prev60d
  FROM e WHERE kind='obs' GROUP BY 1""").fetchdf().round(4).to_string(index=False))
print(con.execute("SELECT currency, count(*) n, median(claimed) med, min(claimed), max(claimed) FROM cp WHERE subcategory='Cargo no reconocido' GROUP BY 1").fetchdf().to_string(index=False))
