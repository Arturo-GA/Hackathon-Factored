# ids_24: ¿dónde se sortea transaction_status / response_code / tipo / canal? escaneo de desfases antes del sorteo de fraude;
# pureza = exactitud de predecir la categoría con 200 bins del uniforme en ese desfase (1.0 = sorteo directo con pesos fijos)
import sys, numpy as np, pandas as pd
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words
SP='C:/Users/Arturo/AppData/Local/Temp/claude/C--Users-Arturo-Documents-Factored-Hackathon/dd019af3-3739-4a2c-98c4-2235ab816d32/scratchpad/tx400k_pos.parquet'
df = pd.read_parquet(SP); df = df[df.off>0].copy()
N=400000; w = words(N*86+5000)
def U(p): return ((w[p]>>5).astype(np.float64)*67108864.0 + (w[p+1]>>6).astype(np.float64))/9007199254740992.0
fpos = df.pos.values - df.off.values - 2   # posición del sorteo de fraude
df['code']=df.code.fillna('NA')
def purity(u, y):
    b = np.minimum((u*200).astype(int),199); t = pd.crosstab(b, y)
    return t.max(axis=1).sum()/len(y), y.value_counts(normalize=True).max()
res=[]
for k in range(1, 70):
    u = U(fpos - k)
    for col in ['st','code','ch','tt','cur']:
        p, base = purity(u, df[col]); res.append((round(p-base,4), col, k, round(p,4), round(base,4)))
res.sort(reverse=True)
for r in res[:12]: print(r)
