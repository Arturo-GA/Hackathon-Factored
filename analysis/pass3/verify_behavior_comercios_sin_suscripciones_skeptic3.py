"""Verificador escéptico (parte C): ¿periodicidad o montos parecidos en pares del MISMO comercio vs pares de comercios
DISTINTOS dentro del mismo producto? (control interno: mismo producto, mismas fechas posibles; solo cambia el comercio)."""
import duckdb, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 100)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

base = """WITH b AS (SELECT {lvl} id, merchant_name m, ts, amount a, row_number() OVER () rid FROM tx WHERE merchant_name IS NOT NULL),
pr AS (SELECT (x.m=y.m) same, {grp} g, abs(date_diff('day', x.ts, y.ts)) d, x.a a1, y.a a2,
              day(x.ts)=day(y.ts) same_dom
       FROM b x JOIN b y ON x.id=y.id AND x.rid<y.rid)
SELECT same, g, count(*) n, median(d) med_gap,
  round(100*avg((d BETWEEN 27 AND 33)::INT),3) pct_27_33,
  round(100*avg((d>=27 AND abs(d-30*round(d/30.0))<=2)::INT),3) pct_mult30_pm2,
  round(100*avg((d>=26 AND abs(d-30*round(d/30.0))>=5 AND abs(d-30*round(d/30.0))<=7)::INT),3) pct_ctrl_off30,
  round(100*avg(same_dom::INT),3) pct_mismo_dia_mes,
  round(100*avg((abs(a2/a1-1)<=0.05)::INT),3) pct_monto_5pct,
  round(100*avg((a1=a2)::INT),4) pct_monto_igual
FROM pr GROUP BY 1,2 ORDER BY 2,1"""

print("== C1 pares dentro de PRODUCTO: mismo comercio vs distinto ==")
print(q(base.format(lvl="product_id", grp="'todos'")))
print("== C2 pares dentro de CLIENTE: mismo comercio vs distinto ==")
print(q(base.format(lvl="customer_id", grp="'todos'")))
print("== C3 dentro de PRODUCTO, por comercio de x (tipo 'suscripción' vs resto) ==")
print(q(base.format(lvl="product_id", grp="CASE WHEN x.m IN ('Cable TV','Streaming Music','Internet Plus','Empresa Telefónica','Servicios Públicos') THEN x.m ELSE 'resto' END")))
