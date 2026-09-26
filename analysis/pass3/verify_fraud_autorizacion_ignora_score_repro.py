"""Verificación independiente: ¿status/code son independientes de fraud y fscore?"""
import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def show(sql):
    df = con.execute(sql).df(); print(df.to_string(index=False)); print(); return df

print("== Grupos: legítimas / fraude score>30 / fraude score<=30 o nulo ==")
show("""SELECT CASE WHEN NOT fraud THEN 'legit' WHEN fscore>30 THEN 'fraud_hi' ELSE 'fraud_lo_null' END g,
 count(*) n,
 round(100*avg((status='Approved')::int),2) appr, round(100*avg((status='Declined')::int),2) decl,
 round(100*avg((status='Pending')::int),2) pend, round(100*avg((status='Reversed')::int),3) rev,
 sum((status='Approved')::int) n_appr, sum((status='Reversed')::int) n_rev
 FROM tx GROUP BY 1 ORDER BY 1""")

print("== fscore distribución por fraud ==")
show("""SELECT fraud, count(*) n, count(fscore) n_score, round(min(fscore),2) mn, round(max(fscore),2) mx, round(avg(fscore),2) av,
 sum((fscore>30)::int) gt30, sum((fscore>=50)::int) ge50 FROM tx GROUP BY 1""")

print("== Tramos de fscore (todos) ==")
show("""SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<10 THEN '00-10' WHEN fscore<20 THEN '10-20' WHEN fscore<30 THEN '20-30'
 WHEN fscore<50 THEN '30-50' ELSE '50-100' END tramo, count(*) n, sum(fraud::int) nf,
 round(100*avg((status='Declined')::int),2) decl, round(100*avg((status='Reversed')::int),2) rev, round(100*avg((status='Pending')::int),2) pend,
 round(100*avg((code='00')::int),2) c00, round(100*avg((code='05')::int),2) c05, round(100*avg((code='14')::int),2) c14,
 round(100*avg((code='51')::int),2) c51, round(100*avg((code='54')::int),2) c54, round(100*avg((code IS NULL)::int),2) cnull
 FROM tx GROUP BY 1 ORDER BY 1""")

print("== code x fraud ==")
show("""SELECT coalesce(code,'NULL') code, count(*) FILTER (WHERE NOT fraud) n_leg, count(*) FILTER (WHERE fraud) n_fr,
 round(100.0*count(*) FILTER (WHERE NOT fraud)/sum(count(*) FILTER (WHERE NOT fraud)) over(),2) pct_leg,
 round(100.0*count(*) FILTER (WHERE fraud)/sum(count(*) FILTER (WHERE fraud)) over(),2) pct_fr
 FROM tx GROUP BY 1 ORDER BY 1""")

print("== status x code (fraude vs legit) ==")
show("""SELECT status, coalesce(code,'NULL') code, count(*) FILTER (WHERE NOT fraud) n_leg, count(*) FILTER (WHERE fraud) n_fr FROM tx GROUP BY 1,2 ORDER BY 1,2""")

# Chi2 / Cramér V status x fraud y code x fraud
from scipy.stats import chi2_contingency
for col in ['status', "coalesce(code,'NULL')"]:
    df = con.execute(f"SELECT {col} k, fraud, count(*) n FROM tx GROUP BY 1,2").df()
    ct = df.pivot(index='k', columns='fraud', values='n').fillna(0).values
    chi2, p, dof, _ = chi2_contingency(ct)
    n = ct.sum(); v = np.sqrt(chi2/(n*(min(ct.shape)-1)))
    print(f"{col} x fraud: chi2={chi2:.1f} p={p:.3g} V={v:.5f}")
# status x tramo fscore V
df = con.execute("""SELECT status k, CASE WHEN fscore IS NULL THEN 'nulo' ELSE (floor(fscore/10))::VARCHAR END b, count(*) n FROM tx GROUP BY 1,2""").df()
ct = df.pivot(index='k', columns='b', values='n').fillna(0).values
chi2, p, dof, _ = chi2_contingency(ct); n=ct.sum()
print(f"status x decil fscore: chi2={chi2:.1f} p={p:.3g} V={np.sqrt(chi2/(n*(min(ct.shape)-1))):.5f}")

print("\n== AUC de fscore para Declined vs no (solo con score) y fraud por status ==")
show("""WITH s AS (SELECT fscore, (status='Declined') y FROM tx WHERE fscore IS NOT NULL),
 r AS (SELECT y, rank() OVER (ORDER BY fscore) rk FROM s)
 SELECT (sum(rk) FILTER (WHERE y) - count(*) FILTER (WHERE y)*(count(*) FILTER (WHERE y)+1)/2.0)
   / (count(*) FILTER (WHERE y)::DOUBLE * count(*) FILTER (WHERE NOT y)) auc_fscore_declined FROM r""")
show("""SELECT status, count(*) n, sum(fraud::int) nf, round(1000*avg(fraud::int),3) fraud_permil, round(avg(fscore),3) avg_fscore FROM tx GROUP BY 1 ORDER BY 1""")

print("== correlaciones fscore (no fraude) ==")
show("""SELECT corr(fscore, ln(1+amount)) r_logamt, corr(fscore, hour(ts)) r_hour FROM tx WHERE NOT fraud AND fscore IS NOT NULL""")

print("== fraudes aprobados con fscore>30 y tasa mensual ==")
show("""SELECT count(*) n, count(DISTINCT date_trunc('month', ts)) meses,
 round(count(*)/ (date_diff('day', min(ts)::DATE, max(ts)::DATE)/30.4375),1) por_mes FROM tx WHERE fraud AND fscore>30 AND status='Approved'""")
show("""SELECT min(ts), max(ts), date_diff('day', min(ts)::DATE, max(ts)::DATE) dias FROM tx""")
print("== ¿fscore>30 alguna vez legit? ==")
show("""SELECT fraud, sum((fscore>30)::int) gt30, sum((fscore>30 AND fscore<50)::int) b30_50 FROM tx GROUP BY 1""")
