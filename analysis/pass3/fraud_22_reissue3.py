"""Control intra-cliente y emparejado por mes: aperturas de producto en 14/30d tras el fraude vs tras tx legítimas del MISMO cliente; placebo desplazando la fecha."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
con = connect()
con.execute("""CREATE TEMP TABLE fc AS SELECT DISTINCT customer_id FROM tx WHERE fraud""")
con.execute("""CREATE TEMP TABLE a AS SELECT t.transaction_id aid, t.customer_id, t.ts, t.fraud FROM tx t JOIN fc USING(customer_id)""")
def opens(shift_days=0):
    return q(con, f"""SELECT a.aid, a.customer_id, a.fraud, date_trunc('month', a.ts) m,
      count(x.product_id) FILTER (WHERE x.opened > (a.ts + INTERVAL ({shift_days}) DAY)::date AND x.opened <= (a.ts + INTERVAL ({shift_days}) DAY)::date + 14) o14,
      count(x.product_id) FILTER (WHERE x.opened > (a.ts + INTERVAL ({shift_days}) DAY)::date AND x.opened <= (a.ts + INTERVAL ({shift_days}) DAY)::date + 30) o30
      FROM a LEFT JOIN pr x ON x.customer_id=a.customer_id GROUP BY 1,2,3,4""")
rng = np.random.default_rng(1)
for shift in [0, -60, 60, -120]:
    d = opens(shift)
    # intra-cliente: por cliente, media en fraude vs media en legítimas
    g = d.groupby(['customer_id','fraud'])[['o14','o30']].mean().unstack('fraud').dropna()
    diff14 = (g[('o14',True)]-g[('o14',False)]); diff30=(g[('o30',True)]-g[('o30',False)])
    bs = [diff14.sample(len(diff14), replace=True, random_state=rng.integers(1e9)).mean() for _ in range(400)]
    print(f"shift={shift:>4}d  clientes={len(g)}  o14 fraude={g[('o14',True)].mean():.4f} legit_mismo_cliente={g[('o14',False)].mean():.4f} dif={diff14.mean():+.4f} IC95=[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}] | o30 dif={diff30.mean():+.4f} ratio30={g[('o30',True)].mean()/g[('o30',False)].mean():.3f}")
