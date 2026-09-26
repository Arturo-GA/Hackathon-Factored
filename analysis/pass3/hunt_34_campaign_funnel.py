"""hunt_34: embudo de campanas (cs). Regla: delivered ~ Bernoulli(0.94) igual en todo canal; opened | delivered con tasa fija
por canal (SMS 0.5, Push 0.4, Email 0.3; WhatsApp/Voice sin tracking); clicked | opened = 0.2; conv | clicked = 0.1.
Verifica implicaciones (click => opened, conv => clicked, open_ts/conv_ts), nulos de opened, independencia de segmento/consentimiento/campana,
y que 'conversion alguna por cliente' (AUC 0.59 en hunt_04) es exposicion (n envios por canal).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_34_campaign_funnel.py
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
print('(1) embudo por canal')
print(q("""SELECT send_channel, count(*) n, avg(CASE WHEN delivered THEN 1.0 ELSE 0 END) deliv,
  avg(CASE WHEN opened IS NULL THEN 1.0 ELSE 0 END) opened_null,
  avg(CASE WHEN opened THEN 1.0 ELSE 0 END) FILTER (WHERE delivered) open_g_deliv,
  avg(CASE WHEN clicked THEN 1.0 ELSE 0 END) FILTER (WHERE opened) click_g_open,
  avg(CASE WHEN conv THEN 1.0 ELSE 0 END) FILTER (WHERE clicked) conv_g_click,
  count(*) FILTER (WHERE clicked AND NOT coalesce(opened,false)) click_sin_open,
  count(*) FILTER (WHERE conv AND NOT clicked) conv_sin_click,
  count(*) FILTER (WHERE opened AND NOT delivered) open_sin_deliv,
  avg(CASE WHEN open_ts IS NULL THEN 1.0 ELSE 0 END) FILTER (WHERE opened) open_ts_null_si_open,
  count(*) FILTER (WHERE open_ts IS NOT NULL AND NOT coalesce(opened,false)) open_ts_sin_open
  FROM cs GROUP BY 1 ORDER BY open_g_deliv DESC""").round(4).to_string())
print('(2) opened NULL: por delivered x canal')
print(q("""SELECT send_channel, delivered, count(*) n, avg(CASE WHEN opened IS NULL THEN 1.0 ELSE 0 END) opened_null FROM cs GROUP BY 1,2 ORDER BY 1,2""").round(4).to_string())
print('(3) send_status vs delivered / failure_reason por canal')
print(q("""SELECT send_channel, send_status, coalesce(failure_reason,'∅') fr, count(*) n FROM cs GROUP BY 1,2,3 ORDER BY 1,2,3""").to_string())
print('(4) tasas por segmento x mkt x canal SMS (independencia)')
print(q("""SELECT c.segment, c.mkt, avg(CASE WHEN s.opened THEN 1.0 ELSE 0 END) FILTER (WHERE s.delivered AND s.send_channel='SMS') open_sms,
  avg(CASE WHEN s.clicked THEN 1.0 ELSE 0 END) FILTER (WHERE s.opened) click_g_open, count(*) n
  FROM cs s JOIN cu c USING (customer_id) GROUP BY 1,2 ORDER BY 1,2""").round(4).to_string())
print('(5) variacion entre campanas (open | delivered, SMS) vs binomial')
g = q("""SELECT campaign_id, count(*) n, sum(CASE WHEN opened THEN 1 ELSE 0 END) k FROM cs WHERE delivered AND send_channel='SMS' GROUP BY 1""")
p = g.k.sum() / g.n.sum()
print('campanas', len(g), 'p', round(p, 4), 'dispersion obs/binomial', round((((g.k - g.n * p) ** 2).sum()) / ((g.n * p * (1 - p)).sum()), 3))
print('(6) conversion alguna por cliente ~ exposicion por canal')
c = q("""SELECT customer_id, max(CASE WHEN conv THEN 1 ELSE 0 END) y, count(*) n,
  sum(CASE WHEN send_channel='SMS' THEN 1 ELSE 0 END) n_sms, sum(CASE WHEN send_channel='Push' THEN 1 ELSE 0 END) n_push,
  sum(CASE WHEN send_channel='Email' THEN 1 ELSE 0 END) n_email FROM cs GROUP BY 1""")
pc = {'sms': 0.94 * 0.5 * 0.2 * 0.1, 'push': 0.94 * 0.4 * 0.2 * 0.1, 'email': 0.94 * 0.3 * 0.2 * 0.1}
c['pf'] = 1 - (1 - pc['sms']) ** c.n_sms * (1 - pc['push']) ** c.n_push * (1 - pc['email']) ** c.n_email
print('clientes', len(c), 'tasa', round(c.y.mean(), 4), ' AUC n envios=', round(roc_auc_score(c.y, c.n), 4),
      ' AUC formula por canal=', round(roc_auc_score(c.y, c.pf), 4), ' prob media formula=', round(c.pf.mean(), 4))
print('(7) conv_value y conv_ts')
print(q("""SELECT count(*) n, min(conv_value) mn, max(conv_value) mx, avg(conv_value) av, min(epoch(conv_ts - ts)/3600) h_min, max(epoch(conv_ts - ts)/3600) h_max,
  min(epoch(open_ts - ts)/3600) o_min, max(epoch(open_ts - ts)/3600) o_max FROM cs WHERE conv""").round(2).to_string())
