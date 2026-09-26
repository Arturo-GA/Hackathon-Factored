"""hunt_39: regla de puntaje de encuestas: score | (tipo, resolved) -> distribucion exacta; categorias NPS; q1-q3 y comentario vs resolved.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_39_survey_rule.py
"""
import duckdb
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='300MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
d = con.execute("""SELECT s.survey_type, c.resolved, s.score, count(*) n FROM sv s JOIN cc c USING (interaction_id) GROUP BY 1,2,3""").df()
t = d.pivot_table(index=['survey_type', 'resolved'], columns='score', values='n', fill_value=0)
print(t.to_string()); print((t.div(t.sum(1), axis=0)).round(3).to_string())
print(con.execute("""SELECT survey_type, coalesce(nps_category,'∅') cat, min(score) mn, max(score) mx, count(*) n FROM sv GROUP BY 1,2 ORDER BY 1,2""").df().to_string())
print('NPS estandar = %promotores(9-10) - %detractores(0-6):', con.execute("""SELECT 100*(avg(CASE WHEN score>=9 THEN 1.0 ELSE 0 END) - avg(CASE WHEN score<=6 THEN 1.0 ELSE 0 END)) FROM sv WHERE survey_type='NPS'""").fetchone())
print('q1/q2/q3 medias por resolved (¿dependen?):')
print(con.execute("""SELECT c.resolved, avg(q1) q1, avg(q2) q2, avg(q3) q3, count(q1) n1 FROM sv s JOIN cc c USING (interaction_id) GROUP BY 1""").df().round(3).to_string())
print(con.execute("""SELECT c.resolved, coalesce(s.comment_sentiment,'∅') cs, count(*) n FROM sv s JOIN cc c USING (interaction_id) GROUP BY 1,2 ORDER BY 1,2""").df().pivot(index='resolved', columns='cs', values='n').to_string())
print('corr(q1, score) por tipo:', con.execute("SELECT survey_type, corr(q1, score) FROM sv GROUP BY 1").fetchall())
