"""H5/H6: status y code vs variables categoricas (V de Cramer), nulos de code, tasas por nivel."""
import duckdb, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from scipy.stats import chi2_contingency
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
def cramer(ct):
    ct = ct.loc[ct.sum(1)>0, ct.sum(0)>0]
    chi2 = chi2_contingency(ct.values, correction=False)[0]
    n = ct.values.sum(); k = min(ct.shape)-1
    return np.sqrt(chi2/(n*k)) if k>0 else np.nan
feats = {
 'ttype':'ttype','channel':'channel','mcat':"coalesce(mcat,'(nulo)')",'tcat':"coalesce(tcat,'(nulo)')",'currency':'currency',
 'country':'country','hour':'hour(ts)','dow':'dayofweek(ts)','year':'year(ts)','month':'month(ts)',
 'amt_dec':"currency||'_'||cast(floor(log10(greatest(amount,0.01))) as varchar)",
 'merchant_null':'merchant_name is null','branch_null':'branch_id is null','latnull':'lat is null',
 'amtusd_null':'amount_usd is null','fscore_null':'fscore is null','fraud':'fraud',
 'lag_proc':"least(date_diff('day', cast(ts as date), process_date),5)",
 'country_raw':'country_raw','sec0':'second(ts)=0',
}
rows=[]
for name, expr in feats.items():
    df = q(f"""select {expr} f, status, coalesce(code,'NA') code, count(*) n from tx group by all""")
    ct_s = df.pivot_table(index='f', columns='status', values='n', aggfunc='sum', fill_value=0)
    nonapp = df[df.status!='Approved']
    ct_c = nonapp.pivot_table(index='f', columns='code', values='n', aggfunc='sum', fill_value=0)
    ct_null = df.assign(isnull=df.code=='NA').pivot_table(index='f', columns='isnull', values='n', aggfunc='sum', fill_value=0)
    dr = ct_s.get('Declined',0)/ct_s.sum(1)
    rows.append((name, ct_s.shape[0], cramer(ct_s), cramer(ct_c), cramer(ct_null), dr.min(), dr.max()))
res = pd.DataFrame(rows, columns=['feat','niveles','V_status','V_code|noAprob','V_codeNulo','decl_min','decl_max'])
print(res.round(4).to_string())
# nulos de code por estado
print(q("""select status, avg(case when code is null then 1 else 0 end) null_rate, count(*) n from tx group by 1""").to_string())
# lag process_date por estado
print(q("""select status, avg(date_diff('day', cast(ts as date), process_date)) lag_mean,
 avg(case when process_date> cast(ts as date) then 1 else 0 end) lag_pos, avg(case when process_date< cast(ts as date) then 1 else 0 end) lag_neg from tx group by 1""").to_string())
