# ids_11: registration_branch_id / assigned_branch_id son IDs nuevos sorteados DENTRO de la fila (no punteros corruptos):
# se ubican en el flujo MT cerca del ID propio de la fila con desfase casi fijo; las pocas coincidencias con branches son colisiones de semilla
import sys, numpy as np, duckdb, collections
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words, chars_per_word, locate
c = chars_per_word(words(2_000_000))
con = duckdb.connect(); con.execute("SET memory_limit='500MB'; SET threads=2")
def pos_of(table, col, n):
    ids = [r[0] for r in con.execute(f"select {col} from read_parquet('data/bronze/{table}.parquet', file_row_number=true) where file_row_number<{n} order by file_row_number").fetchall()]
    out=[]; prev=0
    for v in ids:
        p = locate(c, v.split('-',1)[1], prev, prev+100000); out.append(p)
        if p>=0: prev=p+1
    return ids, np.array(out)
def rel(table, idcol, fkcol, n):
    rows = con.execute(f"select {idcol}, {fkcol} from read_parquet('data/bronze/{table}.parquet', file_row_number=true) where file_row_number<{n} order by file_row_number").fetchall()
    offs=[]; prev=0
    for rid, fk in rows:
        p = locate(c, rid.split('-',1)[1], prev, prev+100000)
        if p<0: offs.append('noid'); continue
        prev=p+1
        if fk is None: continue
        q = locate(c, fk.split('-',1)[1], max(0,p-600), p+600)
        offs.append(q-p if q>=0 else 'nf')
    cnt=collections.Counter(offs)
    loc = sum(v for k,v in cnt.items() if isinstance(k,(int,np.integer)))
    print(f"{table}.{fkcol}: filas={len(rows)} fk_no_nulo={len(offs)} ubicados_en_su_propia_fila={loc} desfases_top={cnt.most_common(6)}")
rel('customers','customer_id','registration_branch_id',2000)
rel('service_agents','agent_id','assigned_branch_id',1200)
# colisiones: la posición del reg_branch coincide con la del branch real?
bids, bpos = pos_of('branches','branch_id',350)
bmap = dict(zip(bids,bpos))
cids, cpos = pos_of('customers','customer_id',200)
regs = [r[0] for r in con.execute("select registration_branch_id from read_parquet('data/bronze/customers.parquet', file_row_number=true) where file_row_number<200 order by file_row_number").fetchall()]
for i,(r,p) in enumerate(zip(regs,cpos)):
    if r in bmap:
        q = locate(c, r.split('-',1)[1], max(0,p-600), p+600)
        print(f"fila cliente {i}: reg={r} pos_en_flujo={q} pos_branch_real={bmap[r]} -> misma_posicion={q==bmap[r]}")
print('último branch termina en palabra', bpos.max()+16, '; cliente fila 130 empieza en', cpos[130])
