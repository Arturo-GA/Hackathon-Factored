"""Fraude/rechazo vs rasgos secuenciales y de ciclo de vida: gap desde tx previa del producto, posición en la secuencia,
tx antes de apertura / después de vencimiento, cstatus del cliente, dpd del producto, #productos, comercio repetido."""
from behavior_common import connect, q
import numpy as np
from sklearn.metrics import roc_auc_score
con = connect()
con.execute("""CREATE TEMP TABLE f AS SELECT t.transaction_id, t.customer_id, t.fraud::INT fraud, (t.status='Declined')::INT decl,
   epoch(t.ts - lag(t.ts) OVER (PARTITION BY t.product_id ORDER BY t.ts))/86400 gap_prod,
   epoch(t.ts - lag(t.ts) OVER (PARTITION BY t.customer_id ORDER BY t.ts))/86400 gap_cust,
   row_number() OVER (PARTITION BY t.product_id ORDER BY t.ts) pos,
   (t.ts::DATE < p.opened)::INT pre_open, coalesce((t.ts::DATE > p.expires)::INT,0) post_exp,
   (c.cstatus<>'Active')::INT cust_inact, coalesce(p.dpd,0) dpd, (t.country<>c.country)::INT foreign_tx,
   (t.merchant_name IS NOT NULL AND t.merchant_name = lag(t.merchant_name) OVER (PARTITION BY t.product_id ORDER BY t.ts))::INT same_merch,
   abs(t.amount_usd_n / nullif(lag(t.amount_usd_n) OVER (PARTITION BY t.product_id ORDER BY t.ts),0) - 1) amt_change
 FROM (SELECT *, CASE currency WHEN 'USD' THEN amount WHEN 'COP' THEN amount/4000 ELSE amount/350 END amount_usd_n FROM tx WHERE hash(customer_id) % 16 = 0) t
 JOIN pr p USING(product_id) JOIN cu c ON c.customer_id=t.customer_id""")
cols = ['gap_prod','gap_cust','pos','pre_open','post_exp','cust_inact','dpd','foreign_tx','same_merch','amt_change']
d = q(con, f"SELECT customer_id, fraud, decl, {','.join(cols)} FROM f")
rng = np.random.default_rng(0)
cust = d.customer_id.unique(); 
for tgt in ['fraud','decl']:
    for c in cols:
        m = d[c].notna()
        y = d.loc[m, tgt].values; x = d.loc[m, c].values
        if y.sum() < 20: continue
        auc = roc_auc_score(y, x)
        # bootstrap agrupado por cliente
        g = d.loc[m, 'customer_id'].values
        uc, inv = np.unique(g, return_inverse=True)
        bs = []
        for _ in range(100):
            w = rng.poisson(1, len(uc))[inv]
            bs.append(roc_auc_score(y, x, sample_weight=w))
        print(f"{tgt:5s} {c:11s} n={m.sum():6d} pos={int(y.sum()):5d} AUC={auc:.3f} IC95=[{np.percentile(bs,2.5):.3f},{np.percentile(bs,97.5):.3f}]")
print(q(con, "SELECT pre_open, post_exp, count(*) n, avg(fraud)*1000 fr_mil, avg(decl) decl FROM f GROUP BY 1,2 ORDER BY 1,2"))
