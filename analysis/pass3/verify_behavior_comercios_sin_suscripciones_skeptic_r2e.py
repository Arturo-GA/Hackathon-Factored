"""Verificador escéptico (ronda 2, parte E): ¿hay cargos recurrentes FUERA de las compras con comercio?
(préstamos/seguros con Payment mensual, débitos fijos). Consecutivas mismo (producto, ttype):
densidad diaria de brechas en 28-31 vs vecinas, % mismo día del mes vs esperado (sum p_dom^2), % montos idénticos,
nº máx de tx por (producto, ttype) en 3 años (una cuota mensual daría ~36)."""
import duckdb, pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

dom = q("SELECT day(ts) d, count(*) n FROM tx GROUP BY 1")
p_dom_same = float(((dom.n / dom.n.sum()) ** 2).sum())
print(f"P(mismo día del mes) esperado por azar = {p_dom_same:.5f}")

r = q("""WITH s AS (SELECT p.ptype, t.ttype, t.product_id, t.ts, t.amount,
            date_diff('day', lag(t.ts) OVER w, t.ts) d, lag(t.amount) OVER w pa, day(lag(t.ts) OVER w)=day(t.ts) sdom
          FROM tx t JOIN pr p USING(product_id) WINDOW w AS (PARTITION BY t.product_id, t.ttype ORDER BY t.ts))
  SELECT ptype, ttype, count(*) n, median(d) med_gap,
    100*avg((d BETWEEN 28 AND 31)::INT)/4 pdia_28_31, 100*avg((d BETWEEN 21 AND 27 OR d BETWEEN 32 AND 38)::INT)/14 pdia_vecinos,
    100*avg((d BETWEEN 6 AND 8)::INT)/3 pdia_6_8, 100*avg((d BETWEEN 3 AND 5 OR d BETWEEN 9 AND 11)::INT)/6 pdia_vec7,
    100*avg(sdom::INT) pct_mismo_dom, 100*avg((amount=pa)::INT) pct_monto_igual, 100*avg((abs(amount/pa-1)<=0.05)::INT) pct_monto5
  FROM s WHERE d IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""")
r["RR_28_31"] = r.pdia_28_31 / r.pdia_vecinos
r["RR_7"] = r.pdia_6_8 / r.pdia_vec7
r["RR_dom"] = r.pct_mismo_dom / (100 * p_dom_same)
print(r.round(4).to_string(index=False))
print(f"\nRR_28_31 rango {r.RR_28_31.min():.3f}–{r.RR_28_31.max():.3f} | RR_dom rango {r.RR_dom.min():.3f}–{r.RR_dom.max():.3f} | %monto igual máx {r.pct_monto_igual.max():.4f}")

print("\n== nº de tx por (producto, ttype): máximo y p99 (cuota mensual 3 años => ~36) ==")
print(q("""WITH c AS (SELECT p.ptype, t.ttype, t.product_id, count(*) k FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2,3)
  SELECT ptype, ttype, count(*) n_prod, round(avg(k),2) k_medio, quantile_cont(k, 0.99) k_p99, max(k) k_max
  FROM c GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))

print("\n== secuencias: >=3 tx consecutivas del mismo (producto, ttype) con ambas brechas en 27-33 días ==")
print(q("""WITH s AS (SELECT t.ttype, date_diff('day', lag(t.ts) OVER w, t.ts) d1, date_diff('day', lag(t.ts,2) OVER w, lag(t.ts) OVER w) d2
          FROM tx t WINDOW w AS (PARTITION BY t.product_id, t.ttype ORDER BY t.ts))
  SELECT ttype, count(*) n_tripletas, sum((d1 BETWEEN 27 AND 33 AND d2 BETWEEN 27 AND 33)::INT) n_mensual_doble,
         round(100*avg((d1 BETWEEN 27 AND 33)::INT),3) p1, round(100*avg((d1 BETWEEN 27 AND 33 AND d2 BETWEEN 27 AND 33)::INT),4) p_doble,
         round(100*avg((d1 BETWEEN 27 AND 33)::INT)*avg((d2 BETWEEN 27 AND 33)::INT),4) p_doble_indep
  FROM s WHERE d2 IS NOT NULL GROUP BY 1 ORDER BY 1""").to_string(index=False))
