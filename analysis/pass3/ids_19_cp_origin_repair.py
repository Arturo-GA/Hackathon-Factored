# ids_19: ¿se puede reparar cp.origin_interaction_id (100% nulo)? buscar interacción cc del mismo cliente cerca de la creación del reclamo vs placebo (cliente al azar / fecha desplazada)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select rchan, count(*) n from cp group by 1 order by 2 desc"))
con.execute("create temp table c as select customer_id, ts, cat, channel from cc")
for w in [0, 1, 7]:
    print('ventana dias', w, q(f"""select cp.rchan, count(*) n,
      round(avg((exists(select 1 from c where c.customer_id=cp.customer_id and c.ts between cp.ts - interval {w} day - interval 1 hour and cp.ts + interval 1 hour))::int),4) any_cc,
      round(avg((exists(select 1 from c where c.customer_id=cp.customer_id and c.cat='Queja' and c.ts between cp.ts - interval {w} day - interval 1 hour and cp.ts + interval 1 hour))::int),4) queja_cc,
      round(avg((exists(select 1 from c where c.customer_id=cp.customer_id and c.ts between cp.ts - interval {w+60} day - interval 1 hour and cp.ts - interval 60 day + interval 1 hour))::int),4) placebo_m60d
      from (select * from cp using sample 15000) cp group by rollup(1) order by 1"""))
print(q("select min(ts), max(ts) from cp"))
