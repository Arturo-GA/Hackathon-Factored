"""hunt_10: reglas segment -> credit_score / income (hallazgo del GBM hunt_04: R2 0.73 y 0.84 explicados por segment)."""
import duckdb
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
INC = "income / CASE country WHEN 'Colombia' THEN 4000.0 WHEN 'Argentina' THEN 350.0 ELSE 17.0 END"
print(con.execute(f"""
SELECT segment, count(*) n, min(credit_score) cs_min, quantile_cont(credit_score,0.01) cs_p01, median(credit_score) cs_med,
  quantile_cont(credit_score,0.99) cs_p99, max(credit_score) cs_max, stddev(credit_score) cs_sd,
  min({INC}) inc_min, quantile_cont({INC},0.01) inc_p01, median({INC}) inc_med, quantile_cont({INC},0.99) inc_p99, max({INC}) inc_max,
  avg(CASE WHEN credit_score IS NULL THEN 1 ELSE 0 END) cs_null, avg(CASE WHEN income IS NULL THEN 1 ELSE 0 END) inc_null
FROM cu GROUP BY 1 ORDER BY cs_med""").df().to_string(float_format=lambda x: f'{x:.1f}'))
# income por pais en moneda local
print(con.execute("""SELECT country, segment, min(income), median(income), max(income) FROM cu GROUP BY 1,2 ORDER BY 1,4""").df().to_string())
# accuracy de una regla: clasificar segmento por umbrales de credit_score
df = con.execute(f"SELECT segment, credit_score cs, {INC} inc, date_diff('day', dob, DATE '2026-06-17')/365.25 age, occupation FROM cu WHERE credit_score IS NOT NULL").df()
from sklearn.tree import DecisionTreeClassifier, export_text
for cols in (['cs'], ['inc'], ['cs', 'inc']):
    m = df.dropna(subset=cols)
    t = DecisionTreeClassifier(max_depth=3, random_state=0).fit(m[cols], m.segment)
    print(cols, 'acc arbol prof3:', round(t.score(m[cols], m.segment), 4), 'n=', len(m))
    print(export_text(t, feature_names=cols, decimals=1))
print(pd.crosstab(df.segment, pd.cut(df.age, [0, 18, 25, 30, 40, 60, 120]), normalize='index').round(3))
print(pd.crosstab(df.occupation.fillna('∅'), df.segment, normalize='index').round(3).head(25))
# income vs credit_score dentro de segmento
print(df.groupby('segment').apply(lambda g: g[['cs', 'inc']].corr().iloc[0, 1]))
