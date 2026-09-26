# ids_23: estructura del final de cada fila de tx en el flujo MT: [..., u_fraude, u_score, (0/1/3 sorteos), ID].
# ¿qué determina los sorteos entre fraud_score y el ID? (canal, lat/lon, estado...) y verificación is_fraud <=> u<0.001 con desfase fijo
import sys, numpy as np, duckdb, pandas as pd
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words, chars_per_word, AMAP
N=400000
w = words(N*86+5000); c = chars_per_word(w); del_ = None
def U(p): return ((w[p]>>5).astype(np.float64)*67108864.0 + (w[p+1]>>6).astype(np.float64))/9007199254740992.0
con = duckdb.connect(); con.execute("SET memory_limit='500MB'; SET threads=2")
df = con.execute(f"""select transaction_id, is_fraud='True' fraud, try_cast(fraud_score as double) fs, channel ch, transaction_type tt, transaction_status st,
   response_code code, currency cur, latitude is null lat_null, merchant_name is null mer_null, branch_id is null br_null, amount_usd is null usd_null
   from read_parquet('data/bronze/transactions.parquet', file_row_number=true) where file_row_number<{N} order by file_row_number""").fetchdf()
pos=np.full(len(df),-1,dtype=np.int64); prev=0
for i,v in enumerate(df.transaction_id.values):
    e=np.array([AMAP[x] for x in v[4:]],dtype=np.int8); seg=c[prev:prev+700]
    cand=np.nonzero(seg[:660]==e[0])[0]
    for j in range(1,20):
        cand=cand[seg[cand+2*j]==e[j]]
        if len(cand)==0: break
    if len(cand): pos[i]=prev+cand[0]; prev=pos[i]+1
df['pos']=pos; print('ubicadas', (pos>=0).mean(), 'filas', len(df), 'fraudes', int(df.fraud.sum()))
# offset del score (solo filas con fs visible)
offs=np.full(len(df),-1)
for d in [2,4,6,8,10]:
    sc=np.where(df.fraud.values,100.0,30.0); m=(offs<0)&df.fs.notna().values&(np.abs(U(df.pos.values-d)*sc-df.fs.fillna(-9).values)<0.006)
    offs[m]=d
df['off']=offs
print(pd.crosstab(df.ch, df.off).to_string())
print(pd.crosstab(df.tt, df.off).to_string())
# verificación de is_fraud con el sorteo previo al score: en filas con off conocido
k = df[df.off>0]
uf = U(k.pos.values - k.off.values - 2)
print('filas con off conocido', len(k), 'fraudes', int(k.fraud.sum()))
print('P(fraude | u<0.001)=', k.fraud[uf<0.001].mean(), 'n=', int((uf<0.001).sum()), ' P(fraude | u>=0.001)=', k.fraud[uf>=0.001].mean(), 'max u fraude=', uf[k.fraud.values].max())
df.to_parquet('C:/Users/Arturo/AppData/Local/Temp/claude/C--Users-Arturo-Documents-Factored-Hackathon/dd019af3-3739-4a2c-98c4-2235ab816d32/scratchpad/tx400k_pos.parquet')

# --- filas con fraud_score NULO en canales digitales (App/Web/Transfer: sin sorteos de lat/lon, desfase fijo 2): ¿el sorteo existe igual y decide el fraude?
m = df.fs.isna() & df.ch.isin(['App','Web','Transfer'])
k2 = df[m]; uf2 = U(k2.pos.values - 4)
print('fs nulo digital: filas', len(k2), 'fraudes', int(k2.fraud.sum()), 'P(fraude|u<0.001)=', k2.fraud[uf2<0.001].mean(), 'n=', int((uf2<0.001).sum()), 'P(fraude|u>=0.001)=', k2.fraud[uf2>=0.001].mean())
