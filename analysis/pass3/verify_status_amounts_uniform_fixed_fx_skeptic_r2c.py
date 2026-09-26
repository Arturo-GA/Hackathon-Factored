# Verificador escéptico r2c: ¿el monto depende de algo más que ttype? (eta² por variable, ICC por cliente) y nulos de amount_usd MCAR
import duckdb, time, numpy as np, pandas as pd
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
B = {'Purchase':(5,500),'Withdrawal':(20,500),'Payment':(50,2000),'Deposit':(50,5000),'Transfer':(100,10000),'Adjustment':(10,1000)}
bexpr = "case t.ttype " + " ".join(f"when '{k}' then {a}" for k,(a,b) in B.items()) + " end"
wexpr = "case t.ttype " + " ".join(f"when '{k}' then {b-a}" for k,(a,b) in B.items()) + " end"
kexpr = "case t.currency when 'COP' then 4000.0 when 'ARS' then 350.0 else 1.0 end"
U = f"((t.amount/{kexpr} - {bexpr})/{wexpr})"
feats = {
 'status':'t.status', 'code':"coalesce(t.code,'NULL')", 'fraud':'t.fraud', 'fscore_bin':"coalesce(floor(t.fscore/10)::varchar,'NULL')",
 'channel':'t.channel', 'currency':'t.currency', 'country_tx':'t.country', 'mcat':"coalesce(t.mcat,'NULL')", 'tcat':"coalesce(t.tcat,'NULL')",
 'year_month':"strftime(t.ts,'%Y-%m')", 'dow':'dayofweek(t.ts)', 'hour':'hour(t.ts)',
 'ptype':'p.ptype', 'segment':'c.segment', 'cstatus':'c.cstatus', 'income_dec':'least(9, floor(c.income/ (select quantile_cont(income,0.1) from cu)))::int',
 'credit_dec':"floor(c.credit_score/50)::int", 'country_cli':'c.country', 'occupation':'c.occupation', 'merchant':"coalesce(t.merchant_name,'NULL')",
}
base = "from tx t join pr p using(product_id) join cu c on c.customer_id=t.customer_id"
tot = con.execute(f"select count(*), avg({U}), var_pop({U}) {base}").fetchone()
N, mu, V = tot
print(f"N={N} media_u={mu:.5f} var_u={V:.5f} (uniforme: 0.5, {1/12:.5f})\n")
rows = []
for name, e in feats.items():
    d = con.execute(f"select {e} k, count(*) n, avg({U}) m {base} group by 1").df()
    ssb = (d.n*(d.m-mu)**2).sum()/N
    eta2 = ssb/V
    k = len(d)
    eta2_null = (k-1)/(N-1)   # valor esperado de eta² bajo independencia
    dd = d[d.n >= 1000]
    rows.append(dict(var=name, niveles=k, eta2=f"{eta2:.2e}", eta2_azar=f"{eta2_null:.2e}", ratio=round(eta2/eta2_null,2),
                     m_min=round(dd.m.min(),4), m_max=round(dd.m.max(),4), n_min=int(dd.n.min()) if len(dd) else 0))
print("== 1. eta² de u=(monto_usd-a)/(b-a) por variable (u es uniforme(0,1) si solo depende de ttype) ==")
print(pd.DataFrame(rows).to_string(), '\n', flush=True)
print(f"[t={time.time()-t0:.0f}s]")

print("== 2. ¿efecto cliente/producto? varianza de la media de u por cliente vs binomial esperada ==")
for key in ['t.customer_id', 't.product_id']:
    d = con.execute(f"select {key} k, count(*) n, avg({U}) m from tx t group by 1 having count(*)>=10").df()
    exp_var = ((1/12)/d.n).mean()
    print(key, "grupos", len(d), "var_obs", round(d.m.var(),6), "var_esperada", round(exp_var,6), "ratio", round(d.m.var()/exp_var,3))
print()
print("== 3. autocorrelacion secuencial de u dentro de producto ==")
r = con.execute(f"""with s as (select {U} u, lag({U}) over (partition by t.product_id order by t.ts, t.transaction_id) pu from tx t)
                   select corr(u, pu), count(pu) from s""").fetchone()
print("corr(u, u_prev) =", round(r[0],5), "n =", r[1], '\n')
print(f"[t={time.time()-t0:.0f}s]")

print("== 4. nulos de amount_usd en COP/ARS: tasa por variable ==")
nf = {'currency':'t.currency','ttype':'t.ttype','status':'t.status','channel':'t.channel','fraud':'t.fraud','year':'year(t.ts)',
      'u_decil':f"least(9,floor({U}*10))::int", 'segment':'c.segment', 'ptype':'p.ptype'}
rows = []
for name, e in nf.items():
    d = con.execute(f"select {e} k, count(*) n, avg((t.amount_usd is null)::int) r {base} where t.currency in ('COP','ARS') group by 1").df()
    d = d[d.n >= 1000]
    rows.append(dict(var=name, niveles=len(d), r_min=round(d.r.min()*100,3), r_max=round(d.r.max()*100,3), razon=round(d.r.max()/d.r.min(),3)))
print(pd.DataFrame(rows).to_string(), '\n')
print(f"[t={time.time()-t0:.0f}s]")
