"""Tasa de fraude por atributos categóricos de tx, producto y cliente (razón de tasas vs base)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width',200)
con = connect()
print(q(con,"SELECT count(*) n, sum(fraud::int) f, sum(CASE WHEN fscore>30 THEN 1 ELSE 0 END) f30, sum(CASE WHEN fraud AND fscore>30 THEN 1 ELSE 0 END) f30t FROM tx"))
con.execute("""CREATE TEMP TABLE t AS SELECT t.fraud, t.ttype, t.tcat, t.channel, t.currency, t.status, coalesce(t.code,'NULL') code, t.mcat,
  t.country, (t.country_raw) craw, p.ptype, p.pstatus, p.opening_channel, c.segment, c.cstatus, c.gender, c.country ccountry, c.occupation,
  c.education_level edu, c.marital_status ms, CASE WHEN c.mkt THEN 'y' ELSE 'n' END mkt,
  (date_diff('year', c.dob, t.ts::date)//10)*10 age_dec,
  (date_diff('day', c.registration_date, t.ts::date)//365) ten_y,
  (date_diff('day', p.opened, t.ts::date)//180) prod_age_hy,
  hour(t.ts) hr, dayofweek(t.ts) dow, day(t.ts) dom, year(t.ts) yr, month(t.ts) mo,
  (t.merchant_name IS NULL) no_merch, (t.lat IS NULL) no_geo, (t.branch_id IS NULL) no_branch, (t.amount_usd IS NULL) no_usd, (t.fscore IS NULL) no_score
  FROM tx t LEFT JOIN pr p USING(product_id) LEFT JOIN cu c ON t.customer_id=c.customer_id""")
base = q(con,"SELECT avg(fraud::int) FROM t").iloc[0,0]
print('base', base)
cols = ['ttype','tcat','channel','currency','status','code','mcat','country','craw','ptype','pstatus','opening_channel','segment','cstatus','gender','ccountry','occupation','edu','ms','mkt','age_dec','ten_y','prod_age_hy','hr','dow','dom','yr','mo','no_merch','no_geo','no_branch','no_usd','no_score']
rows=[]
for c in cols:
    d = q(con, f"SELECT {c}::VARCHAR v, count(*) n, sum(fraud::int) f FROM t GROUP BY 1")
    d['rate']=d.f/d.n; d['rr']=d.rate/base
    dd = d[d.n>=20000]
    rows.append((c, len(d), dd.rr.min(), dd.rr.max(), dd.loc[dd.rr.idxmax(),'v'] if len(dd) else None, dd.loc[dd.rr.idxmin(),'v'] if len(dd) else None))
    if (dd.rr.max()>=1.3 or dd.rr.min()<=0.77) and len(dd):
        print('\n==',c); print(dd.sort_values('rr').to_string(index=False))
print(pd.DataFrame(rows, columns=['col','k','rr_min','rr_max','v_max','v_min']).to_string())
