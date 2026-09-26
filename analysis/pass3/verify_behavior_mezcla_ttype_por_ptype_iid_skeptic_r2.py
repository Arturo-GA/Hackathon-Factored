"""Verificador escéptico (reintento r2) de 'behavior_mezcla_ttype_por_ptype_iid'.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_behavior_mezcla_ttype_por_ptype_iid_skeptic_r2.py <SEC>
  A  cobertura/dueño, soporte cerrado, pesos vs declarados (GOF), V global ptype/familia vs ttype (¿ya sabido V=0.48?)
  B  coherencia semántica de ttype con channel/tcat/mcat/merchant/status/monto (¿sirve de guardrail?)
  C  Markov lag-1/lag-2 dentro del producto con 3 órdenes (ts, transaction_id, process_date) y empates
  D  nivel cliente: ¿el ttype previo predice el ttype o el PRODUCTO siguiente? (estratificado + barajado)
  E  predictivo held-out agrupado por cliente: log-loss y AUC con/ sin historia, IC95 bootstrap por clúster de clientes
  F  día del mes (share de Deposit dentro de cuentas; cancela calendario) y ventanas de quincena
  G  ciclos depósito->retiro y compra->pago: tiempo y monto vs línea base
"""
import sys, warnings
warnings.filterwarnings("ignore")
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2 as chi2dist, chi2_contingency

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
TT = ['Adjustment', 'Deposit', 'Payment', 'Purchase', 'Transfer', 'Withdrawal']
DECL = {'Cuenta': {'Deposit': .25, 'Payment': .10, 'Transfer': .35, 'Withdrawal': .30},
        'Tarjeta': {'Purchase': .70, 'Payment': .15, 'Withdrawal': .15},
        'Otro': {'Payment': .60, 'Adjustment': .30, 'Transfer': .10}}
FAM = "CASE WHEN p.ptype LIKE 'Cuenta%' THEN 'Cuenta' WHEN p.ptype LIKE 'Tarjeta%' THEN 'Tarjeta' ELSE 'Otro' END"
fam_of = lambda s: 'Cuenta' if s.startswith('Cuenta') else ('Tarjeta' if s.startswith('Tarjeta') else 'Otro')


def cramer(tab):
    tab = np.asarray(tab, dtype=float)
    tab = tab[tab.sum(1) > 0][:, tab.sum(0) > 0]
    if min(tab.shape) < 2:
        return np.nan, np.nan, 0, tab.sum(), np.nan
    c2, p, dof, _ = chi2_contingency(tab, correction=False)
    n = tab.sum(); k = min(tab.shape) - 1
    return np.sqrt(c2 / n / k), p, dof, n, np.sqrt(dof / n / k)   # último: V esperado bajo H0 (~sqrt(E[chi2]/(n k)))


sec = sys.argv[1] if len(sys.argv) > 1 else 'A'

if sec == 'A':
    print("== A1. cobertura y dueño del producto ==")
    print(q("""SELECT count(*) n_tx, count(p.product_id) join_ok, sum((p.customer_id = t.customer_id)::INT) mismo_duenio,
               sum((p.customer_id <> t.customer_id)::INT) otro_duenio, sum((p.pstatus='Active')::INT) prod_activo
               FROM tx t LEFT JOIN pr p USING(product_id)""").to_string(index=False))
    ct = q("SELECT p.ptype, t.ttype, count(*) n FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2")
    pv = ct.pivot(index='ptype', columns='ttype', values='n').reindex(columns=TT).fillna(0).astype(int)
    print(pv.to_string())
    rows = []
    for pt, r in pv.iterrows():
        w = DECL[fam_of(pt)]; n = r.sum(); sup = list(w)
        fuera = int(r[[c for c in TT if c not in w]].sum())
        obs = r[sup] / n; exp = pd.Series(w)
        c2 = (((r[sup] - n * exp) ** 2) / (n * exp)).sum()
        rows.append(dict(ptype=pt, n=n, fuera_soporte=fuera, max_dev_pp=round(((obs - exp).abs() * 100).max(), 3),
                         gof_chi2=round(c2, 2), gof_p=round(chi2dist.sf(c2, len(sup) - 1), 3),
                         **{f"{c[:5]}%": round(r[c] / n * 100, 2) for c in TT}))
    print(pd.DataFrame(rows).to_string(index=False))
    print("== A2. ¿ya sabido? V global ptype x ttype, familia x ttype, y V intra-familia ==")
    V, p, dof, n, _ = cramer(pv.values); print(f"V(ptype, ttype) = {V:.4f}  (YA SABEMOS reporta 0.48)")
    fam = pv.groupby(pv.index.map(fam_of)).sum(); V2, *_ = cramer(fam.values); print(f"V(familia, ttype) = {V2:.4f}")
    for f in ['Cuenta', 'Tarjeta', 'Otro']:
        sub = pv[pv.index.map(fam_of) == f]
        Vf, pf, dof, nf, v0 = cramer(sub.values)
        print(f"  intra-familia {f:8s}: V={Vf:.4f} p={pf:.3f} n={int(nf)} (V nulo esperado~{v0:.4f})")
    # entropía: cuánta información del ttype aporta ptype vs familia
    def H(v):
        v = np.asarray(v, float); v = v[v > 0] / v.sum(); return -(v * np.log2(v)).sum()
    Ht = H(pv.values.sum(0)); Hc_pt = sum(pv.loc[i].sum() / pv.values.sum() * H(pv.loc[i].values) for i in pv.index)
    Hc_f = sum(fam.loc[i].sum() / fam.values.sum() * H(fam.loc[i].values) for i in fam.index)
    print(f"H(ttype)={Ht:.4f} bits; H(ttype|familia)={Hc_f:.4f}; H(ttype|ptype)={Hc_pt:.4f} -> ptype no agrega sobre familia: {Hc_f - Hc_pt:.5f} bits")
    print("== A3. pesos 'fijos': V ttype~X dentro de familia (n, V, V nulo) ==")
    dims = {'pais_tx': "t.country", 'anio': "year(t.ts)::VARCHAR", 'moneda': "t.currency", 'status': "t.status",
            'segmento_cli': "c.segment", 'cstatus': "c.cstatus", 'canal_apertura': "p.opening_channel",
            'anio_apertura': "year(p.opened)::VARCHAR", 'decil_monto': "ntile(10) OVER (PARTITION BY t.currency ORDER BY t.amount)::VARCHAR"}
    out = []
    for name, expr in dims.items():
        d = q(f"""WITH z AS (SELECT {FAM} fam, {expr} x, t.ttype FROM tx t JOIN pr p USING(product_id)
                  LEFT JOIN cu c ON c.customer_id = t.customer_id)
                  SELECT fam, x, ttype, count(*) n FROM z GROUP BY ALL""")
        for f, g in d.groupby('fam'):
            tab = g.pivot_table(index='x', columns='ttype', values='n', aggfunc='sum').fillna(0)
            Vx, px, dof, nx, v0 = cramer(tab.values)
            sh = tab[tab.sum(1) >= 5000]; sh = sh.div(sh.sum(1), axis=0) * 100
            rng = (sh.max() - sh.min()).max() if len(sh) > 1 else np.nan
            out.append(dict(dim=name, fam=f, niveles=len(tab), n=int(nx), V=round(Vx, 4), V_nulo=round(v0, 4), p=px, rango_pp=round(rng, 2)))
    o = pd.DataFrame(out)
    print(o.to_string(index=False))

if sec == 'B':
    print("== B. coherencia semántica de ttype (¿el guardrail se extiende a canal/categoría?) ==")
    for col in ['channel', "coalesce(tcat,'<NULL>')", "coalesce(mcat,'<NULL>')", "(merchant_name IS NULL)::VARCHAR", 'status', "coalesce(code,'<NULL>')",
                "(branch_id IS NULL)::VARCHAR", "CASE WHEN amount<0 THEN 'neg' WHEN amount=0 THEN 'cero' ELSE 'pos' END"]:
        d = q(f"SELECT ttype, {col} x, count(*) n FROM tx GROUP BY 1,2")
        tab = d.pivot_table(index='ttype', columns='x', values='n', aggfunc='sum').fillna(0)
        V, p, dof, n, v0 = cramer(tab.values)
        sh = (tab.div(tab.sum(1), axis=0) * 100).round(1)
        print(f"-- ttype x {col}: V={V:.4f} (nulo~{v0:.4f})")
        print(sh.iloc[:, :12].to_string())
    print(q("""SELECT ttype, currency, count(*) n, round(quantile_cont(amount, 0.5),2) med, round(quantile_cont(amount,0.99),2) p99
               FROM tx GROUP BY 1,2 ORDER BY 2,1""").to_string(index=False))

if sec == 'C':
    print("== C. Markov dentro del producto con 3 órdenes ==")
    print(q("""SELECT count(*) grupos_empate, sum(k) tx_en_empate FROM (SELECT product_id, ts, count(*) k FROM tx GROUP BY 1,2 HAVING count(*)>1)""").to_string(index=False))
    K = 8
    orders = {'ts': 't.ts, t.transaction_id', 'transaction_id': 't.transaction_id', 'process_date': 't.process_date, t.ts'}
    for oname, order in orders.items():
        parts = []
        for b in range(K):
            parts.append(q(f"""WITH z AS (SELECT p.ptype, t.ttype, lag(t.ttype,1) OVER w prev1, lag(t.ttype,2) OVER w prev2
                             FROM tx t JOIN pr p USING(product_id) WHERE hash(t.product_id) % {K} = {b}
                             WINDOW w AS (PARTITION BY t.product_id ORDER BY {order}))
                           SELECT ptype, prev1, coalesce(prev2,'-') prev2, ttype, count(*) n FROM z WHERE prev1 IS NOT NULL GROUP BY ALL"""))
        S = pd.concat(parts).groupby(['ptype', 'prev1', 'prev2', 'ttype']).n.sum().reset_index()
        print(f"-- orden por {oname}")
        tot_c2, tot_dof = 0.0, 0
        for pt, g in S.groupby('ptype'):
            t1 = g.pivot_table(index='prev1', columns='ttype', values='n', aggfunc='sum').fillna(0)
            V1, p1, dof1, n1, v0 = cramer(t1.values)
            g2 = g[g.prev2 != '-']
            t2 = g2.assign(h=g2.prev2 + '|' + g2.prev1).pivot_table(index='h', columns='ttype', values='n', aggfunc='sum').fillna(0)
            V2, p2, *_ = cramer(t2.values)
            lift = t1.values / (np.outer(t1.sum(1), t1.sum(0)) / t1.values.sum())
            tot_c2 += V1 ** 2 * n1 * (min(t1.shape) - 1); tot_dof += dof1
            print(f"  {pt:22s} n={int(n1):8d} V_lag1={V1:.4f} (nulo~{v0:.4f}) p={p1:.3f} | V_lag2(par)={V2:.4f} p={p2:.3f} | lift min/max={lift.min():.3f}/{lift.max():.3f}")
        print(f"  combinado 8 ptypes: chi2={tot_c2:.1f} dof={tot_dof} p={chi2dist.sf(tot_c2, tot_dof):.3f}")

if sec == 'D':
    print("== D. nivel cliente (25% de clientes): dependencias entre productos más allá de la composición ==")
    res = {}
    for lab, order in [('obs', 't.ts, t.transaction_id'), ('shuf', "hash(t.transaction_id || 'r2')")]:
        parts = []
        for b in range(4):
            parts.append(q(f"""WITH z AS (SELECT p.ptype, t.ttype, t.product_id,
                        lag(p.ptype) OVER w pptype, lag(t.ttype) OVER w prev, lag(t.product_id) OVER w pprod
                      FROM tx t JOIN pr p USING(product_id) WHERE hash(t.customer_id) % 16 = {b}
                      WINDOW w AS (PARTITION BY t.customer_id ORDER BY {order}))
                    SELECT pptype, prev, ptype, ttype, (pprod = product_id) same, count(*) n FROM z WHERE prev IS NOT NULL GROUP BY ALL"""))
        res[lab] = pd.concat(parts).groupby(['pptype', 'prev', 'ptype', 'ttype', 'same']).n.sum().reset_index()
    for lab, d in res.items():
        # (i) ttype_next ⟂ ttype_prev | (ptype_prev, ptype_next)
        c2s, dofs = 0.0, 0
        for _, h in d.groupby(['pptype', 'ptype']):
            tab = h.pivot_table(index='prev', columns='ttype', values='n', aggfunc='sum').fillna(0).values
            tab = tab[tab.sum(1) > 0][:, tab.sum(0) > 0]
            if min(tab.shape) >= 2:
                c2, _, dof, _ = chi2_contingency(tab, correction=False); c2s += c2; dofs += dof
        # (ii) ptype_next ⟂ ttype_prev | ptype_prev  (¿el tipo previo decide qué producto se usa después?)
        c2b, dofb, Vs = 0.0, 0, []
        for _, h in d.groupby('pptype'):
            tab = h.pivot_table(index='prev', columns='ptype', values='n', aggfunc='sum').fillna(0).values
            tab = tab[tab.sum(1) > 0][:, tab.sum(0) > 0]
            if min(tab.shape) >= 2:
                c2, _, dof, _ = chi2_contingency(tab, correction=False); c2b += c2; dofb += dof
        N = d.n.sum()
        print(f"[{lab}] N={N} P(mismo producto)={d[d.same].n.sum() / N:.4f} P(mismo ptype)={d[d.pptype == d.ptype].n.sum() / N:.4f}")
        print(f"   ttype⟂prev|(pptype,ptype): chi2={c2s:.1f} dof={dofs} p={chi2dist.sf(c2s, dofs):.3f}  V_equiv={np.sqrt(c2s / N / 5):.4f}")
        print(f"   ptype_next⟂prev|pptype:   chi2={c2b:.1f} dof={dofb} p={chi2dist.sf(c2b, dofb):.3f}  V_equiv={np.sqrt(c2b / N / 5):.4f}")
    # lift pooled (sin estratificar) para mostrar que es composición
    for lab, d in res.items():
        t = d.pivot_table(index='prev', columns='ttype', values='n', aggfunc='sum').fillna(0)
        lift = t / (np.outer(t.sum(1), t.sum(0)) / t.values.sum())
        print(f"[{lab}] lift pooled Adj->Adj={lift.loc['Adjustment', 'Adjustment']:.2f} Dep->Wd={lift.loc['Deposit', 'Withdrawal']:.3f} Pur->Pay={lift.loc['Purchase', 'Payment']:.3f} Dep->Dep={lift.loc['Deposit', 'Deposit']:.2f}")

if sec == 'E':
    print("== E. predictivo held-out agrupado por cliente (train hash%10<7, test >=7; 30 clústeres de test para bootstrap) ==")
    parts = []
    for b in range(8):
        parts.append(q(f"""WITH z AS (SELECT {FAM} fam, p.ptype, t.ttype, t.customer_id,
                        lag(t.ttype,1) OVER w prev1, lag(t.ttype,2) OVER w prev2,
                        epoch(t.ts - lag(t.ts) OVER w)/86400.0 gap
                      FROM tx t JOIN pr p USING(product_id) WHERE hash(t.product_id) % 8 = {b}
                      WINDOW w AS (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id))
                    SELECT fam, ptype, coalesce(prev1,'-') prev1, coalesce(prev2,'-') prev2,
                           CASE WHEN gap IS NULL THEN '-' WHEN gap<1 THEN 'a' WHEN gap<7 THEN 'b' WHEN gap<30 THEN 'c' WHEN gap<90 THEN 'd' ELSE 'e' END gb,
                           hash(customer_id) % 10 split, hash(customer_id || 'boot') % 30 clu, ttype, count(*) n FROM z GROUP BY ALL"""))
    D = pd.concat(parts).groupby(['fam', 'ptype', 'prev1', 'prev2', 'gb', 'split', 'clu', 'ttype']).n.sum().reset_index()
    tr_, te_ = D[D.split < 7], D[D.split >= 7]
    rng = np.random.default_rng(7)

    def fit(keys, alpha=1.0):
        c = tr_.groupby(keys + ['ttype']).n.sum().unstack(fill_value=0)
        c = c + alpha * (c > -1)  # suavizado de Laplace sobre las 6 clases
        return (c.div(c.sum(1), axis=0)).stack().rename('p').reset_index()

    models = {'ptype': ['ptype'], 'ptype+prev1': ['ptype', 'prev1'], 'ptype+prev1+prev2+gap': ['ptype', 'prev1', 'prev2', 'gb']}
    base = te_.merge(fit(['ptype']), on=['ptype', 'ttype'], how='left')
    ll0 = base.assign(l=-base.n * np.log(base.p)).groupby('clu').agg(l=('l', 'sum'), n=('n', 'sum'))
    for mname, keys in models.items():
        m = te_.merge(fit(keys), on=keys + ['ttype'], how='left')
        m['p'] = m.p.fillna(base.p)
        llm = m.assign(l=-m.n * np.log(m.p)).groupby('clu').agg(l=('l', 'sum'), n=('n', 'sum'))
        imp = (ll0.l - llm.l)
        point = imp.sum() / ll0.n.sum()
        bs = []
        for _ in range(500):
            idx = rng.integers(0, len(imp), len(imp))
            bs.append(imp.values[idx].sum() / ll0.n.values[idx].sum())
        print(f"  {mname:24s} logloss={llm.l.sum() / llm.n.sum():.5f} nats; mejora vs ptype={point:+.6f} IC95=[{np.percentile(bs, 2.5):+.6f},{np.percentile(bs, 97.5):+.6f}] "
              f"({point / (ll0.l.sum() / ll0.n.sum()) * 100:+.3f}%)")
    # AUC one-vs-rest dentro de familia usando P(clase | ptype, prev1, prev2, gap) (score categórico, empates a medias)
    keys = ['ptype', 'prev1', 'prev2', 'gb']
    P = fit(keys)
    for f, cls in [('Cuenta', 'Withdrawal'), ('Cuenta', 'Deposit'), ('Tarjeta', 'Payment'), ('Otro', 'Adjustment')]:
        t = te_[te_.fam == f]
        g = t.assign(pos=np.where(t.ttype == cls, t.n, 0), neg=np.where(t.ttype != cls, t.n, 0)).groupby(keys + ['clu'])[['pos', 'neg']].sum().reset_index()
        s = P[P.ttype == cls][keys + ['p']]
        g = g.merge(s, on=keys, how='left').fillna({'p': 0})

        def auc(gg):
            a = gg.groupby('p')[['pos', 'neg']].sum().sort_index()
            nb = a.neg.cumsum() - a.neg
            return ((a.pos * (nb + 0.5 * a.neg)).sum()) / (a.pos.sum() * a.neg.sum())
        point = auc(g)
        clus = g.clu.unique(); bs = []
        byc = {c: g[g.clu == c] for c in clus}
        for _ in range(300):
            pick = rng.choice(clus, len(clus))
            bs.append(auc(pd.concat([byc[c] for c in pick])))
        print(f"  AUC {f}:{cls:10s} = {point:.4f} IC95=[{np.percentile(bs, 2.5):.4f},{np.percentile(bs, 97.5):.4f}]  n_test={int(g.pos.sum() + g.neg.sum())}")

if sec == 'F':
    print("== F. día del mes: share de Deposit entre tx de cuentas (cancela el efecto calendario) ==")
    d = q("""SELECT day(t.ts) d, count(*) n, sum((t.ttype='Deposit')::INT) k, sum((t.ttype='Withdrawal')::INT) w
             FROM tx t JOIN pr p USING(product_id) WHERE p.ptype LIKE 'Cuenta%' GROUP BY 1 ORDER BY 1""")
    d['dep%'] = d.k / d.n * 100; d['wd%'] = d.w / d.n * 100
    V, p, dof, n, v0 = cramer(np.c_[d.k, d.n - d.k])
    print(f"Deposit share por día: min={d['dep%'].min():.2f}% max={d['dep%'].max():.2f}% V={V:.4f} (nulo~{v0:.4f}) p={p:.3f}")
    print(d[d.d.isin([1, 2, 14, 15, 16, 28, 29, 30, 31])][['d', 'n', 'dep%', 'wd%']].round(2).T.to_string())
    e = q("""SELECT (day(t.ts) IN (1,15,16) OR day(t.ts) >= day(last_day(t.ts))-1) quincena, count(*) n,
                    avg((t.ttype='Deposit')::INT)*100 dep_pct FROM tx t JOIN pr p USING(product_id) WHERE p.ptype LIKE 'Cuenta%' GROUP BY 1""")
    print(e.to_string(index=False))
    # distribución de todas las tx de cuentas por día (efecto calendario puro)
    cal = q("SELECT day(x) d, count(*) nd FROM (SELECT unnest(generate_series(DATE '2023-06-17', DATE '2026-06-17', INTERVAL 1 DAY)) x) GROUP BY 1")
    m = d.merge(cal, on='d'); m['dep_share_de_depositos%'] = m.k / m.k.sum() * 100; m['esperado_cal%'] = m.nd / m.nd.sum() * 100
    print("Deposit %% del total de depósitos, días 1-30: min=%.2f max=%.2f; día 30=%.2f (esperado calendario %.2f); día 31=%.2f (esp %.2f)" % (
        m[m.d <= 30]['dep_share_de_depositos%'].min(), m[m.d <= 30]['dep_share_de_depositos%'].max(),
        m[m.d == 30]['dep_share_de_depositos%'].iloc[0], m[m.d == 30]['esperado_cal%'].iloc[0],
        m[m.d == 31]['dep_share_de_depositos%'].iloc[0], m[m.d == 31]['esperado_cal%'].iloc[0]))

if sec == 'G':
    print("== G. ciclos: depósito->retiro (cuentas) y compra->pago (tarjeta crédito): tiempo y monto ==")
    parts = []
    for b in range(4):
        parts.append(q(f"""WITH z AS (SELECT p.ptype, t.ttype, t.amount, t.ts,
                        lead(t.ttype) OVER w nt, lead(t.amount) OVER w na, epoch(lead(t.ts) OVER w - t.ts)/86400.0 g
                      FROM tx t JOIN pr p USING(product_id) WHERE hash(t.product_id) % 16 = {b}
                        AND (p.ptype LIKE 'Cuenta%' OR p.ptype='Tarjeta Crédito')
                      WINDOW w AS (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id))
                    SELECT CASE WHEN ptype LIKE 'Cuenta%' THEN 'Cuenta' ELSE 'TC' END fam, ttype prev, nt nxt,
                      CASE WHEN g<1 THEN '1:<1d' WHEN g<7 THEN '2:<7d' WHEN g<30 THEN '3:<30d' ELSE '4:>=30d' END gb, count(*) n,
                      sum((abs(na/amount-1)<0.05)::INT) n_monto5, sum((na<=amount)::INT) n_menor
                    FROM z WHERE nt IS NOT NULL AND amount>0 GROUP BY ALL"""))
    G = pd.concat(parts).groupby(['fam', 'prev', 'nxt', 'gb']).sum().reset_index()
    for fam, a, c in [('Cuenta', 'Deposit', 'Withdrawal'), ('Cuenta', 'Deposit', 'Transfer'), ('TC', 'Purchase', 'Payment')]:
        h = G[G.fam == fam]
        rows = []
        for gb, hh in h.groupby('gb'):
            A = hh[hh.prev == a]; B = hh[hh.prev != a]
            pa = A[A.nxt == c].n.sum() / A.n.sum(); pb = B[B.nxt == c].n.sum() / B.n.sum()
            ma = A[A.nxt == c].n_monto5.sum() / max(A[A.nxt == c].n.sum(), 1); mb = B[B.nxt == c].n_monto5.sum() / max(B[B.nxt == c].n.sum(), 1)
            rows.append(dict(gap=gb, n_tras_A=int(A.n.sum()), P_next_C_tras_A=round(pa * 100, 2), P_next_C_tras_otro=round(pb * 100, 2),
                             razon=round(pa / pb, 3), pct_monto_5pct_tras_A=round(ma * 100, 2), pct_monto_5pct_tras_otro=round(mb * 100, 2)))
        print(f"-- {fam}: {a} -> {c}"); print(pd.DataFrame(rows).to_string(index=False))
