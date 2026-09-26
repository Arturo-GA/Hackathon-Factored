# ids_20: verificación completa: TODOS los customer_id (150k) y product_id (400k) están en el flujo MT(seed=42) en orden de archivo,
# con consumo por fila casi constante -> IDs = random.choices('0-9A-Z', k) con random.seed(42) por tabla
import sys, numpy as np, pyarrow.parquet as pq, collections
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words, chars_per_word, AMAP
def run(table, col, nwords, win=600):
    ids = pq.read_table(f'data/bronze/{table}.parquet', columns=[col]).column(col).to_pylist()
    c = chars_per_word(words(nwords))
    pos = np.full(len(ids), -1, dtype=np.int64); prev=0
    for i,v in enumerate(ids):
        e = np.frombuffer(v.split('-',1)[1].encode(), dtype=np.uint8)
        e = np.array([AMAP[chr(x)] for x in e], dtype=np.int8); k=len(e)
        seg = c[prev:prev+win+2*k]
        cand = np.nonzero(seg[:win]==e[0])[0]
        for j in range(1,k):
            cand = cand[seg[cand+2*j]==e[j]]
            if len(cand)==0: break
        if len(cand):
            pos[i]=prev+cand[0]; prev=pos[i]+1
    ok = pos>=0; g=np.diff(pos[ok])
    print(f"{table}.{col}: n={len(ids)} ubicados={ok.sum()} ({ok.mean():.4%}) palabras/fila media={g.mean():.1f} sd={g.std():.1f} min={g.min()} max={g.max()} ultima_pos={pos[ok].max()}")
    del c
run('branches','branch_id', 30000)
run('service_agents','agent_id', 150000)
run('marketing_campaigns','campaign_id', 20000)
run('customers','customer_id', 19_500_000)
run('products','product_id', 31_500_000)
