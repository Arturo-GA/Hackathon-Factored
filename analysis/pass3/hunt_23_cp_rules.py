"""hunt_23: barrido de V de Cramer + reglas dentro de reclamos (cp): status -> timestamps, sla vs rdays/priority,
resolution/compensation/res_sat, repeat vs historial, priority vs case_type/category/rchan, subcategory vs category.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_23_cp_rules.py
"""
import itertools
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.metrics import normalized_mutual_info_score
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
df = con.execute("""
SELECT case_type, category, coalesce(subcategory,'∅') subcategory, rchan, priority, status, CAST(sla AS VARCHAR) sla, CAST(repeat AS VARCHAR) rep,
  coalesce(currency,'∅') currency,
  CASE WHEN claimed IS NULL THEN 'null' ELSE 'val' END claimed_n,
  CASE WHEN affected_product_id IS NULL THEN 'null' ELSE 'val' END aff_n,
  CASE WHEN related_branch_id IS NULL THEN 'null' ELSE 'val' END branch_n,
  CASE WHEN assigned_agent_id IS NULL THEN 'null' ELSE 'val' END agent_n,
  CASE WHEN assigned_at IS NULL THEN 'null' ELSE 'val' END assigned_n,
  CASE WHEN first_resp_at IS NULL THEN 'null' ELSE 'val' END fresp_n,
  CASE WHEN resolved_at IS NULL THEN 'null' ELSE 'val' END resolved_n,
  CASE WHEN closed_at IS NULL THEN 'null' ELSE 'val' END closed_n,
  coalesce(CAST(least(rdays, 31) AS VARCHAR), '∅') rdays_s,
  coalesce(left(resolution, 18), '∅') resol,
  CASE WHEN compensation IS NULL THEN 'null' ELSE 'val' END comp_n,
  coalesce(CAST(res_sat AS VARCHAR),'∅') res_sat,
  CAST(year(ts) AS VARCHAR) yr,
  CAST(dayofweek(ts) AS VARCHAR) dow
FROM cp""").df()
cols = list(df.columns)
rows = []
for a, b in itertools.combinations(cols, 2):
    ct = pd.crosstab(df[a], df[b])
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        continue
    chi2 = chi2_contingency(ct, correction=False)[0]
    v = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
    rows.append((a, b, ct.shape[0], ct.shape[1], v, normalized_mutual_info_score(df[a], df[b])))
r = pd.DataFrame(rows, columns=['a', 'b', 'ka', 'kb', 'V', 'NMI']).sort_values('V', ascending=False)
print('pares:', len(r))
print(r.head(45).to_string(index=False, float_format=lambda x: f'{x:.4f}'))
print('... pares con V<0.02:', int((r.V < 0.02).sum()))
for a, b in [('status', 'resolved_n'), ('status', 'closed_n'), ('status', 'agent_n'), ('status', 'fresp_n'), ('status', 'res_sat'),
             ('status', 'comp_n'), ('resol', 'comp_n'), ('status', 'sla'), ('priority', 'sla'), ('case_type', 'claimed_n'),
             ('category', 'subcategory'), ('category', 'priority'), ('rchan', 'priority'), ('case_type', 'priority')]:
    print(f'--- {a} x {b}')
    print(pd.crosstab(df[a], df[b]).to_string())
