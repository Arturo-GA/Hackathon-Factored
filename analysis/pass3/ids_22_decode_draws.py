# ids_22: decodificar sorteos por fila en transacciones: ¿en qué desfase (desde el ID propio o hacia el ID siguiente) está el uniforme
# que produce fraud_score (legítimas ~U(0,30], fraude ~U(0,100)) y el uniforme que decide is_fraud (u<0.001)?
import sys, numpy as np, duckdb
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words, chars_per_word, locate
N=40000
w = words(N*100+2000); c = chars_per_word(w)
u = ((w[:-1]>>5).astype(np.float64)*67108864.0 + (w[1:]>>6).astype(np.float64))/9007199254740992.0  # random() que empieza en palabra p
con = duckdb.connect(); con.execute("SET memory_limit='500MB'; SET threads=2")
df = con.execute(f"""select transaction_id, is_fraud='True' fraud, try_cast(fraud_score as double) fs, try_cast(amount as double) amt, transaction_status st
   from read_parquet('data/bronze/transactions.parquet', file_row_number=true) where file_row_number<{N} order by file_row_number""").fetchdf()
pos=[]; prev=0
for v in df.transaction_id:
    p = locate(c, v.split('-',1)[1], prev, prev+5000); pos.append(p); prev=p+1
df['pos']=np.array(pos); df['nxt']=df.pos.shift(-1)
df=df.dropna(subset=['nxt']).copy(); df['nxt']=df.nxt.astype(int)
leg = df[(~df.fraud)&df.fs.notna()]
best=[]
for ref in ['pos','nxt']:
    for d in (range(40,200) if ref=='pos' else range(-150,0)):
        uu = u[leg[ref].values+d]
        for scale in [30.0, 100.0]:
            m = np.mean(np.abs(uu*scale - leg.fs.values) < 0.006)
            best.append((m, ref, d, scale))
best.sort(reverse=True); print('mejores desfases para fraud_score legítimas (frac exacta a 2 decimales):', best[:5])
# ¿is_fraud = u < p en algún desfase fijo?
res=[]
for ref in ['pos','nxt']:
    for d in (range(40,200) if ref=='pos' else range(-150,0)):
        uu = u[df[ref].values+d]
        fr = df.fraud.values
        res.append((np.mean(uu[fr]<0.01), np.mean(uu[~fr]<0.01), ref, d))
res.sort(reverse=True); print('desfases donde u<0.01 en fraudes:', [r for r in res[:5]])

# --- búsqueda flexible: el ID parece sortearse AL FINAL de la fila; buscar el uniforme de fraud_score en una ventana antes del ID propio
def match_window(sub, lo, hi, scale, tol=0.006):
    P = sub.pos.values
    M = np.stack([u[P+d] for d in range(lo,hi)], axis=1)*scale
    hit = np.abs(M - sub.fs.values[:,None]) < tol
    return hit.any(1).mean(), (hit.argmax(1)+lo)[hit.any(1)]
for lo,hi in [(-12,0),(-30,-12),(-80,-30)]:
    r, offs = match_window(leg, lo, hi, 30.0)
    print(f'legítimas ventana [{lo},{hi}) escala 30: frac con coincidencia={r:.3f}; azar≈{(hi-lo)*0.012/30:.4f}; desfases top', np.unique(offs, return_counts=True)[1][:0], np.bincount(offs-lo).argmax()+lo if len(offs) else None)
fr = df[df.fraud & df.fs.notna()]
for sc in [100.0, 30.0]:
    r, offs = match_window(fr, -12, 0, sc)
    print(f'fraudes (n={len(fr)}) ventana [-12,0) escala {sc}: frac={r:.3f}')

# --- posición exacta del sorteo de fraud_score por fila y búsqueda del uniforme que decide is_fraud antes/después
def fs_pos(sub):
    P = sub.pos.values; sc = np.where(sub.fraud.values, 100.0, 30.0)
    M = np.stack([u[P+d] for d in range(-12,0)], axis=1)*sc[:,None]
    hit = np.abs(M - sub.fs.values[:,None]) < 0.006
    return np.where(hit.any(1), P + hit.argmax(1) - 12, -1)
sub = df[df.fs.notna()].copy(); sub['fsp'] = fs_pos(sub); sub = sub[sub.fsp>=0]
print('filas con fs ubicado', len(sub), 'desfase fs respecto al ID:', np.bincount(sub.pos.values - sub.fsp.values)[:14])
F = sub.fraud.values
out=[]
for k in range(-90, 0):
    uu = u[sub.fsp.values + k]
    out.append((k, round(float(np.mean(uu[F]<0.002)),3), round(float(np.mean(uu[~F]<0.002)),4), round(float(uu[F].max()),5)))
out.sort(key=lambda x: -x[1]); print('k, P(u<0.002|fraude), P(u<0.002|legit), max u fraude:', out[:6])
d_off = sub.pos.values - sub.fsp.values
print('distribución (pos_ID - pos_fraud_score):', dict(zip(*np.unique(d_off, return_counts=True))))
