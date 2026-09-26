# ids_01: tamaño del pool de cada FK y cobertura contra su tabla maestra
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
fks = [('cu','registration_branch_id','br','branch_id'),('ag','assigned_branch_id','br','branch_id'),
       ('pr','opening_branch_id','br','branch_id'),('cp','related_branch_id','br','branch_id'),('tx','branch_id','br','branch_id'),
       ('cp','affected_product_id','pr','product_id'),('cp','assigned_agent_id','ag','agent_id'),('cc','agent_id','ag','agent_id'),
       ('cp','customer_id','cu','customer_id'),('pr','customer_id','cu','customer_id'),('de','product_id','pr','product_id'),
       ('cs','campaign_id','mc','campaign_id'),('sv','agent_id','ag','agent_id'),('tr','agent_id','ag','agent_id'),
       ('tx','product_id','pr','product_id'),('sv','interaction_id','cc','interaction_id'),('tr','interaction_id','cc','interaction_id')]
for t,c,m,k in fks:
    r = con.execute(f"""with f as (select distinct {c} v from {t} where {c} is not null)
      select (select count(*) from {t} where {c} is not null) nn, (select count(*) from f) ndist,
             (select count(*) from f where v in (select {k} from {m})) nmatch,
             (select count(*) from {m}) nmaster""").fetchone()
    print(f"{t}.{c} -> {m}.{k}: nonnull={r[0]} distinct={r[1]} distinct_in_master={r[2]} master_size={r[3]}")
