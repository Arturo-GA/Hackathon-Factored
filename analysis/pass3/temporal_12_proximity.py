"""H16: ¿los contactos (cc), reclamos (cp) y eventos digitales (de) ocurren cerca en el tiempo de las tx del mismo cliente?
Compara observado vs placebo (mismo evento con ts desplazado +k días, k determinista 60-400, envuelto en la ventana).
Métrica: % de eventos con >=1 tx del cliente en ventana [-W, 0] antes y [0, +W] después; W=1h, 24h, 7d."""
import duckdb, pandas as pd
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
T0, T1 = "TIMESTAMP '2023-06-17 06:00:00'", "TIMESTAMP '2026-06-18 06:00:00'"
con.execute("CREATE TEMP TABLE cust AS SELECT customer_id FROM cu WHERE hash(customer_id) % 10 = 0")
con.execute("CREATE TEMP TABLE t AS SELECT customer_id, product_id, ts, ttype, status, amount, channel FROM tx WHERE customer_id IN (SELECT customer_id FROM cust)")
def placebo(col):
    return f"""CASE WHEN {col} + to_days(CAST(60 + hash(ev_id) % 340 AS INTEGER)) < {T1} THEN {col} + to_days(CAST(60 + hash(ev_id) % 340 AS INTEGER))
                  ELSE {col} + to_days(CAST(60 + hash(ev_id) % 340 AS INTEGER)) - INTERVAL 1096 DAY END"""
events = {
 'cc_all': "SELECT interaction_id ev_id, customer_id, ts, cat grp FROM cc",
 'cp_all': "SELECT complaint_id ev_id, customer_id, ts, coalesce(subcategory, category) grp FROM cp",
 'de_tx': "SELECT event_id ev_id, customer_id, ts, event_type grp FROM de WHERE event_category='Transaction' AND customer_id IS NOT NULL",
 'de_login': "SELECT event_id ev_id, customer_id, ts, event_type grp FROM de WHERE event_type='Login' AND customer_id IS NOT NULL",
}
rows = []
for name, q in events.items():
    con.execute(f"CREATE OR REPLACE TEMP TABLE e AS SELECT * FROM ({q}) WHERE customer_id IN (SELECT customer_id FROM cust)")
    con.execute(f"CREATE OR REPLACE TEMP TABLE e2 AS SELECT ev_id, customer_id, grp, ts, 'obs' kind FROM e UNION ALL SELECT ev_id, customer_id, grp, {placebo('ts')}, 'placebo' FROM e")
    r = con.execute("""SELECT kind, count(*) n_ev,
      avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts - INTERVAL 1 HOUR AND e2.ts))::INT) b1h,
      avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts - INTERVAL 24 HOUR AND e2.ts))::INT) b24h,
      avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts - INTERVAL 7 DAY AND e2.ts))::INT) b7d,
      avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts AND e2.ts + INTERVAL 1 HOUR))::INT) a1h,
      avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts AND e2.ts + INTERVAL 24 HOUR))::INT) a24h,
      avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts - INTERVAL 7 DAY AND e2.ts AND t.status='Declined'))::INT) b7d_decl
      FROM e2 GROUP BY 1 ORDER BY 1""").fetchdf()
    r.insert(0, 'event', name); rows.append(r)
    if name in ('cc_all', 'cp_all'):
        g = con.execute("""SELECT grp, kind, count(*) n, avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts - INTERVAL 7 DAY AND e2.ts))::INT) b7d,
            avg((EXISTS (SELECT 1 FROM t WHERE t.customer_id=e2.customer_id AND t.ts BETWEEN e2.ts - INTERVAL 7 DAY AND e2.ts AND t.status<>'Approved'))::INT) b7d_notappr
            FROM e2 GROUP BY ALL ORDER BY 1,2""").fetchdf()
        print(name); print(g.round(4).to_string(index=False))
print(pd.concat(rows).round(4).to_string(index=False))
