# ids_25: escaneo desde el INICIO de cada fila (fin del ID de la fila anterior = pos_prev+40) para ubicar sorteos de status/code/canal/tipo/moneda
import sys, numpy as np, pandas as pd
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words
SP='C:/Users/Arturo/AppData/Local/Temp/claude/C--Users-Arturo-Documents-Factored-Hackathon/dd019af3-3739-4a2c-98c4-2235ab816d32/scratchpad/tx400k_pos.parquet'
df = pd.read_parquet(SP)
df['start'] = df.pos.shift(1) + 40
df = df.dropna(subset=['start']); df['start']=df.start.astype(np.int64)
df['code']=df.code.fillna('NA'); df['fsnull']=df.fs.isna()
N=400000; w = words(N*86+5000)
def U(p): return ((w[p]>>5).astype(np.float64)*67108864.0 + (w[p+1]>>6).astype(np.float64))/9007199254740992.0
def purity(u, y):
    b = np.minimum((u*400).astype(int),399); t = pd.crosstab(b, y)
    return t.max(axis=1).sum()/len(y), y.value_counts(normalize=True).max()
res=[]
for k in range(0, 45):
    u = U(df.start.values + k)
    for col in ['st','code','ch','tt','cur','fsnull','usd_null','mer_null','lat_null']:
        p, base = purity(u, df[col].astype(str)); res.append((round(p-base,4), col, k, round(p,4), round(base,4)))
res.sort(reverse=True)
for r in res[:15]: print(r)
print('gap filas', (df.pos-df.start).describe().round(1).to_dict())
