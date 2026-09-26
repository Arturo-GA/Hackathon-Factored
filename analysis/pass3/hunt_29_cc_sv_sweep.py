"""hunt_29: barrido de V de Cramer dentro del call center (cc, muestra 300k) con columnas derivadas
(nulos, buckets) + tiene_encuesta / tipo y canal de encuesta (join sv por interaction_id) + transcript.
Objetivo: reglas deterministas ocultas (itype->canal, grabacion/transcript, encuesta) y sesgo de respuesta de encuestas.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_29_cc_sv_sweep.py
"""
import itertools
import duckdb
import numpy as np
import pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df = con.execute("""
SELECT c.itype, c.channel, c.cat, CAST(c.resolved AS VARCHAR) resolved, CAST(c.followup AS VARCHAR) followup, c.sent,
  CAST(c.escalated AS VARCHAR) escalated, coalesce(c.c_acc,'∅') c_acc, coalesce(c.a_acc,'∅') a_acc,
  CAST(c.has_transcript AS VARCHAR) has_tr, CAST(c.has_recording AS VARCHAR) has_rec,
  CASE WHEN c.dur IS NULL THEN 'null' ELSE CAST(ntile(5) OVER (ORDER BY c.dur) AS VARCHAR) END dur_q,
  CASE WHEN c.wait IS NULL THEN 'null' ELSE CAST(ntile(5) OVER (ORDER BY c.wait) AS VARCHAR) END wait_q,
  CASE WHEN c.mentioned_products IS NULL THEN 'null' ELSE 'val' END mentioned,
  CASE WHEN s.survey_id IS NULL THEN 'no' ELSE 'yes' END has_sv, coalesce(s.survey_type,'∅') sv_type, coalesce(s.send_channel,'∅') sv_chan,
  CASE WHEN t.transcript_id IS NULL THEN 'no' ELSE 'yes' END tr_row,
  CAST(dayofweek(c.ts) AS VARCHAR) dow, cu.country, cu.segment
FROM (SELECT * FROM cc USING SAMPLE 300000 ROWS) c
LEFT JOIN sv s USING (interaction_id)
LEFT JOIN (SELECT interaction_id, min(transcript_id) transcript_id FROM tr GROUP BY 1) t USING (interaction_id)
LEFT JOIN cu ON cu.customer_id = c.customer_id
""").df()
print('filas', len(df))


def cv(a, b):
    ct = pd.crosstab(a, b).values.astype(float)
    n = ct.sum(); r, k = ct.shape
    if r < 2 or k < 2:
        return np.nan
    e = np.outer(ct.sum(1), ct.sum(0)) / n
    chi2 = ((ct - e) ** 2 / e).sum()
    phi2c = max(0, chi2 / n - (k - 1) * (r - 1) / (n - 1))
    rc = r - (r - 1) ** 2 / (n - 1); kc = k - (k - 1) ** 2 / (n - 1)
    return np.sqrt(phi2c / min(kc - 1, rc - 1))


rows = [(a, b, cv(df[a], df[b])) for a, b in itertools.combinations(df.columns, 2)]
r = pd.DataFrame(rows, columns=['a', 'b', 'V']).sort_values('V', ascending=False)
print('pares', len(r), ' V>=0.9:', int((r.V >= 0.9).sum()), ' 0.02<=V<0.9:', int(((r.V >= 0.02) & (r.V < 0.9)).sum()), ' V<0.02:', int((r.V < 0.02).sum()))
print(r[r.V >= 0.02].to_string(index=False, float_format=lambda x: f'{x:.4f}'))
for a, b in [('itype', 'channel'), ('itype', 'has_rec'), ('itype', 'has_tr'), ('itype', 'wait_q'), ('itype', 'dur_q'), ('has_tr', 'tr_row'),
             ('itype', 'sv_chan'), ('has_sv', 'resolved')]:
    print(f'--- {a} x {b}'); print(pd.crosstab(df[a], df[b]).to_string())
print('P(tiene encuesta) por resolved/cat/itype/escalated/sent:')
for c in ['resolved', 'cat', 'itype', 'escalated', 'sent', 'channel', 'country', 'segment']:
    print(c, df.groupby(c).has_sv.apply(lambda s: round((s == 'yes').mean(), 4)).to_dict())
