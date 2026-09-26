# ids_07: ubica cada ID (en orden de archivo) en el flujo MT de seed=42 -> prueba que todos los IDs son random.choices('0-9A-Z') con semilla 42
# y mide cuántas palabras aleatorias consume cada fila (gap entre IDs consecutivos)
import sys, numpy as np, pyarrow.parquet as pq, collections
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words, chars_per_word, locate
N = 12_000_000
c = chars_per_word(words(N))
def run(table, col, nrows, extra=()):
    t = pq.read_table(f'data/bronze/{table}.parquet', columns=[col,*extra]).slice(0, nrows).to_pandas()
    pos=[]; prev=0
    for i,v in enumerate(t[col]):
        body = v.split('-',1)[1]
        p = locate(c, body, start=prev, maxpos=prev+200000)
        pos.append(p)
        if p>=0: prev = p+1
    pos=np.array(pos); ok=pos>=0
    gaps = np.diff(pos[ok])
    print(f"{table}.{col}: filas={nrows} ubicadas={ok.sum()} primera_pos={pos[0]} gap_mediano={np.median(gaps) if len(gaps) else None} gaps_top={collections.Counter(gaps).most_common(5)}")
    return t, pos
run('branches','branch_id',350)
run('service_agents','agent_id',1200)
run('marketing_campaigns','campaign_id',200)
t,pos = run('customers','customer_id',300)
t,pos = run('products','product_id',300)
