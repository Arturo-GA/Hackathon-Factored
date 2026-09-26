"""hunt_27: ¿existen rasgos latentes por cliente fuera de tx? Correlacion split-half por cliente:
los eventos de cada cliente se parten al azar en dos mitades (hash del id del evento) y se correlaciona
la media del resultado en la mitad A con la mitad B entre clientes. Sin rasgo latente r~0.
Incluye controles positivos (atributos que SI son del cliente) para validar el metodo.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_27_customer_traits.py
"""
import time
import duckdb
import numpy as np
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

SPECS = {
    'cc': ('interaction_id', 'cc', None, {
        'resolved': "CASE WHEN resolved THEN 1.0 ELSE 0 END",
        'escalated': "CASE WHEN escalated THEN 1.0 ELSE 0 END",
        'followup': "CASE WHEN followup THEN 1.0 ELSE 0 END",
        'sent_score': "sent_score",
        'sent_neg': "CASE WHEN sent IN ('Negativo','Muy Negativo') THEN 1.0 ELSE 0 END",
        'log_dur': "ln(dur)",
        'wait': "wait",
        'cat_queja': "CASE WHEN cat='Queja' THEN 1.0 ELSE 0 END",
        'cat_transacc': "CASE WHEN cat='Transaccional' THEN 1.0 ELSE 0 END",
        'itype_inbound': "CASE WHEN itype='Inbound Call' THEN 1.0 ELSE 0 END",
        'chan_phone': "CASE WHEN channel='Phone' THEN 1.0 ELSE 0 END",
        'has_transcript': "CASE WHEN has_transcript THEN 1.0 ELSE 0 END",
        'CTRL_c_acc_mex': "CASE WHEN c_acc='mexican' THEN 1.0 WHEN c_acc IS NULL THEN NULL ELSE 0 END",
    }),
    'sv': ('survey_id', 'sv', None, {
        'csat_score': "CASE WHEN survey_type='CSAT' THEN score END",
        'nps_score': "CASE WHEN survey_type='NPS' THEN score END",
        'resp_hours': "resp_hours",
        'send_email': "CASE WHEN send_channel='Email' THEN 1.0 ELSE 0 END",
        'type_csat': "CASE WHEN survey_type='CSAT' THEN 1.0 ELSE 0 END",
        'comment_neg': "CASE WHEN comment_sentiment='Negative' THEN 1.0 WHEN comment_sentiment IS NULL THEN NULL ELSE 0 END",
    }),
    'cs': ('send_id', 'cs', None, {
        'delivered': "CASE WHEN delivered THEN 1.0 ELSE 0 END",
        'opened_sms_push_email': "CASE WHEN send_channel IN ('SMS','Push','Email') AND delivered THEN (CASE WHEN opened THEN 1.0 ELSE 0 END) END",
        'clicked_given_open': "CASE WHEN opened THEN (CASE WHEN clicked THEN 1.0 ELSE 0 END) END",
        'chan_email': "CASE WHEN send_channel='Email' THEN 1.0 ELSE 0 END",
    }),
    'cp': ('complaint_id', 'cp', None, {
        'prio_high': "CASE WHEN priority IN ('High','Critical') THEN 1.0 ELSE 0 END",
        'sla': "CASE WHEN sla THEN 1.0 ELSE 0 END",
        'repeat': "CASE WHEN repeat THEN 1.0 ELSE 0 END",
        'cat_transactions': "CASE WHEN category='Transactions' THEN 1.0 ELSE 0 END",
        'rchan_callcenter': "CASE WHEN rchan='Call Center' THEN 1.0 ELSE 0 END",
        'type_complaint': "CASE WHEN case_type='Complaint' THEN 1.0 ELSE 0 END",
    }),
    # de: muestra de clientes (hash % 8 = 0) para acotar RAM
    'de': ('event_id', 'de', "customer_id IS NOT NULL AND hash(customer_id) % 8 = 0", {
        'is_error': "CASE WHEN event_type='Error' THEN 1.0 ELSE 0 END",
        'is_login': "CASE WHEN event_type='Login' THEN 1.0 ELSE 0 END",
        'log_dur': "ln(1+dur)",
        'chan_ios': "CASE WHEN channel='iOS App' THEN 1.0 ELSE 0 END",
        'is_mobile': "CASE WHEN is_mobile THEN 1.0 ELSE 0 END",
        'CTRL_ip_country_mx': "CASE WHEN ip_country IN ('México','Mexico') THEN 1.0 ELSE 0 END",
    }),
}
rows = []
for tname, (idcol, tbl, where, outs) in SPECS.items():
    t0 = time.time()
    sel = ", ".join([f"avg({expr}) AS \"{k}\"" for k, expr in outs.items()])
    w = f"WHERE {where}" if where else "WHERE customer_id IS NOT NULL"
    df = con.execute(f"""SELECT customer_id, (hash({idcol}) % 2) AS half, count(*) n, {sel}
                         FROM {tbl} {w} GROUP BY 1,2""").df()
    a = df[df.half == 0].set_index('customer_id')
    b = df[df.half == 1].set_index('customer_id')
    j = a.join(b, lsuffix='_a', rsuffix='_b', how='inner')
    for k in outs:
        x, y = j[f'{k}_a'], j[f'{k}_b']
        m = x.notna() & y.notna()
        if m.sum() < 100:
            continue
        r = np.corrcoef(x[m], y[m])[0, 1]
        # IC95 bootstrap sobre clientes
        rng = np.random.default_rng(0)
        xv, yv = x[m].values, y[m].values
        bs = []
        for _ in range(200):
            s = rng.integers(0, len(xv), len(xv))
            bs.append(np.corrcoef(xv[s], yv[s])[0, 1])
        lo, hi = np.percentile(bs, [2.5, 97.5])
        # Spearman-Brown: fiabilidad del promedio de todos los eventos ~ 2r/(1+r)
        rows.append((tname, k, int(m.sum()), round(float(np.mean(j.loc[m, 'n_a'] + j.loc[m, 'n_b'])), 2), round(r, 4), round(lo, 4), round(hi, 4)))
    print(tname, f'{time.time()-t0:.0f}s', flush=True)
res = pd.DataFrame(rows, columns=['tabla', 'resultado', 'clientes', 'eventos_medios', 'r_split_half', 'ic_lo', 'ic_hi'])
print(res.to_string(index=False))
