"""hunt_01: valores y frecuencias de columnas categoricas clave."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
spec = {
 'tx': ['ttype','tcat','currency','channel','mcat','country','status','code'],
 'cu': ['document_type','gender','country','detected_accent','segment','occupation','marital_status','education_level','cstatus','mkt'],
 'pr': ['ptype','currency','pstatus','opening_channel','app'],
 'cc': ['itype','channel','cat','sent','c_acc','a_acc'],
 'cp': ['case_type','category','rchan','priority','status','resolution'],
}
for t, cols in spec.items():
    for c in cols:
        r = con.execute(f"SELECT {c}, count(*) n FROM {t} GROUP BY 1 ORDER BY 2 DESC LIMIT 25").fetchall()
        print(t, c, len(r), r[:25])
print(con.execute("SELECT count(DISTINCT merchant_name), count(DISTINCT city), count(DISTINCT branch_id) FROM tx").fetchall())
print(con.execute("SELECT count(DISTINCT contact_reason) FROM cc").fetchall())
print(con.execute("SELECT contact_reason, cat, count(*) FROM cc GROUP BY 1,2 ORDER BY 3 DESC LIMIT 40").fetchall())
print(con.execute("SELECT min(credit_score),avg(credit_score),max(credit_score),min(income),median(income),max(income), count(*) FILTER (WHERE credit_score IS NULL), count(*) FILTER (WHERE income IS NULL) FROM cu").fetchall())
print(con.execute("SELECT count(*) FILTER (WHERE dpd>0), count(*) FILTER (WHERE dpd>=30), count(*) FILTER (WHERE dpd IS NULL), count(*) FROM pr").fetchall())
print(con.execute("SELECT ptype, count(*), count(*) FILTER (WHERE dpd>0), avg(dpd), count(*) FILTER (WHERE app), count(*) FILTER (WHERE app IS NULL) FROM pr GROUP BY 1").fetchall())
