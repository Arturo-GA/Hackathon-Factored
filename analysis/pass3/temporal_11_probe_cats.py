import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2")
print(con.execute("SELECT category, subcategory, count(*) n FROM cp GROUP BY ALL ORDER BY n DESC LIMIT 30").fetchdf().to_string(index=False))
print(con.execute("SELECT event_category, event_type, count(*) n FROM de GROUP BY ALL ORDER BY n DESC LIMIT 30").fetchdf().to_string(index=False))
print(con.execute("SELECT cat, contact_reason, count(*) n FROM cc GROUP BY ALL ORDER BY n DESC LIMIT 40").fetchdf().to_string(index=False))
