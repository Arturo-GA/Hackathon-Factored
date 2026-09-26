import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
d = con.execute("""WITH c AS (SELECT process_date d, count(*) ncc FROM cc GROUP BY 1),
 s AS (SELECT process_date d, count(*) nsv FROM sv GROUP BY 1)
 SELECT c.d, ncc, coalesce(nsv,0) nsv FROM c LEFT JOIN s USING(d) ORDER BY 1""").fetchdf()
r = d.nsv / d.ncc
print("sv/cc diario: media=%.4f sd=%.5f min=%.4f max=%.4f" % (r.mean(), r.std(), r.min(), r.max()))
for p in [0.31, 0.3, 0.32]:
    print(p, "floor exact:", np.mean(d.nsv == np.floor(d.ncc * p)), "round exact:", np.mean(d.nsv == np.round(d.ncc * p)))
print("binomial sd esperada rel:", np.sqrt(r.mean()*(1-r.mean())/d.ncc.mean()) )
# cc interactions: fraction with survey, by day - thinning
print(con.execute("""SELECT count(*) n_cc, count(s.interaction_id) n_sv, count(DISTINCT s.interaction_id) nd FROM cc c LEFT JOIN sv s USING(interaction_id)""").fetchdf())
