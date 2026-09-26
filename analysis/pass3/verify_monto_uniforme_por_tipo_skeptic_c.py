# Parte C: ¿alguna variable (tx, cliente, producto) explica la posición u dentro del rango de su ttype?
# Para cada variable: eta^2 dentro de ttype (R^2 de medias de grupo), F y p; razón var_grupo/(1/12); min/max de u por grupo (rango distinto con igual media).
import duckdb, numpy as np, pandas as pd
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
K="(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
LO="(case t.ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)"
HI="(case t.ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Transfer' then 10000 when 'Payment' then 2000 when 'Deposit' then 5000 else 1000 end)"
BASE=f"""
with c as (select customer_id, segment, gender, document_type, occupation, education_level, marital_status, cstatus, mkt::int::varchar mkt, detected_accent cu_accent,
   country cu_country, state cu_state,
   ntile(10) over (partition by country order by income) inc_dec, ntile(10) over (order by credit_score) cs_dec,
   ntile(10) over (order by dob) age_dec, ntile(10) over (order by registration_date) reg_dec from cu),
p as (select product_id, ptype, pstatus, opening_channel, coalesce(app::int::varchar,'NA') app, currency pcur,
   ntile(10) over (partition by currency, ptype order by bal) bal_dec, ntile(10) over (partition by currency, ptype order by credit_limit) lim_dec,
   ntile(10) over (partition by ptype order by rate) rate_dec, ntile(10) over (order by opened) open_dec,
   case when dpd is null then 'NA' when dpd=0 then '0' when dpd<=30 then '1-30' when dpd<=90 then '31-90' else '90+' end dpd_b from pr)
select t.ttype, (t.amount/{K} - {LO})/({HI}-{LO}) u,
 t.channel, t.status, coalesce(t.code,'NA') code, t.fraud::int::varchar fraud,
 case when t.fscore is null then 'NA' else cast(least(floor(t.fscore/10),9) as varchar) end fs_dec,
 t.country, coalesce(t.country_raw,'NA') country_raw, coalesce(t.city,'NA') city, coalesce(t.tcat,'NA') tcat, coalesce(t.mcat,'NA') mcat,
 coalesce(t.merchant_name,'NA') merchant, coalesce(t.branch_id,'NA') branch, (t.lat is null)::int::varchar lat_null, (t.amount_usd is null)::int::varchar ausd_null,
 year(t.ts)::varchar yr, month(t.ts)::varchar mo, dayofweek(t.ts)::varchar dow, hour(t.ts)::varchar hr, minute(t.ts)::varchar mi, second(t.ts)::varchar sec, day(t.ts)::varchar dom,
 cast(datediff('day', cast(t.ts as date), t.process_date) as varchar) lag,
 c.segment, c.gender, c.document_type, c.occupation, c.education_level, c.marital_status, c.cstatus, c.mkt, c.cu_accent, c.cu_country, c.cu_state,
 c.inc_dec::varchar inc_dec, c.cs_dec::varchar cs_dec, c.age_dec::varchar age_dec, c.reg_dec::varchar reg_dec,
 p.ptype, p.pstatus, p.opening_channel, p.app, p.bal_dec::varchar bal_dec, p.lim_dec::varchar lim_dec, p.rate_dec::varchar rate_dec, p.open_dec::varchar open_dec, p.dpd_b,
 (c.cu_country <> t.country)::int::varchar foreign_tx
from tx t left join c using(customer_id) left join p using(product_id)
"""
VARS=['currency_dummy']
VARS=['channel','status','code','fraud','fs_dec','country','country_raw','city','tcat','mcat','merchant','branch','lat_null','ausd_null',
 'yr','mo','dow','hr','mi','sec','dom','lag','segment','gender','document_type','occupation','education_level','marital_status','cstatus','mkt','cu_accent',
 'cu_country','cu_state','inc_dec','cs_dec','age_dec','reg_dec','ptype','pstatus','opening_channel','app','bal_dec','lim_dec','rate_dec','open_dec','dpd_b','foreign_tx']
out=[]
chunk=8
for i in range(0,len(VARS),chunk):
    vs=VARS[i:i+chunk]
    gs=', '.join(f'(ttype, {v})' for v in vs)
    sel=', '.join(vs)
    df=con.execute(f"""with b as ({BASE}) select ttype, {sel}, grouping_id({sel}) gid, count(*) n, sum(u) s, sum(u*u) ss, min(u) mn, max(u) mx
      from b group by grouping sets ({gs})""").df()
    for j,v in enumerate(vs):
        # rows where only v is grouped (others null by grouping)
        mask=np.ones(len(df),bool)
        for k,w in enumerate(vs):
            if w!=v: mask &= df[w].isna().values if df[w].dtype==object else df[w].isna().values
        g=df[mask & ((df.gid.values>>(len(vs)-1-j))&1==0)].copy()
        # if v itself was null-valued it's fine because we coalesced to 'NA'
        N=g.n.sum(); T=g.groupby('ttype').agg(n=('n','sum'),s=('s','sum'),ss=('ss','sum'))
        corr=(T.s**2/T.n).sum()
        SSB=(g.s**2/g.n).sum()-corr; SST=g.ss.sum()-corr; SSW=SST-SSB
        G=len(g); df1=G-len(T); df2=N-G
        F=(SSB/df1)/(SSW/df2) if df1>0 else np.nan
        pF=stats.f.sf(F,df1,df2) if df1>0 else np.nan
        big=g[g.n>=2000].copy()
        big['m']=big.s/big.n; big['var']=big.ss/big.n-big.m**2
        big['tm']=big.ttype.map(T.s/T.n)
        big['z']=(big.m-big.tm)/np.sqrt(1/12/big.n)
        out.append(dict(var=v, groups=G, N=int(N), eta2=SSB/SST, F=F, df1=df1, p=pF,
          max_dmean=(big.m-big.tm).abs().max() if len(big) else np.nan, max_absz=big.z.abs().max() if len(big) else np.nan,
          var_ratio_min=(big['var']*12).min() if len(big) else np.nan, var_ratio_max=(big['var']*12).max() if len(big) else np.nan,
          max_min_u=big.mn.max() if len(big) else np.nan, min_max_u=big.mx.min() if len(big) else np.nan, n_big=len(big)))
    print('ok', vs, flush=True)
r=pd.DataFrame(out)
r['p_bonf']=np.minimum(r.p*len(r),1)
pd.set_option('display.width',250)
print(r.sort_values('eta2',ascending=False).to_string(index=False, float_format=lambda x: f'{x:.4g}'))
print('\nmax eta2 =', r.eta2.max(), ' variables con p_bonf<0.05:', r.loc[r.p_bonf<0.05,'var'].tolist())
