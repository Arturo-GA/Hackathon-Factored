"""Suscripciones: pares cliente-comercio repetidos; intervalos entre compras; similitud de montos.
Compara con lo esperado si el comercio se elige al azar (según frecuencia global)."""
from behavior_common import connect, q
import numpy as np
con = connect()
# pares cliente-comercio
d = q(con, """WITH p AS (SELECT product_id, merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2)
  SELECT n, count(*) npairs FROM p GROUP BY 1 ORDER BY 1""")
print(d)
# expected under independence: for each product, number of purchases with merchant; distribution of repeats
# simulate: per product with k merchant tx, sample merchants iid from global freq
freq = q(con, "SELECT merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1")
pm = (freq.n/freq.n.sum()).values
kdist = q(con, "SELECT k, count(*) np FROM (SELECT product_id, count(*) k FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1) GROUP BY 1")
rng = np.random.default_rng(0)
from collections import Counter
cnt = Counter()
for k, npr in zip(kdist.k, kdist.np):
    s = rng.multinomial(k, pm, size=npr)
    for v in s[s>0].ravel(): cnt[int(v)] += 1
print("simulado (indep):", sorted(cnt.items())[:10])
# intervalos entre compras sucesivas en el mismo producto-comercio
iv = q(con, """WITH s AS (SELECT product_id, merchant_name, ts, amount,
   lag(ts) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pts, lag(amount) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pamt
   FROM tx WHERE merchant_name IS NOT NULL)
 SELECT merchant_name, count(*) n, median(date_diff('day', pts, ts)) med_gap, avg((date_diff('day', pts, ts) BETWEEN 27 AND 33)::INT) pct_27_33,
   median(abs(amount/pamt-1)) med_amt_rel_diff, avg((abs(amount/pamt-1)<0.05)::INT) pct_amt_5pct
 FROM s WHERE pts IS NOT NULL GROUP BY 1 ORDER BY 1""")
print(iv)
# baseline: gaps between any two consecutive purchases in same product (any merchant)
print(q(con, """WITH s AS (SELECT product_id, ts, amount, lag(ts) OVER (PARTITION BY product_id ORDER BY ts) pts, lag(amount) OVER (PARTITION BY product_id ORDER BY ts) pamt FROM tx WHERE ttype='Purchase')
 SELECT count(*), median(date_diff('day', pts, ts)) med_gap, avg((date_diff('day', pts, ts) BETWEEN 27 AND 33)::INT) pct_27_33, avg((abs(amount/pamt-1)<0.05)::INT) pct_amt_5pct FROM s WHERE pts IS NOT NULL"""))
