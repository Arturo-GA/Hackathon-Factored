"""Verificador escéptico (parte 2): fraud_autorizacion_ignora_score.
(a) Simpson: Declined fraude vs legit por estrato (ttype, channel, country, año) + MH-RR y heterogeneidad.
(b) Replicación split-half del exceso de código 14 dentro de Declined (fraud_hi vs fraud_lo_null, por año).
(c) Reacción posterior: ¿las tx siguientes del MISMO producto tras un fraude se rechazan más (tarjeta bloqueada)?
(d) pstatus del producto con fraude vs sin fraude."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency, chi2 as chi2d
from fraud_00_common import connect, q
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = connect()

def rr_ci(a, n1, b, n0):
    if a == 0 or b == 0: return np.nan, np.nan, np.nan
    r = (a/n1)/(b/n0); se = np.sqrt(1/a - 1/n1 + 1/b - 1/n0)
    return r, np.exp(np.log(r)-1.96*se), np.exp(np.log(r)+1.96*se)

print('== (a) Declined fraude vs legit por estrato ==')
for col in ['ttype', 'channel', 'country', 'year(ts)', 'currency']:
    d = q(con, f"""SELECT {col} s, count(*) FILTER (WHERE fraud) nf, count(*) FILTER (WHERE fraud AND status='Declined') df,
      count(*) FILTER (WHERE fraud AND status<>'Approved') naf,
      count(*) FILTER (WHERE NOT fraud) nl, count(*) FILTER (WHERE NOT fraud AND status='Declined') dl,
      count(*) FILTER (WHERE NOT fraud AND status<>'Approved') nal FROM tx GROUP BY 1 ORDER BY 1""")
    rows = []; num = den = 0; lrs = []; ws = []
    for _, r in d.iterrows():
        rr, lo, hi = rr_ci(r.df, r.nf, r.dl, r.nl)
        rows.append(f"{str(r.s):12s} nf={int(r.nf):5d} decl_f={100*r.df/r.nf:5.2f}% decl_l={100*r.dl/r.nl:5.2f}% RR={rr:.2f}[{lo:.2f},{hi:.2f}]  noAprob_f={100*r.naf/r.nf:5.2f}% vs {100*r.nal/r.nl:5.2f}%")
        N = r.nf + r.nl; num += r.df*r.nl/N; den += r.dl*r.nf/N
        if r.df > 0:
            lr = np.log((r.df/r.nf)/(r.dl/r.nl)); v = 1/r.df - 1/r.nf + 1/r.dl - 1/r.nl; lrs.append(lr); ws.append(1/v)
    lrs, ws = np.array(lrs), np.array(ws); pooled = (lrs*ws).sum()/ws.sum(); Q = (ws*(lrs-pooled)**2).sum()
    print(f"-- {col}: MH-RR Declined = {num/den:.3f}; heterogeneidad Q={Q:.2f} gl={len(lrs)-1} p={1-chi2d.cdf(Q, len(lrs)-1):.3f}")
    for x in rows: print('   ', x)

print('\n== (b) Código dentro de Declined: fraud_hi vs fraud_lo_null vs legit, y por mitad temporal ==')
d = q(con, """SELECT CASE WHEN NOT fraud THEN 'legit' WHEN fscore>30 THEN 'fraud_hi' ELSE 'fraud_lo_null' END g,
  CASE WHEN ts < TIMESTAMP '2024-12-17' THEN 'H1' ELSE 'H2' END h, coalesce(code,'NULL') code, count(*) n
  FROM tx WHERE status='Declined' GROUP BY ALL""")
for key in ['g', 'h']:
    sub = d if key == 'g' else d[d.g != 'legit']
    pv = sub.pivot_table(index=key, columns='code', values='n', aggfunc='sum').fillna(0).astype(int)
    print((pv.div(pv.sum(1), axis=0)*100).round(1).assign(N=pv.sum(1)))
# código 14 entre Declined no aprobadas (Pending/Reversed) también
print(q(con, """SELECT status, fraud, count(*) n, round(100*avg((code='14')::int),2) pct14 FROM tx WHERE status<>'Approved' GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))

print('\n== (c) Tx siguientes del mismo producto tras un fraude vs tras una legítima ==')
con.execute("""CREATE TEMP TABLE seq AS SELECT product_id, ts, fraud, status,
   row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn FROM tx""")
con.execute("""CREATE TEMP TABLE ev AS SELECT product_id, ts ev_ts, rn ev_rn, fraud ev_fraud FROM seq
   WHERE fraud OR hash(product_id || ts::VARCHAR) % 200 = 0""")
d = q(con, """SELECT e.ev_fraud, (s.rn - e.ev_rn) k, count(*) n, avg((s.status='Declined')::int) p_decl, avg((s.status<>'Approved')::int) p_noapr,
   avg(s.fraud::int) p_fraud, avg(date_diff('hour', e.ev_ts, s.ts)) h_med
   FROM ev e JOIN seq s ON s.product_id=e.product_id AND s.rn BETWEEN e.ev_rn+1 AND e.ev_rn+5 GROUP BY 1,2 ORDER BY 1,2""")
print(d.round(4).to_string(index=False))
for w in [1, 7, 30]:
    d = q(con, f"""SELECT e.ev_fraud, count(*) n, sum((s.status='Declined')::int) dcl, sum((s.status<>'Approved')::int) na
      FROM ev e JOIN seq s ON s.product_id=e.product_id AND s.rn > e.ev_rn AND s.ts <= e.ev_ts + INTERVAL ({w}) DAY GROUP BY 1""").set_index('ev_fraud')
    rr, lo, hi = rr_ci(d.loc[True, 'dcl'], d.loc[True, 'n'], d.loc[False, 'dcl'], d.loc[False, 'n'])
    print(f"  ventana {w:2d}d: tx posteriores tras fraude n={d.loc[True,'n']:,} Declined={100*d.loc[True,'dcl']/d.loc[True,'n']:.2f}% vs tras legit n={d.loc[False,'n']:,} {100*d.loc[False,'dcl']/d.loc[False,'n']:.2f}%  RR={rr:.3f}[{lo:.3f},{hi:.3f}]")
d = q(con, """SELECT e.ev_fraud, count(*) n_ev, avg(cnt) tx_post_30d FROM (SELECT e.product_id, e.ev_rn, e.ev_fraud,
   count(s.rn) cnt FROM ev e LEFT JOIN seq s ON s.product_id=e.product_id AND s.rn > e.ev_rn AND s.ts <= e.ev_ts + INTERVAL 30 DAY GROUP BY ALL) e GROUP BY 1""")
print('  volumen de tx posteriores (30d) por evento:\n', d.to_string(index=False))

print('\n== (d) pstatus del producto: con >=1 fraude vs sin fraude ==')
d = q(con, """WITH f AS (SELECT product_id, max(fraud::int) hf, max(CASE WHEN fraud AND fscore>30 THEN 1 ELSE 0 END) hhi FROM tx GROUP BY 1)
  SELECT p.pstatus, count(*) FILTER (WHERE hf=1) n_f, count(*) FILTER (WHERE hf=0) n_nf, count(*) FILTER (WHERE hhi=1) n_hi FROM f JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1""")
d['pct_f'] = (100*d.n_f/d.n_f.sum()).round(2); d['pct_nf'] = (100*d.n_nf/d.n_nf.sum()).round(2); d['pct_hi'] = (100*d.n_hi/d.n_hi.sum()).round(2)
print(d.to_string(index=False))
