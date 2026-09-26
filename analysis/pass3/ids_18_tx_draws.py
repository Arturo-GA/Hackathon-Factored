# ids_18: nº de palabras MT consumidas por cada transacción (gap entre IDs consecutivos en orden de generación) vs campos visibles.
# Si el fraude/rechazo consumiera sorteos extra 'ocultos', aparecería como gap distinto no explicado por campos visibles.
import sys, numpy as np, duckdb, pandas as pd
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words, chars_per_word, locate
N=40000
c = chars_per_word(words(N*100+1000))
con = duckdb.connect(); con.execute("SET memory_limit='500MB'; SET threads=2")
df = con.execute(f"""select file_row_number frn, transaction_id, transaction_type tt, channel ch, transaction_status st, response_code code, is_fraud fraud,
   fraud_score fs, amount_usd au, merchant_name mn, branch_id bid, transaction_country ctry, latitude lat
   from read_parquet('data/bronze/transactions.parquet', file_row_number=true) where file_row_number<{N} order by file_row_number""").fetchdf()
pos=[]; prev=0
for v in df.transaction_id:
    p = locate(c, v.split('-',1)[1], prev, prev+5000); pos.append(p)
    if p>=0: prev=p+1
df['pos']=pos
print('ubicadas', (df.pos>=0).mean())
df['gap']=df.pos.shift(-1)-df.pos   # palabras consumidas por la fila (ID + resto de campos)
df=df.dropna(subset=['gap'])
for col in ['tt','ch','st','fraud']:
    print(df.groupby(col).gap.agg(['mean','std','count']).round(2).to_string())
for col in ['code','fs','au','mn','bid','lat']:
    print(col, df.groupby(df[col].isna()).gap.agg(['mean','std','count']).round(2).to_string())
# regresión lineal del gap sobre campos visibles; ¿el fraude añade algo residual?
X = pd.get_dummies(df[['tt','ch','st']].astype(str), drop_first=True)
for col in ['code','fs','au','mn','bid','lat']: X[col+'_null']=df[col].isna().astype(int)
from sklearn.linear_model import LinearRegression
m = LinearRegression().fit(X, df.gap); r = df.gap - m.predict(X)
print('R2 campos visibles', round(m.score(X, df.gap),3))
print('residuo por fraude', r.groupby(df.fraud).agg(['mean','std','count']).round(2).to_string())
