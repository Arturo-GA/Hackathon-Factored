"""hunt_37: resumen del barrido de V de Cramer (hunt_07: tx muestra 800k con atributos de cliente/producto, cu, pr).
Distribucion bimodal de V, maximo V entre atributos 'blandos' (demografia, estados, app, canal de apertura) y cualquier otra columna,
y la banda intermedia 0.02-0.9 con su explicacion estructural.
Requiere analysis/pass3/hunt_cache/hunt_07_cramer.csv (generado por hunt_07_cramer.py, ~7 min).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_37_cramer_summary.py
"""
import pandas as pd
pd.set_option('display.width', 220); pd.set_option('display.max_rows', 100)
r = pd.read_csv('analysis/pass3/hunt_cache/hunt_07_cramer.csv')
r['banda'] = pd.cut(r.V, [-1, 0.02, 0.1, 0.3, 0.9, 1.01], labels=['<0.02', '0.02-0.1', '0.1-0.3', '0.3-0.9', '>=0.9'])
print(pd.crosstab(r.lvl, r.banda, margins=True).to_string())
soft = {'tx': ['segment', 'gender', 'occupation', 'cstatus', 'mkt', 'education', 'marital', 'age_dec', 'papp', 'opening_channel', 'popen_yr'],
        'cu': ['gender', 'occupation', 'marital', 'education', 'cstatus', 'mkt', 'landline', 'email_dom', 'age_dec', 'regbr_null'],
        'pr': ['pstatus', 'app', 'opening_channel', 'obr_null', 'rate_dec', 'bal_dec']}
outcome = ['status', 'code', 'fraud', 'fscore_b']
for lvl, cols in soft.items():
    x = r[(r.lvl == lvl) & (r.a.isin(cols) | r.b.isin(cols))].sort_values('V', ascending=False)
    print(f'{lvl}: pares con atributo blando={len(x)}  V max={x.V.max():.4f}  NMI max={x.NMI.max():.5f}  top:',
          x.head(3)[['a', 'b', 'V']].values.tolist())
t = r[(r.lvl == 'tx') & (r.a.isin(outcome) ^ r.b.isin(outcome))].sort_values('V', ascending=False)
print(f'tx: status/code/fraud/fscore vs resto: pares={len(t)} V max={t.V.max():.4f} top:', t.head(3)[['a', 'b', 'V']].values.tolist())
print('banda intermedia 0.02<=V<0.9:')
print(r[(r.V >= 0.02) & (r.V < 0.9)].sort_values(['lvl', 'V'], ascending=[True, False])[['lvl', 'a', 'b', 'ka', 'kb', 'V', 'NMI']].to_string(index=False, float_format=lambda v: f'{v:.3f}'))
