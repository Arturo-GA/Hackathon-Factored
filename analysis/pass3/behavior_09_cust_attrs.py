"""¿Atributos del cliente predicen comportamiento transaccional?
Targets: nact (#productos activos), ntx/nact (tx por producto activo), monto medio usd-equivalente, tasa de rechazo, mezcla de ttype.
Features: segment, income, credit_score, country, occupation, edad, cstatus, marital, education, gender, antigüedad."""
from behavior_common import connect, q
import numpy as np, pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score
con = connect()
d = q(con, """WITH t AS (SELECT customer_id, count(*) ntx,
      avg(CASE currency WHEN 'USD' THEN amount WHEN 'COP' THEN amount/4000 ELSE amount/350 END) amt_usd,
      avg(CASE WHEN ttype='Purchase' THEN CASE currency WHEN 'USD' THEN amount WHEN 'COP' THEN amount/4000 ELSE amount/350 END END) pur_usd,
      avg((status='Declined')::INT) decl, avg((ttype='Purchase')::INT) sh_pur, avg((channel IN ('App','Web'))::INT) sh_dig,
      avg((country<>cty)::INT) foreign_sh
    FROM (SELECT t.*, c.country cty FROM tx t JOIN cu c USING(customer_id)) GROUP BY 1),
  p AS (SELECT customer_id, count(*) nprod, sum((pstatus='Active')::INT) nact, max(dpd) maxdpd FROM pr GROUP BY 1)
  SELECT c.customer_id, c.segment, c.income, c.credit_score, c.country, c.occupation, c.marital_status, c.education_level, c.gender, c.cstatus,
     date_diff('year', c.dob, DATE '2026-06-17') age, date_diff('day', c.registration_date::DATE, DATE '2026-06-17') tenure, c.mkt::INT mkt,
     coalesce(p.nprod,0) nprod, coalesce(p.nact,0) nact, p.maxdpd, coalesce(t.ntx,0) ntx, t.amt_usd, t.pur_usd, t.decl, t.sh_pur, t.sh_dig, t.foreign_sh
  FROM cu c LEFT JOIN p USING(customer_id) LEFT JOIN t USING(customer_id)""")
print(d.shape)
print(d.groupby('segment')[['income','credit_score','nprod','nact','ntx','amt_usd','pur_usd','decl']].mean().round(3))
print(d.groupby('country')[['income','nprod','nact','ntx','amt_usd','decl','foreign_sh']].mean().round(3))
print(d.groupby('cstatus')[['nprod','nact','ntx','decl']].mean().round(3))
print(d[['income','credit_score','age','tenure','nprod','nact','ntx','amt_usd','pur_usd','decl','sh_dig','maxdpd']].corr(method='spearman').round(3).loc[['income','credit_score','age','tenure'],:])
cats = ['segment','country','occupation','marital_status','education_level','gender','cstatus']
X = d[['income','credit_score','age','tenure','mkt']+cats].copy()
for c in cats: X[c] = X[c].astype('category').cat.codes
X2 = X.copy(); X2['nact'] = d.nact; X2['nprod'] = d.nprod
groups = d.customer_id
gkf = GroupKFold(n_splits=5)
def cvr2(Xm, y, mask):
    m = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.1, categorical_features=[Xm.columns.get_loc(c) for c in cats])
    pred = cross_val_predict(m, Xm[mask], y[mask], cv=gkf, groups=groups[mask])
    return r2_score(y[mask], pred)
allm = np.ones(len(d), bool); has = d.ntx.values > 0
d['tx_per_act'] = np.where(d.nact>0, d.ntx/d.nact.replace(0,np.nan), np.nan)
for tgt, Xm, mask in [('nprod', X, allm), ('nact', X, allm), ('ntx', X, allm), ('ntx', X2, allm), ('tx_per_act', X, d.nact.values>0),
                      ('amt_usd', X2, has), ('pur_usd', X2, d.pur_usd.notna().values), ('decl', X2, has), ('sh_dig', X2, has), ('sh_pur', X2, has)]:
    print(f"R2 CV {tgt:12s} feats={'X+nact' if 'nact' in Xm else 'X'}: {cvr2(Xm, d[tgt].values, mask):.4f}")
