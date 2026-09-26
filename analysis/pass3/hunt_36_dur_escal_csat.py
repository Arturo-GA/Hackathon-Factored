"""hunt_36: ¿la duracion (o espera/sentimiento) predice escalamiento o el puntaje de encuesta, mas alla de resolved/categoria?
AUC univariante por categoria para escalated; CSAT/NPS/CES medio por resolved x cuartil de duracion; AUC dur->CSAT<=2 dentro de resolved.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_36_dur_escal_csat.py
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
z = con.execute("""SELECT cat, CAST(escalated AS INT) esc, CAST(resolved AS INT) res, dur, wait, sent_score FROM cc""").df()
print('(1) AUC -> escalated por categoria (dur, wait, sent_score, resolved)')
for c, g in z.groupby('cat'):
    out = {}
    for f in ['dur', 'wait', 'sent_score', 'res']:
        m = g[f].notna()
        out[f] = round(roc_auc_score(g.esc[m], g[f][m]), 4)
    print(c, 'n=', len(g), 'esc=', round(g.esc.mean(), 4), out)
s = con.execute("""SELECT s.survey_type, s.score, CAST(c.resolved AS INT) res, c.cat, c.dur, c.wait, c.sent_score, CAST(c.escalated AS INT) esc, s.resp_hours
  FROM sv s JOIN cc c USING (interaction_id)""").df()
print('(2) puntaje medio por tipo x resolved x cuartil de duracion')
s['dq'] = pd.qcut(s.dur, 4, labels=['q1', 'q2', 'q3', 'q4'])
print(s.groupby(['survey_type', 'res', 'dq'], observed=True).score.mean().unstack().round(3).to_string())
print('(3) AUC dentro de resolved: features -> puntaje bajo (<= mediana del tipo)')
for (t, r), g in s.groupby(['survey_type', 'res']):
    low = (g.score <= g.score.median()).astype(int)
    if low.nunique() < 2:
        print(t, r, 'puntaje constante', g.score.unique()[:5]); continue
    out = {}
    for f in ['dur', 'wait', 'sent_score', 'esc', 'resp_hours']:
        m = g[f].notna()
        out[f] = round(roc_auc_score(low[m], -g[f][m]), 4)
    print(t, 'resolved=', r, 'n=', len(g), 'valores=', sorted(g.score.unique().tolist()), out)
