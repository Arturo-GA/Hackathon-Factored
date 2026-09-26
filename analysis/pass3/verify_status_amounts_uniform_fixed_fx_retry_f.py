"""Verificacion (retry) status_amounts_uniform_fixed_fx. Parte F: aleatoriedad de nulos de amount_usd en COP/ARS; independencia del monto normalizado (u) respecto de status/code/fraude/canal/cliente."""
import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def cramer(rows):
    # rows: (cat, n, n_null)
    obs = np.array([[r[2], r[1]-r[2]] for r in rows], dtype=float)
    chi2, p, dof, _ = stats.chi2_contingency(obs, correction=False)
    return np.sqrt(chi2/obs.sum()), p
print("== nulos de amount_usd en COP/ARS por variable (tasa %, min-max entre categorias, V de Cramer)")
for col in ["ttype","status","channel","coalesce(code,'nulo')","fraud","year(ts)","country","currency","case when fscore is null then 'nulo' else 'con' end","dayofweek(ts)","hour(ts)"]:
    rows = con.execute(f"select {col} c, count(*) n, sum(case when amount_usd is null then 1 else 0 end) nn from tx where currency<>'USD' group by 1 order by 1").fetchall()
    rates = [100*r[2]/r[1] for r in rows if r[1] >= 1000]
    V, p = cramer([r for r in rows if r[1] >= 1000])
    print(f"{col[:40]:40s} k={len(rates):3d} tasa_min={min(rates):.2f}% tasa_max={max(rates):.2f}% V={V:.4f} p={p:.3g}")
# nulos por cliente: sobredispersion?
r = con.execute("""with c as (select customer_id, count(*) n, sum(case when amount_usd is null then 1 else 0 end) k from tx where currency<>'USD' group by 1)
 select count(*) n_cli, sum(n) N, sum(k) K, sum(n*(n-1)) s_nn from c""").fetchone()
p0 = r[2]/r[1]
rows = con.execute("select n, k from (select customer_id, count(*) n, sum(case when amount_usd is null then 1 else 0 end) k from tx where currency<>'USD' group by 1)").fetchnumpy()
n, k = rows['n'].astype(float), rows['k'].astype(float)
chi = ((k - n*p0)**2/(n*p0*(1-p0))).sum(); dof = len(n)-1
print(f"== nulos por cliente: {len(n)} clientes, p0={p0:.4f}, dispersion chi2/dof={chi/dof:.4f} (1=binomial pura), p={stats.chi2.sf(chi,dof):.3g}")
# u normalizado por status/code/fraude/canal
B = "(values ('Purchase',5,500),('Withdrawal',20,500),('Payment',50,2000),('Deposit',50,5000),('Transfer',100,10000),('Adjustment',10,1000)) v(ttype,a,b)"
U = "((t.amount/(case t.currency when 'COP' then 4000 when 'ARS' then 350 else 1 end) - v.a)/(v.b-v.a))"
print("== media de u=(monto_usd-a)/(b-a) por grupo (esperado 0.5; ee aprox 0.2887/sqrt(n))")
for col in ["t.status","coalesce(t.code,'nulo')","t.fraud","t.channel","t.country"]:
    rows = con.execute(f"select {col} c, count(*) n, avg({U}) m from tx t join {B} using(ttype) group by 1 order by 1").fetchall()
    s = "; ".join(f"{r[0]}:{r[2]:.4f}(n={r[1]})" for r in rows)
    zmax = max(abs(r[2]-0.5)/(0.2887/np.sqrt(r[1])) for r in rows)
    print(f"{col}: {s} | |z|max={zmax:.2f}")
# AUC de u para Declined vs Approved y fraude, muestra por hash
smp = con.execute(f"select {U} u, t.status, t.fraud from tx t join {B} using(ttype) where hash(t.transaction_id) % 15 = 0").fetchnumpy()
u = smp['u']; st = smp['status']; fr = smp['fraud']
from sklearn.metrics import roc_auc_score
m = np.isin(st, ['Approved','Declined'])
print(f"== AUC u -> Declined vs Approved (n={m.sum()}): {roc_auc_score(st[m]=='Declined', u[m]):.4f}; AUC u -> fraude (n={len(u)}, pos={int(fr.sum())}): {roc_auc_score(fr.astype(int), u):.4f}")
# efecto cliente: ICC de u (ANOVA de un factor)
r = con.execute(f"""with d as (select t.customer_id, {U} u from tx t join {B} using(ttype)),
 c as (select customer_id, count(*) n, avg(u) m, var_samp(u) v from d group by 1 having count(*)>=2)
 select count(*) C, sum(n) N, sum(n*m) S, sum(n*m*m) SS, sum((n-1)*v) SSW from c""").fetchone()
C, N, S, SS, SSW = r
grand = S/N; SSB = SS - N*grand**2
MSB = SSB/(C-1); MSW = SSW/(N-C); n0 = N/C
icc = (MSB-MSW)/(MSB+(n0-1)*MSW)
F = MSB/MSW
print(f"== efecto cliente sobre u: clientes={C}, tx={N}, F={F:.4f}, p={stats.f.sf(F, C-1, N-C):.3g}, ICC={icc:.5f}")
