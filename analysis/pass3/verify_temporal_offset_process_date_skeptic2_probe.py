"""Sonda: ¿el desplazamiento aleatorio U = ts - (process_date + K) es el mismo flujo en tx, cp y cc (misma semilla)?
Lee los CSV crudos de unos días en orden de archivo (módulo csv, sin reordenar)."""
import csv, glob, datetime as dt
def load(t, day, tcol):
    f = glob.glob(f'data/raw/{t}/year={day[:4]}/month={day[4:6]}/day={day[6:]}/*.csv')[0]
    rows = []
    with open(f, encoding='utf-8-sig', newline='') as fh:
        for r in csv.DictReader(fh):
            ts = dt.datetime.strptime(r[tcol], '%Y-%m-%d %H:%M:%S')
            pd_ = dt.datetime.strptime(r['process_date'], '%Y-%m-%d')
            rows.append((list(r.values())[0], int((ts - pd_).total_seconds()), r.get('customer_id')))
    return rows
for day in ['20230617', '20240101', '20250704']:
    tx = load('transactions', day, 'transaction_date'); cp = load('complaints', day, 'creation_date')
    cc = load('call_center_interactions', day, 'interaction_date')
    print(day, 'n', len(tx), len(cp), len(cc))
    for i in range(4):
        print('  tx', tx[i][0], tx[i][1] - 6*3600, '| cp', cp[i][0], cp[i][1] - 8*3600, '| cc', cc[i][0], cc[i][1] - 8*3600)
