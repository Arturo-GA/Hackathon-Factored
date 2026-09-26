"""Verificador escéptico (parte D): (1) reproducir la comparación del hallazgo (consecutivas mismo comercio vs
consecutivas del producto) para ver si el 'vs 5.0%' es un control válido; (2) ¿hay recurrencia en OTROS tipos
(Payment con tcat, Deposit, Transfer...) que contradiga el título 'no existen cargos recurrentes'?"""
import duckdb, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 100)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

print("== D1 réplica del hallazgo: consecutivas mismo producto-comercio (rango sobre 24 comercios) ==")
iv = q("""WITH s AS (SELECT product_id, merchant_name, ts, amount,
   lag(ts) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pts, lag(amount) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pamt
   FROM tx WHERE merchant_name IS NOT NULL)
 SELECT merchant_name, count(*) n, median(date_diff('day', pts, ts)) med_gap, 100*avg((date_diff('day', pts, ts) BETWEEN 27 AND 33)::INT) pct_27_33,
   100*avg((abs(amount/pamt-1)<0.05)::INT) pct_amt_5pct FROM s WHERE pts IS NOT NULL GROUP BY 1""")
print(iv[["med_gap","pct_27_33","pct_amt_5pct"]].agg(["min","max"]).round(2))
print("== D1b baseline del hallazgo: consecutivas de compras del producto (cualquier comercio) ==")
print(q("""WITH s AS (SELECT product_id, ts, amount, lag(ts) OVER (PARTITION BY product_id ORDER BY ts) pts, lag(amount) OVER (PARTITION BY product_id ORDER BY ts) pamt FROM tx WHERE ttype='Purchase')
 SELECT count(*) n, median(date_diff('day', pts, ts)) med_gap, round(100*avg((date_diff('day', pts, ts) BETWEEN 27 AND 33)::INT),2) pct_27_33,
   round(100*avg((abs(amount/pamt-1)<0.05)::INT),2) pct_amt_5pct FROM s WHERE pts IS NOT NULL""").round(2))

print("== D2 recurrencia por ttype: consecutivas mismo (producto, ttype[, tcat]) ; bump en 27-33 vs vecinos ==")
d2 = q("""WITH s AS (SELECT ttype, product_id, ts, amount,
     date_diff('day', lag(ts) OVER (PARTITION BY product_id, ttype, coalesce(tcat,'?') ORDER BY ts), ts) d,
     lag(amount) OVER (PARTITION BY product_id, ttype, coalesce(tcat,'?') ORDER BY ts) pamt,
     day(lag(ts) OVER (PARTITION BY product_id, ttype, coalesce(tcat,'?') ORDER BY ts)) = day(ts) same_dom
   FROM tx)
 SELECT ttype, count(*) n, median(d) med_gap,
   round(100*avg((d BETWEEN 27 AND 33)::INT)/7,4) pdia_27_33,
   round(100*avg((d BETWEEN 20 AND 26)::INT)/7,4) pdia_20_26,
   round(100*avg((d BETWEEN 34 AND 40)::INT)/7,4) pdia_34_40,
   round(100*avg((d BETWEEN 6 AND 8)::INT)/3,4) pdia_6_8,
   round(100*avg((d BETWEEN 3 AND 5)::INT)/3,4) pdia_3_5,
   round(100*avg((d BETWEEN 9 AND 11)::INT)/3,4) pdia_9_11,
   round(100*avg(same_dom::INT),3) pct_mismo_dia_mes,
   round(100*avg((abs(amount/pamt-1)<=0.05)::INT),3) pct_monto_5pct,
   round(100*avg((amount=pamt)::INT),4) pct_monto_igual
 FROM s WHERE d IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
print(d2)

print("== D3 control de montos: mismo ttype+moneda, pareja AL AZAR de otro producto (orden por hash) ==")
print(q("""WITH s AS (SELECT ttype, currency, amount, lag(amount) OVER (PARTITION BY ttype, currency ORDER BY hash(transaction_id)) pamt FROM tx)
 SELECT ttype, round(100*avg((abs(amount/pamt-1)<=0.05)::INT),3) pct_monto_5pct_azar, round(100*avg((amount=pamt)::INT),4) pct_igual_azar
 FROM s WHERE pamt IS NOT NULL GROUP BY 1 ORDER BY 1"""))
