"""Verificacion independiente (intento 3, parte 2): status_iso_codes_inconsistent.
Codigos de rechazo vs tipo de producto / tipo de tx / canal (solo tx no aprobadas)."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2_contingency
warnings.filterwarnings('ignore')
pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

BASE = """(select t.status, coalesce(t.code,'NA') code, t.ttype, t.channel, p.ptype,
   case when p.ptype like 'Tarjeta%' then 'tarjeta'
        when p.ptype like 'Cuenta%' then 'cuenta'
        else 'prest_inv_seg' end grp
   from tx t join pr p on t.product_id = p.product_id
   where t.status <> 'Approved') na"""

def cramer(ct):
    ct = ct.loc[ct.sum(1) > 0, ct.sum(0) > 0]
    chi2, p, dof, _ = chi2_contingency(ct.values, correction=False)
    n = ct.values.sum(); k = min(ct.shape) - 1
    v = np.sqrt(chi2 / (n * k))
    # piso de ruido: E[chi2]=dof bajo independencia -> V esperado ~ sqrt(dof/(n k))
    return v, p, np.sqrt(dof / (n * k)), int(n)

def ctab(col, where="code <> 'NA'"):
    d = q(f"select {col} r, code, count(*) n from {BASE} where {where} group by 1,2")
    return d.pivot(index='r', columns='code', values='n').fillna(0)

print("== denominadores no aprobadas ==")
print(q(f"""select count(*) n_no_aprob,
  sum(case when code<>'NA' then 1 else 0 end) n_con_codigo,
  sum(case when code in ('14','54') and grp<>'tarjeta' then 1 else 0 end) c1454_no_tarjeta,
  sum(case when code in ('14','54') and grp='cuenta' then 1 else 0 end) c1454_cuenta,
  sum(case when code in ('14','54') and grp='prest_inv_seg' then 1 else 0 end) c1454_prest_inv_seg,
  sum(case when code in ('14','54') and grp='tarjeta' then 1 else 0 end) c1454_tarjeta
  from {BASE}""").T.to_string())

print("\n== codigo x grupo de producto (no aprobadas con codigo): conteos y % fila ==")
ct = ctab('grp'); print(ct.astype(int).to_string()); print(ct.div(ct.sum(1), axis=0).round(4).to_string())
ct2 = ctab("case when grp='tarjeta' then 'tarjeta' else 'no_tarjeta' end")
print(ct2.astype(int).to_string())

print("\n== codigo x ptype (% fila, no aprobadas con codigo) ==")
ct = ctab('ptype'); print(ct.div(ct.sum(1), axis=0).round(4).assign(n=ct.sum(1).astype(int)).to_string())

print("\n== codigo x ttype (% fila, no aprobadas con codigo) ==")
ct = ctab('ttype'); print(ct.div(ct.sum(1), axis=0).round(4).assign(n=ct.sum(1).astype(int)).to_string())

print("\n== V de Cramer (no aprobadas) ==")
rows = []
for col in ['ttype', 'channel', 'ptype', 'grp', 'status']:
    for lab, where in [('sin NA', "code <> 'NA'"), ('con NA', "1=1")]:
        v, p, floor, n = cramer(ctab(col, where))
        rows.append((col, lab, n, round(v, 4), round(floor, 4), p))
print(pd.DataFrame(rows, columns=['vs', 'codigo', 'n', 'V', 'V_ruido_esperado', 'p_chi2']).to_string())

print("\n== Deposit no aprobados: codigo ==")
d = q(f"select status, code, count(*) n from {BASE} where ttype='Deposit' group by 1,2")
ct = d.pivot(index='status', columns='code', values='n').fillna(0).astype(int)
ct.loc['TOTAL'] = ct.sum(); print(ct.to_string())
tot = ct.loc['TOTAL']; print("51 / dep no aprob =", round(tot['51'] / tot.sum(), 4),
                            "| 51 / dep no aprob con codigo =", round(tot['51'] / (tot.sum() - tot['NA']), 4))

print("\n== solo Declined: 14/54 en no tarjeta y 51 en Deposit ==")
print(q(f"""select count(*) n_declined, sum(case when code<>'NA' then 1 else 0 end) con_codigo,
  sum(case when code in ('14','54') and grp<>'tarjeta' then 1 else 0 end) c1454_no_tarjeta,
  sum(case when code in ('14','54') and grp='prest_inv_seg' then 1 else 0 end) c1454_prest_inv_seg,
  sum(case when ttype='Deposit' then 1 else 0 end) dep, sum(case when ttype='Deposit' and code='51' then 1 else 0 end) dep51
  from {BASE} where status='Declined'""").T.to_string())

print("\n== 14/54 en no tarjeta por canal (para ver cuantas son 'imposibles' tambien por canal) ==")
d = q(f"""select grp, channel, count(*) n from {BASE} where code in ('14','54') and grp<>'tarjeta' group by 1,2""")
print(d.pivot(index='grp', columns='channel', values='n').fillna(0).astype(int).to_string())
