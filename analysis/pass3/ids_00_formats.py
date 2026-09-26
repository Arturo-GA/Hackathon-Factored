# ids_00: formato de cada ID (prefijo, longitud, alfabeto) en todas las tablas
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
cols = [('tx','transaction_id'),('tx','product_id'),('tx','customer_id'),('tx','branch_id'),
        ('cc','interaction_id'),('cc','agent_id'),('cc','mentioned_products'),
        ('tr','transcript_id'),('cu','customer_id'),('cu','document_number'),('cu','registration_branch_id'),('cu','email'),('cu','mobile_phone'),
        ('pr','product_id'),('pr','product_number'),('pr','opening_branch_id'),
        ('cp','complaint_id'),('cp','affected_product_id'),('cp','related_branch_id'),('cp','assigned_agent_id'),
        ('sv','survey_id'),('ag','agent_id'),('ag','employee_code'),('ag','assigned_branch_id'),('ag','email'),
        ('br','branch_id'),('br','branch_code'),('de','event_id'),('de','session_id'),('de','product_id'),('de','ip_address'),
        ('cs','send_id'),('cs','campaign_id'),('mc','campaign_id')]
for t,c in cols:
    samp = "using sample 200000" if t in ('tx','de','cs','cc') else ""
    s = f"""select regexp_replace({c}, '[A-Z]', 'A', 'g') pat0, count(*) n from (select {c} from {t} where {c} is not null {samp}) group by 1 order by 2 desc limit 1"""
    s2 = f"""select count(*) n, count({c}) nn, min(length({c})) mnl, max(length({c})) mxl, any_value({c}) ex,
             count(distinct regexp_replace(regexp_replace({c}, '[A-Z]', 'A', 'g'),'[0-9]','9','g')) npat
             from (select {c} from {t} {samp})"""
    r = con.execute(s2).fetchone()
    pats = con.execute(f"""select regexp_replace(regexp_replace({c}, '[A-Z]', 'A', 'g'),'[0-9]','9','g') p, count(*) n from (select {c} from {t} where {c} is not null {samp}) group by 1 order by 2 desc limit 3""").fetchall()
    print(f"{t}.{c}: n={r[0]} nn={r[1]} len={r[2]}-{r[3]} ex={r[4]} npat={r[5]} top={pats}")
