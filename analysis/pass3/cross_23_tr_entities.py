import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
pd_ = con.execute("select mentioned_entities, detected_keywords, detected_intents, main_topics, left(full_text,300) ft from tr using sample 6").fetchdf()
for r in pd_.itertuples(): print(r.mentioned_entities, '|', r.detected_keywords, '|', r.detected_intents, '|', r.main_topics, '|', r.ft, '\n')
print(q("select count(*) n, count(mentioned_entities) ne, count(distinct mentioned_entities) nde from tr"))
print(q("select mentioned_entities, count(*) from tr group by 1 order by 2 desc limit 10"))
print(q("select ip_country, (customer_id is null) nocust, count(*) from de group by 1,2 order by 1"))
