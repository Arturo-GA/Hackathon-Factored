"""hunt_02: valores de de/cs/sv y fx para disenar features."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t, cols in {'de':['event_type','event_category','channel','platform','browser','action','is_mobile','ip_country','referrer','utm_source'],
                'cs':['send_channel','send_status','failure_reason'],
                'sv':['survey_type','send_channel','nps_category','comment_sentiment'],
                'fx':['src','dst','source']}.items():
    for c in cols:
        r = con.execute(f"SELECT {c}, count(*) n FROM {t} GROUP BY 1 ORDER BY 2 DESC LIMIT 15").fetchall()
        print(t, c, r)
print(con.execute("SELECT src,dst,min(date),max(date),min(rate),avg(rate),max(rate) FROM fx WHERE src='USD' GROUP BY 1,2").fetchall())
print(con.execute("SELECT count(*), count(DISTINCT customer_id), count(product_id) FROM de").fetchall())
print(con.execute("SELECT sv.survey_type, min(score), avg(score), max(score), count(*) FROM sv GROUP BY 1").fetchall())
