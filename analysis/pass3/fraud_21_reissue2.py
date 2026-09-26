"""Verificación: aperturas de producto tras fraude. Ventanas 7-180d, IC95 bootstrap por cliente, tipo del nuevo producto, placebo (ventanas previas)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
con = connect()
con.execute("""CREATE TEMP TABLE a AS SELECT t.transaction_id aid, t.customer_id, t.ts, t.fraud, p.ptype FROM tx t JOIN pr p USING(product_id)
 WHERE t.fraud OR (hash(t.transaction_id)%33=0 AND NOT t.fraud)""")
W=[7,14,30,60,90,180]
cols=[]
for w in W:
    cols += [f"count(x.product_id) FILTER (WHERE x.opened > a.ts::date AND x.opened <= a.ts::date + {w}) aft{w}",
             f"count(x.product_id) FILTER (WHERE x.opened <= a.ts::date AND x.opened > a.ts::date - {w}) bef{w}"]
d = q(con, f"SELECT a.aid, a.customer_id, a.fraud, {', '.join(cols)} FROM a LEFT JOIN pr x ON x.customer_id=a.customer_id GROUP BY 1,2,3")
print(d.fraud.value_counts())
rng = np.random.default_rng(0)
F = d[d.fraud]; C = d[~d.fraud]
for w in W:
    for side in ['aft','bef']:
        c=f'{side}{w}'
        rr = F[c].mean()/C[c].mean()
        bs=[]
        for _ in range(500):
            fi = F.sample(len(F), replace=True, random_state=rng.integers(1e9))
            bs.append(fi[c].mean()/C[c].mean())
        print(f"{c}: fraude {F[c].mean():.4f} (n_ap={F[c].sum()}) control {C[c].mean():.4f} RR={rr:.3f} IC95=[{np.percentile(bs,2.5):.3f},{np.percentile(bs,97.5):.3f}]")
# tipo de producto abierto en 30d tras fraude
t = q(con, """SELECT a.fraud, x.ptype, count(*) n FROM a JOIN pr x ON x.customer_id=a.customer_id AND x.opened > a.ts::date AND x.opened <= a.ts::date + 30 GROUP BY ALL""")
t = t.pivot(index='ptype', columns='fraud', values='n').fillna(0)
nF, nC = len(F), len(C)
t['rate_F']=t[True]/nF; t['rate_C']=t[False]/nC; t['rr']=t.rate_F/t.rate_C; print(t.round(4))
