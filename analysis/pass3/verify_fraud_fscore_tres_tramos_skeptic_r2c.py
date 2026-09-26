"""Verificador escéptico (reintento) — parte C: umbrales, 'umbral aprendido' en held-out por cliente,
AUC por tramos con IC bootstrap por cliente, razones de verosimilitud y cobertura práctica."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width', 220)
con = connect()

print('== C1. Umbrales (datos completos) ==')
tot = q(con, "SELECT count(*) FILTER (WHERE fraud) p, count(*) FILTER (WHERE fraud AND fscore IS NOT NULL) ps FROM tx")
P, PS = int(tot.p[0]), int(tot.ps[0])
for op, thr in [('>', 29.99), ('>=', 30), ('>', 30), ('>', 35), ('>', 40), ('>', 50), ('>=', 50)]:
    d = q(con, f"SELECT count(*) FILTER (WHERE fscore{op}{thr} AND fraud) tp, count(*) FILTER (WHERE fscore{op}{thr}) pp FROM tx")
    tp, pp = int(d.tp[0]), int(d.pp[0])
    print(f"fscore{op}{thr}: tp={tp} pp={pp} precision={tp/pp:.4f} recall_total={tp/P:.4f} recall_con_score={tp/PS:.4f}")

print('\n== C2. Umbral "aprendido" en train (80% clientes) y evaluado en test (20%) ==')
split = "(hash(customer_id) % 5 = 0)"
tr = q(con, f"SELECT max(fscore) FILTER (WHERE NOT fraud) thr FROM tx WHERE NOT {split}")
thr = float(tr.thr[0]); print('umbral aprendido = max score legítimo en train =', thr)
for name, cond in [('aprendido >%.2f' % thr, f'fscore>{thr}'), ('baseline >=50', 'fscore>=50'), ('baseline >50', 'fscore>50')]:
    d = q(con, f"""SELECT count(*) FILTER (WHERE {cond} AND fraud) tp, count(*) FILTER (WHERE {cond}) pp,
                   count(*) FILTER (WHERE fraud) p FROM tx WHERE {split}""")
    print(f"  test {name}: precision={int(d.tp[0])}/{int(d.pp[0])}  recall={int(d.tp[0])}/{int(d.p[0])}={d.tp[0]/d.p[0]:.4f}")

print('\n== C3. AUC en test agrupado por cliente (bootstrap por cliente, 1000 réplicas) ==')
# conteos por cliente de test: (tramo x fraude)
pc = q(con, f"""SELECT customer_id,
   count(*) FILTER (WHERE fscore<=30 AND NOT fraud) l0, count(*) FILTER (WHERE fscore IS NULL AND NOT fraud) l1, count(*) FILTER (WHERE fscore>30 AND NOT fraud) l2,
   count(*) FILTER (WHERE fscore<=30 AND fraud) f0, count(*) FILTER (WHERE fscore IS NULL AND fraud) f1, count(*) FILTER (WHERE fscore>30 AND fraud) f2
   FROM tx WHERE {split} GROUP BY 1""")
M = pc[['l0', 'l1', 'l2', 'f0', 'f1', 'f2']].values.astype(float)
def auc_ordinal(tot, order):
    """tot=[l0,l1,l2,f0,f1,f2]; order = rango de cada tramo (mayor = más riesgo)."""
    L = tot[:3] / tot[:3].sum(); F = tot[3:] / tot[3:].sum(); a = 0.0
    for i in range(3):
        for j in range(3):
            if order[i] > order[j]: a += F[i] * L[j]
            elif order[i] == order[j]: a += 0.5 * F[i] * L[j]
    return a
specs = {'3 tramos (>30 > nulo > <=30)': [0, 1, 2], 'solo indicador >30 (nulo = <=30)': [0, 0, 1],
         'fscore ingenuo con nulo=-1 (nulo < <=30)': [1, 0, 2]}
T = M.sum(0); rng = np.random.default_rng(7)
W = np.stack([np.bincount(rng.integers(0, len(M), len(M)), minlength=len(M)) for _ in range(1000)])
BT = W @ M
print('test: clientes=%d tx=%d fraude=%d' % (len(M), int(T.sum()), int(T[3:].sum())))
for k, o in specs.items():
    bs = [auc_ordinal(b, o) for b in BT]
    print(f"  {k:45s} AUC={auc_ordinal(T, o):.4f} IC95 [{np.percentile(bs,2.5):.4f}, {np.percentile(bs,97.5):.4f}]")

print('\n== C4. Razones de verosimilitud por tramo (todos los datos) ==')
t = q(con, """SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=30 THEN 'le30' ELSE 'gt30' END tramo,
   count(*) FILTER (WHERE fraud) f, count(*) FILTER (WHERE NOT fraud) l FROM tx GROUP BY 1""").set_index('tramo')
t['P_tramo_fraude'] = t.f / t.f.sum(); t['P_tramo_legit'] = t.l / t.l.sum(); t['LR'] = t.P_tramo_fraude / t.P_tramo_legit
print(t.round(4))

print('\n== C5. Cobertura práctica ==')
print(q(con, """SELECT count(*) FILTER (WHERE fscore>30) tx_gt30, round(100.0*count(*) FILTER (WHERE fscore>30)/count(*),4) pct_tx,
   count(DISTINCT customer_id) FILTER (WHERE fscore>30) clientes_gt30, count(DISTINCT customer_id) FILTER (WHERE fraud) clientes_fraude,
   count(DISTINCT customer_id) clientes FROM tx""").to_string(index=False))
print('¿el fraude >30 es otro proceso? (fraude por tramo: estado/tipo/canal)')
print(q(con, """SELECT CASE WHEN fscore>30 THEN 'gt30' WHEN fscore IS NULL THEN 'nulo' ELSE 'le30' END g, count(*) n,
   round(100*avg((status='Approved')::INT),1) aprob, round(100*avg((ttype='Purchase')::INT),1) compra,
   round(100*avg((channel='POS')::INT),1) pos, round(median(amount_usd),1) med_usd FROM tx WHERE fraud GROUP BY 1 ORDER BY 1""").to_string(index=False))

print('\n== C6. Doble conteo: IDs únicos en toda la tabla y casi-duplicados entre fraude >30 ==')
print(q(con, """SELECT count(*) n, count(DISTINCT transaction_id) nid,
   (SELECT count(*) FROM (SELECT customer_id, ts, amount FROM tx WHERE fscore>30 GROUP BY ALL HAVING count(*)>1)) casi_dup_gt30 FROM tx""").to_string(index=False))
