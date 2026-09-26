"""Verificador escéptico (reintento, parte d): código x tramo de fscore dentro de no-Approved; unicidad de transaction_id."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency
from fraud_00_common import connect, q
con = connect()
print(q(con, "SELECT count(*) n, count(DISTINCT transaction_id) n_ids FROM tx").to_string(index=False))
d = q(con, """SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=10 THEN '00-10' WHEN fscore<=20 THEN '10-20' WHEN fscore<=30 THEN '20-30' ELSE '>30' END b,
  coalesce(code,'NULL') code, count(*) n FROM tx WHERE status<>'Approved' GROUP BY ALL""")
ct = d.pivot(index='b', columns='code', values='n').fillna(0)
print((ct.div(ct.sum(axis=1), axis=0)*100).round(2).assign(N=ct.sum(axis=1)).to_string())
chi2, p, dof, _ = chi2_contingency(ct.values, correction=False)
print(f'code x tramo fscore | no-Approved: chi2={chi2:.2f} gl={dof} p={p:.3f} V={np.sqrt(chi2/(ct.values.sum()*(min(ct.shape)-1))):.5f}')
