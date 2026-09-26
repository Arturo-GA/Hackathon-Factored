# ids_21: unicidad de llaves primarias y orden de filas en cc (¿la posición en el archivo diario codifica resolved/escalated?)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
for t,k in [('tx','transaction_id'),('cc','interaction_id'),('cp','complaint_id'),('sv','survey_id'),('tr','transcript_id'),('cs','send_id'),('pr','product_id'),('cu','customer_id')]:
    print(t, k, con.execute(f"select count(*), count(distinct {k}) from {t}").fetchone())
# prefijo CMP- compartido
print(q("select 'cp' t, length(complaint_id) l, count(*) from cp group by 1,2 union all select 'mc', length(campaign_id), count(*) from mc group by 1,2"))
c2 = duckdb.connect(); c2.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
print(c2.execute("""with t as (select _source_file sf, file_row_number frn, was_resolved='True' res, was_escalated='True' esc, try_cast(interaction_date as timestamp) ts
      from read_parquet('data/bronze/call_center_interactions.parquet', file_row_number=true)),
  t2 as (select *, frn - min(frn) over (partition by sf) rin, count(*) over (partition by sf) nf, lag(ts) over (partition by sf order by frn) pts from t)
  select least(4, floor(rin*5.0/nf))::int quintil_pos, count(*) n, round(avg(res::int),4) resolved, round(avg(esc::int),4) escalated, round(avg((ts>=pts)::int),3) ts_nondecr
  from t2 group by 1 order by 1""").fetchdf().to_string())
