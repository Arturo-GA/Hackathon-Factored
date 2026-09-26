"""Descomponer: aperturas 14d tras la tx, separando el PROPIO producto de la tx (tx anterior a su apertura) vs OTROS productos. Intra-cliente."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
con = connect()
con.execute("""CREATE TEMP TABLE fc AS SELECT DISTINCT customer_id FROM tx WHERE fraud""")
con.execute("""CREATE TEMP TABLE a AS SELECT t.transaction_id aid, t.customer_id, t.product_id pid, t.ts, t.fraud FROM tx t JOIN fc USING(customer_id)""")
d = q(con, """SELECT a.aid, a.customer_id, a.fraud,
  count(x.product_id) FILTER (WHERE x.product_id=a.pid AND x.opened > a.ts::date AND x.opened <= a.ts::date + 14) own14,
  count(x.product_id) FILTER (WHERE x.product_id<>a.pid AND x.opened > a.ts::date AND x.opened <= a.ts::date + 14) oth14,
  count(x.product_id) FILTER (WHERE x.product_id<>a.pid AND x.opened > a.ts::date AND x.opened <= a.ts::date + 30) oth30
  FROM a LEFT JOIN pr x ON x.customer_id=a.customer_id GROUP BY 1,2,3""")
rng=np.random.default_rng(2)
g = d.groupby(['customer_id','fraud'])[['own14','oth14','oth30']].mean().unstack('fraud').dropna()
for c in ['own14','oth14','oth30']:
    diff = g[(c,True)]-g[(c,False)]
    bs=[diff.sample(len(diff),replace=True,random_state=rng.integers(1e9)).mean() for _ in range(400)]
    print(f"{c}: fraude={g[(c,True)].mean():.4f} legit_mismo_cliente={g[(c,False)].mean():.4f} ratio={g[(c,True)].mean()/max(g[(c,False)].mean(),1e-9):.3f} dif={diff.mean():+.4f} IC95=[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}]")
# distribución de (opened - ts) para el propio producto, fraude vs legit (global)
print(q(con, """SELECT fraud, count(*) n, round(100*avg((date_diff('day', ts::date, p.opened) BETWEEN 1 AND 14)::int),3) pct_open_1_14d_after,
  round(100*avg((p.opened > ts::date)::int),2) pct_before_open FROM tx JOIN pr p USING(product_id) GROUP BY 1"""))
