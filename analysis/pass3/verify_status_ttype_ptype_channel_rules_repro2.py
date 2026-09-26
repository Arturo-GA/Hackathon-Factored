"""Verificacion independiente (reintento) de status_ttype_ptype_channel_rules.
Metodo: un solo 'cubo' agregado (ptype, ttype, channel, status, code, banderas de llenado) y todas las reglas
se cuentan en pandas sobre el cubo; consultas aparte solo para comercio->mcat, tcat derivable y sucursal.
Cramer V y chi2 calculados a mano (sin chi2_contingency)."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2 as chi2dist
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)

cube = q("""
select p.ptype, t.ttype, t.channel, t.status, coalesce(t.code,'NULL') code,
  (t.merchant_name is not null)::int hm, (t.mcat is not null)::int hmc, (t.tcat is not null)::int htc,
  case when t.tcat is null or t.mcat is null then -1 when t.tcat = t.mcat then 1 else 0 end tceq,
  (t.branch_id is not null)::int hb, (t.lat is not null)::int hla, (t.lon is not null)::int hlo,
  (p.customer_id is not null and p.customer_id <> t.customer_id)::int owner_diff,
  count(*) n
from tx t left join pr p on t.product_id = p.product_id
group by all""")
cube['ptype'] = cube['ptype'].fillna('SIN_MATCH')
N = int(cube.n.sum())
print(f"N={N:,}  filas cubo={len(cube):,}  tx sin producto en pr={int(cube.loc[cube.ptype=='SIN_MATCH','n'].sum())}"
      f"  tx cuyo producto es de otro cliente={int(cube.loc[cube.owner_diff==1,'n'].sum())}")
S = lambda m: int(cube.loc[m, 'n'].sum())

# ---------------- (a) ptype x ttype
allowed = {
 'Cuenta Ahorro': {'Deposit','Payment','Transfer','Withdrawal'},
 'Cuenta Corriente': {'Deposit','Payment','Transfer','Withdrawal'},
 'Tarjeta Crédito': {'Purchase','Payment','Withdrawal'},
 'Tarjeta Débito': {'Purchase','Payment','Withdrawal'},
 'Inversión': {'Adjustment','Payment','Transfer'},
 'Préstamo Hipotecario': {'Adjustment','Payment','Transfer'},
 'Préstamo Personal': {'Adjustment','Payment','Transfer'},
 'Seguro': {'Adjustment','Payment','Transfer'},
}
viol_a = S(~cube.apply(lambda r: r.ttype in allowed.get(r.ptype, set()), axis=1))
pt = cube.pivot_table(index='ptype', columns='ttype', values='n', aggfunc='sum', fill_value=0)
print("\n(a) ptype x ttype\n", pt.to_string())
print("violaciones (a):", viol_a)
obs_support = {p: set(pt.columns[pt.loc[p] > 0]) for p in pt.index}
print("soporte observado == soporte declarado en los 8 ptypes:", all(obs_support[p] == allowed[p] for p in allowed))
print("celda permitida minima:", int(min(pt.loc[p, t] for p in allowed for t in allowed[p])))

# ---------------- (b) status x code
sc = cube.pivot_table(index='status', columns='code', values='n', aggfunc='sum', fill_value=0)
print("\n(b) status x code\n", sc.to_string())
rej = ['05','14','51','54']
print("00 fuera de Approved:", S((cube.code=='00') & (cube.status!='Approved')),
      "| rechazo en Approved:", S(cube.code.isin(rej) & (cube.status=='Approved')),
      "| Approved con code nulo:", S((cube.status=='Approved') & (cube.code=='NULL')),
      f"({S((cube.status=='Approved') & (cube.code=='NULL'))/S(cube.status=='Approved')*100:.2f}% de Approved)")
print("code nulo % por status:", {s: round(S((cube.status==s)&(cube.code=='NULL'))/S(cube.status==s)*100, 2) for s in sc.index})

# ---------------- (c) merchant / mcat / tcat
fill = cube.groupby('ttype').apply(lambda g: pd.Series({'n': g.n.sum(), 'merch': (g.n*g.hm).sum(), 'mcat': (g.n*g.hmc).sum(), 'tcat': (g.n*g.htc).sum()}))
print("\n(c) llenado por ttype\n", fill.astype(int).to_string())
print("merchant fuera de Purchase:", S((cube.hm==1)&(cube.ttype!='Purchase')), "| mcat fuera de Purchase:", S((cube.hmc==1)&(cube.ttype!='Purchase')))
pur = cube.ttype=='Purchase'
print("Purchase con tcat y mcat:", S(pur&(cube.tceq>=0)), " iguales:", S(pur&(cube.tceq==1)), " distintos:", S(pur&(cube.tceq==0)))
print("Purchase merch sin mcat:", S(pur&(cube.hm==1)&(cube.hmc==0)), " mcat sin merch:", S(pur&(cube.hm==0)&(cube.hmc==1)),
      " sin merch:", S(pur&(cube.hm==0)), " sin tcat:", S(pur&(cube.htc==0)))
m = q("""select count(distinct merchant_name) n_merch, count(distinct lower(trim(merchant_name))) n_merch_norm,
  max(k) max_mcat, min(k) min_mcat from (select merchant_name, count(distinct mcat) k from tx where merchant_name is not null group by 1)""")
print(m.to_string())
print("comercios por mcat:", q("""select mcat, count(distinct merchant_name) k from tx where mcat is not null group by 1 order by 1""").set_index('mcat').k.to_dict())
# tcat derivable del comercio cuando mcat es nulo
d = q("""with mp as (select merchant_name, any_value(mcat) mc from tx where mcat is not null group by 1)
 select count(*) n, sum((t.tcat = mp.mc)::int) ok from tx t join mp using(merchant_name)
 where t.ttype='Purchase' and t.mcat is null and t.tcat is not null""")
print("Purchase con mcat nulo y tcat: tcat == mcat del comercio:", d.to_dict('records'))
# tcat fuera de Purchase
pay = q("""select p.ptype, t.tcat, count(*) n from tx t join pr p using(product_id) where t.ttype='Payment' and t.tcat is not null group by 1,2""")

def cramer(ct):
    o = ct.values.astype(float); n = o.sum()
    e = np.outer(o.sum(1), o.sum(0)) / n
    c2 = ((o - e) ** 2 / e).sum(); r, k = o.shape
    return np.sqrt(c2 / (n * (min(r, k) - 1))), c2, (r - 1) * (k - 1), chi2dist.sf(c2, (r - 1) * (k - 1))

pp = pay.pivot_table(index='ptype', columns='tcat', values='n', fill_value=0)
v, c2, df, p = cramer(pp)
print(f"Payment con tcat: {int(pp.values.sum()):,}/{S(cube.ttype=='Payment'):,}; V(ptype,tcat|Payment)={v:.4f} p={p:.3g}")
print((pp.div(pp.sum(1), axis=0) * 100).round(1).to_string())

# ---------------- (d) branch / lat / lon por canal
fc = cube.groupby('channel').apply(lambda g: pd.Series({'n': g.n.sum(), 'p_branch': (g.n*g.hb).sum()/g.n.sum(),
      'p_lat': (g.n*g.hla).sum()/g.n.sum(), 'p_lon': (g.n*g.hlo).sum()/g.n.sum(),
      'lat_xor_lon': (g.n*(g.hla != g.hlo)).sum(), 'ambos': (g.n*((g.hla==1)&(g.hlo==1))).sum()}))
print("\n(d) llenado por canal\n", fc.round(4).to_string())
phys2, phys3 = ['ATM','Branch'], ['ATM','Branch','POS']
print("branch fuera de ATM/Branch:", S((cube.hb==1)&~cube.channel.isin(phys2)),
      "| lat fuera de ATM/Branch/POS:", S((cube.hla==1)&~cube.channel.isin(phys3)),
      "| lon fuera de ATM/Branch/POS:", S((cube.hlo==1)&~cube.channel.isin(phys3)))
print(f"branch lleno en ATM/Branch: {S((cube.hb==1)&cube.channel.isin(phys2))/S(cube.channel.isin(phys2))*100:.2f}%"
      f" | lat llena en ATM/Branch/POS: {S((cube.hla==1)&cube.channel.isin(phys3))/S(cube.channel.isin(phys3))*100:.2f}%"
      f" | lon llena: {S((cube.hlo==1)&cube.channel.isin(phys3))/S(cube.channel.isin(phys3))*100:.2f}%"
      f" | lat y lon ambas: {S((cube.hla==1)&(cube.hlo==1)&cube.channel.isin(phys3))/S(cube.channel.isin(phys3))*100:.2f}%")
b = q("""select count(*) n, sum((b.branch_id is null)::int) no_existe, avg(case when b.branch_id is not null then (t.country=b.country)::int end) mismo_pais,
  avg(case when b.branch_id is not null then (t.city=b.city)::int end) misma_ciudad
 from tx t left join br b on t.branch_id=b.branch_id where t.branch_id is not null""")
print("branch_id de tx vs br:", b.round(4).to_dict('records'))

# ---------------- Adjustment
adj = cube.ttype=='Adjustment'
print("\nAdjustment total:", S(adj), f"({S(adj)/N*100:.2f}%)", "por ptype:",
      cube[adj].groupby('ptype').n.sum().sort_values(ascending=False).to_dict())
print("Adjustment con merchant/mcat/tcat:", S(adj&(cube.hm==1)), S(adj&(cube.hmc==1)), S(adj&(cube.htc==1)))
st = cube.pivot_table(index='ttype', columns='status', values='n', aggfunc='sum', fill_value=0)
print("status % por ttype\n", (st.div(st.sum(1), axis=0) * 100).round(2).to_string())
v, c2, df, p = cramer(st); print(f"V(ttype,status)={v:.4f} chi2={c2:.1f} df={df} p={p:.3g}")

# ---------------- canal vs tipo
for dim in ['ttype', 'ptype']:
    ct = cube.pivot_table(index=dim, columns='channel', values='n', aggfunc='sum', fill_value=0)
    v, c2, df, p = cramer(ct)
    share = ct.div(ct.sum(1), axis=0) * 100
    glob = ct.sum(0) / ct.values.sum() * 100
    print(f"\ncanal % por {dim}  V={v:.4f} chi2={c2:.1f} df={df} p={p:.3g}  max|dif vs global|={np.abs(share - glob).values.max():.3f} pp")
    print(share.round(2).to_string())
print("global:", (glob).round(2).to_dict())
