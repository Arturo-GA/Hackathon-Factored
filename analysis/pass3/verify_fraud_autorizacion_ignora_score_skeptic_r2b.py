"""Verificador escéptico (reintento, parte b): ¿la caída de Declined en las tx POSTERIORES a un fraude es real o azar?
Población completa, mismo producto y mismo cliente: lag 1..5 (tx siguientes) y lead 1..5 (placebo, tx anteriores),
por tramo de fscore del fraude, por mitades aleatorias de eventos (replicación) y por ventana temporal."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import norm
from fraud_00_common import connect, q
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = connect()

def rr_ci(a, n1, b, n0):
    r = (a/n1)/(b/n0); se = np.sqrt(1/a - 1/n1 + 1/b - 1/n0); z = np.log(r)/se
    return r, np.exp(np.log(r)-1.96*se), np.exp(np.log(r)+1.96*se), 2*norm.sf(abs(z))

for part in ['product_id', 'customer_id']:
    con.execute(f"""CREATE OR REPLACE TEMP TABLE s AS SELECT transaction_id, {part} k, ts, fraud,
       CASE WHEN fraud AND fscore>30 THEN 'hi' WHEN fraud THEN 'lo' ELSE 'legit' END g, (status='Declined') dcl,
       hash(transaction_id) % 2 half, row_number() OVER (PARTITION BY {part} ORDER BY ts, transaction_id) rn FROM tx""")
    print(f'== {part}: estado Declined de la tx a distancia d de un fraude (d>0 posterior, d<0 anterior=placebo) ==')
    rows = []
    for dist in [1, 2, 3, 4, 5, -1, -2, -3]:
        d = q(con, f"""SELECT a.g, a.half, count(*) n, sum(b.dcl::int) dcl, avg(date_diff('hour', a.ts, b.ts)) hrs
           FROM s a JOIN s b ON b.k=a.k AND b.rn=a.rn+({dist}) GROUP BY ALL""")
        leg = d[d.g == 'legit']; nl, dl = leg.n.sum(), leg.dcl.sum()
        fr = d[d.g != 'legit']; nf, df_ = fr.n.sum(), fr.dcl.sum()
        r, lo, hi, p = rr_ci(df_, nf, dl, nl)
        extra = {}
        for lab, sub in [('hi', fr[fr.g == 'hi']), ('lo', fr[fr.g == 'lo']), ('h0', fr[fr.half == 0]), ('h1', fr[fr.half == 1])]:
            extra[lab] = f'{100*sub.dcl.sum()/sub.n.sum():.2f}% (n={sub.n.sum()})'
        rows.append(dict(dist=dist, n_fraude=nf, pct_decl_fraude=round(100*df_/nf, 2), pct_decl_legit=round(100*dl/nl, 3),
                         RR=round(r, 3), IC95=f'[{lo:.3f},{hi:.3f}]', p=round(p, 4), hi=extra['hi'], lo=extra['lo'], mitad0=extra['h0'], mitad1=extra['h1']))
    print(pd.DataFrame(rows).to_string(index=False))
    # agregado posterior 1..5 vs anterior 1..3
    if part == 'product_id':
        print('\n  -- Por ventana temporal hacia adelante (todas las tx posteriores del producto) --')
        d = q(con, """SELECT a.fraud, CASE WHEN date_diff('day', a.ts, b.ts) < 1 THEN 'a_<1d' WHEN date_diff('day', a.ts, b.ts) < 7 THEN 'b_1-7d'
              WHEN date_diff('day', a.ts, b.ts) < 30 THEN 'c_7-30d' WHEN date_diff('day', a.ts, b.ts) < 90 THEN 'd_30-90d' ELSE 'e_90d+' END w,
              count(*) n, sum(b.dcl::int) dcl
           FROM (SELECT * FROM s WHERE fraud OR hash(transaction_id) % 50 = 0) a JOIN s b ON b.k=a.k AND b.rn>a.rn GROUP BY ALL ORDER BY 2,1""")
        pv = d.pivot(index='w', columns='fraud', values=['n', 'dcl'])
        for w in pv.index:
            a1, n1, a0, n0 = pv.loc[w, ('dcl', True)], pv.loc[w, ('n', True)], pv.loc[w, ('dcl', False)], pv.loc[w, ('n', False)]
            r, lo, hi, p = rr_ci(a1, n1, a0, n0)
            print(f'   {w:9s} fraude {100*a1/n1:5.2f}% (n={int(n1):6d}) vs legit {100*a0/n0:5.2f}% (n={int(n0):7d})  RR={r:.3f} [{lo:.3f},{hi:.3f}] p={p:.4f}')
    print()
