"""hunt_30: detalle de dependencias del barrido cc (hunt_29): followup vs resolved, sentimiento por categoria,
duracion por resolved dentro de categoria, tipo de encuesta vs canal de envio.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_30_cc_rules_detail.py
"""
import duckdb
import pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
q = lambda s: con.execute(s).df()
print('(1) followup x resolved (completo)')
print(q("""SELECT resolved, followup, count(*) n FROM cc GROUP BY 1,2 ORDER BY 1,2""").to_string())
print(q("""SELECT cat, avg(CASE WHEN followup THEN 1.0 ELSE 0 END) FILTER (WHERE resolved) fu_if_res,
  avg(CASE WHEN followup THEN 1.0 ELSE 0 END) FILTER (WHERE NOT resolved) fu_if_notres, count(*) n FROM cc GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('(2) sentimiento por categoria (% fila) y sent_score medio')
d = q("""SELECT cat, sent, count(*) n FROM cc GROUP BY 1,2""")
print((d.pivot(index='cat', columns='sent', values='n').pipe(lambda x: x.div(x.sum(1), axis=0))).round(3).to_string())
print(q("""SELECT cat, avg(sent_score) ss, min(sent_score) mn, max(sent_score) mx FROM cc GROUP BY 1 ORDER BY 2""").round(3).to_string())
print('sent_score por sent (rangos):')
print(q("""SELECT sent, count(*) n, min(sent_score) mn, max(sent_score) mx, avg(sent_score) av FROM cc GROUP BY 1 ORDER BY 4""").round(3).to_string())
print('(3) duracion por categoria x resolved (llamadas)')
print(q("""SELECT cat, resolved, count(dur) n, median(dur) med, avg(dur) av, min(dur) mn, max(dur) mx FROM cc WHERE dur IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").round(1).to_string())
print('(4) tipo de encuesta x canal de envio')
print(q("""SELECT survey_type, send_channel, count(*) n FROM sv GROUP BY 1,2""").pivot(index='survey_type', columns='send_channel', values='n').to_string())
print('(5) resp_hours y campaign_response_rate por tipo/canal')
print(q("""SELECT survey_type, send_channel, avg(resp_hours) rh, min(resp_hours) mn, max(resp_hours) mx, avg(campaign_response_rate) crr FROM sv GROUP BY 1,2 ORDER BY 1,2""").round(2).to_string())
print('(6) escalated x resolved / followup')
print(q("""SELECT escalated, resolved, followup, count(*) n FROM cc GROUP BY 1,2,3 ORDER BY 1,2,3""").to_string())
