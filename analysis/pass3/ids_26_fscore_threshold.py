# ids_26: consecuencia del mecanismo decodificado (legítima: score=30*u, fraude: score=100*u): umbral óptimo 30, no 50
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select fraud, count(*) n, count(fscore) n_score, max(fscore) max_score, sum((fscore>30)::int) gt30, sum((fscore>=50)::int) ge50, sum((fscore is null)::int) n_null from tx group by 1"""))
print(q("""select thr, sum((fscore>thr and fraud)::int) tp, sum((fscore>thr and not fraud)::int) fp, sum(fraud::int) pos,
   round(sum((fscore>thr and fraud)::int)*1.0/sum(fraud::int),4) recall, round(sum((fscore>thr and fraud)::int)*1.0/nullif(sum((fscore>thr)::int),0),4) prec
   from tx, (select unnest([29.9, 30, 30.01, 40, 49.99]) thr) group by thr order by thr"""))
