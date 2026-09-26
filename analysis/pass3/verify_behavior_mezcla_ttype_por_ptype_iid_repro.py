"""Verificación independiente (reintento) de 'behavior_mezcla_ttype_por_ptype_iid'.

Afirmación a verificar:
  (1) ttype tiene soporte cerrado y pesos fijos por familia de producto:
      Cuentas  -> Deposit .25, Payment .10, Transfer .35, Withdrawal .30
      Tarjetas -> Purchase .70, Payment .15, Withdrawal .15
      Otros (Préstamos, Inversión, Seguro) -> Payment .60, Adjustment .30, Transfer .10
  (2) dentro de un producto la secuencia de ttype es iid (sin Markov, sin ciclos depósito->retiro)
  (3) día del mes plano para depósitos (sin nómina / quincena).

Secciones (argv[1]):
  A  cobertura, tabla ptype x ttype, violaciones de soporte, desvío vs pesos, GOF, homogeneidad intra-familia
  B  heterogeneidad de la mezcla dentro de cada ptype frente a covariables (¿"pesos fijos" o dependen de algo?)
  C  sobredispersión por producto (¿cada producto tiene su propia mezcla?) con nulo simulado
  D  Markov orden 1 y 2 dentro del producto + log-loss held-out (split por cliente, bootstrap por cliente)
  E  ciclos depósito->retiro en cuentas: probabilidad por gap, gaps y montos
  F  día del mes / quincena para depósitos
  G  nivel cliente (entre productos): independencia condicional dado (ptype previo, ptype siguiente)
  F2 día del mes: ¿la desviación vs calendario es de depósitos o de todo el volumen?
  F3 sobredispersión del volumen diario (día de semana + ruido por fecha)
  B2 mezcla dentro de ptype vs día de semana, hora y día del mes

Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_behavior_mezcla_ttype_por_ptype_iid_repro.py A
"""
import sys
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import chi2 as chi2d, chi2_contingency

pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")


def Q(s):
    return con.execute(s).df()


TT = ['Adjustment', 'Deposit', 'Payment', 'Purchase', 'Transfer', 'Withdrawal']
W = {
    'Cuenta': {'Deposit': .25, 'Payment': .10, 'Transfer': .35, 'Withdrawal': .30},
    'Tarjeta': {'Purchase': .70, 'Payment': .15, 'Withdrawal': .15},
    'Otro': {'Payment': .60, 'Adjustment': .30, 'Transfer': .10},
}
FAM = {'Cuenta Ahorro': 'Cuenta', 'Cuenta Corriente': 'Cuenta', 'Tarjeta Crédito': 'Tarjeta', 'Tarjeta Débito': 'Tarjeta',
       'Préstamo Hipotecario': 'Otro', 'Préstamo Personal': 'Otro', 'Inversión': 'Otro', 'Seguro': 'Otro'}
FAMSQL = "CASE WHEN p.ptype LIKE 'Cuenta%' THEN 'Cuenta' WHEN p.ptype LIKE 'Tarjeta%' THEN 'Tarjeta' ELSE 'Otro' END"


def ctab_stats(tab):
    """chi2 de independencia sin corrección, V de Cramér, V esperado bajo H0 y p."""
    tab = np.asarray(tab, dtype=float)
    tab = tab[tab.sum(1) > 0][:, tab.sum(0) > 0]
    if min(tab.shape) < 2:
        return dict(n=tab.sum(), chi2=np.nan, dof=0, p=np.nan, V=np.nan, V0=np.nan)
    c2, p, dof, _ = chi2_contingency(tab, correction=False)
    n = tab.sum(); k = min(tab.shape) - 1
    return dict(n=n, chi2=c2, dof=dof, p=p, V=np.sqrt(c2 / n / k), V0=np.sqrt(dof / n / k))


def mi_bits(tab):
    tab = np.asarray(tab, dtype=float); N = tab.sum()
    pxy = tab / N; px = pxy.sum(1, keepdims=True); py = pxy.sum(0, keepdims=True)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.nansum(np.where(pxy > 0, pxy * np.log2(pxy / (px * py)), 0.0))


sec = sys.argv[1] if len(sys.argv) > 1 else 'A'

# ---------------------------------------------------------------------------------------------
if sec == 'A':
    print("== A. cobertura ==")
    print(Q("""SELECT count(*) n_tx, count(p.product_id) n_con_producto, count(*) FILTER (WHERE t.ttype IS NULL) ttype_nulo,
                      count(*) FILTER (WHERE p.product_id IS NOT NULL AND t.customer_id <> p.customer_id) tx_cliente_distinto_al_dueno,
                      count(DISTINCT t.product_id) productos_con_tx
               FROM tx t LEFT JOIN pr p USING(product_id)""").T)
    ct = Q("SELECT p.ptype, t.ttype, count(*) n FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2")
    pv = ct.pivot(index='ptype', columns='ttype', values='n').reindex(columns=TT).fillna(0).astype(np.int64)
    print(pv.assign(total=pv.sum(1)).to_string())
    rows = []
    for pt, r in pv.iterrows():
        fam = FAM[pt]; w = W[fam]; n = int(r.sum())
        sup = list(w)
        off = int(r[[k for k in TT if k not in w]].sum())
        obs = r[sup] / n; exp = pd.Series(w)
        dev = (obs - exp) * 100
        e = n * exp
        c2 = float((((r[sup] - e) ** 2) / e).sum())
        se_pp = np.sqrt(exp * (1 - exp) / n) * 100
        rows.append(dict(ptype=pt, fam=fam, n=n, fuera_soporte=off,
                         mezcla_obs=' '.join(f"{k[:3]}={obs[k]*100:.2f}" for k in sup),
                         max_abs_dev_pp=round(dev.abs().max(), 3), max_z=round((dev / se_pp).abs().max(), 2),
                         IC95_mitad_pp_max=round(1.96 * se_pp.max(), 3), chi2_gof=round(c2, 2), dof=len(sup) - 1,
                         p_gof=chi2d.sf(c2, len(sup) - 1)))
    out = pd.DataFrame(rows)
    print(out.to_string())
    print("violaciones de soporte totales:", int(out.fuera_soporte.sum()), "de", int(out.n.sum()))
    # Fisher combinado de los GOF (¿los pesos declarados son los del generador?)
    c = -2 * np.log(out.p_gof.clip(lower=1e-300)).sum()
    print(f"Fisher combinado de 8 GOF: X2={c:.2f} dof=16 p={chi2d.sf(c, 16):.3g}")
    for fam in ['Cuenta', 'Tarjeta', 'Otro']:
        pts = [k for k, v in FAM.items() if v == fam]
        s = ctab_stats(pv.loc[pts].values)
        print(f"homogeneidad intra-familia {fam} ({len(pts)} ptypes): V={s['V']:.4f} (V_nulo~{s['V0']:.4f}) chi2={s['chi2']:.2f} dof={s['dof']} p={s['p']:.3g}")
    # familia x ttype: reglas de exclusión usadas en la explotación
    print(Q(f"""SELECT t.ttype, {FAMSQL} fam, count(*) n FROM tx t JOIN pr p USING(product_id)
               WHERE t.ttype IN ('Purchase','Deposit','Adjustment') GROUP BY 1,2 ORDER BY 1,2""").to_string())

# ---------------------------------------------------------------------------------------------
if sec == 'B':
    print("== B. heterogeneidad de la mezcla dentro de cada ptype ==")
    covs = {
        'pais_tx': "t.country",
        'anio_tx': "year(t.ts)::VARCHAR",
        'trimestre_tx': "(year(t.ts)*10+quarter(t.ts))::VARCHAR",
        'status_tx': "t.status",
        'moneda': "t.currency",
        'segmento_cli': "c.segment",
        'n_productos_cli': "least(np.nprod, 6)::VARCHAR",
        'cli_tiene_tarjeta': "np.has_card::VARCHAR",
        'cli_tiene_cuenta': "np.has_acc::VARCHAR",
        'anio_apertura_prod': "least(greatest(year(p.opened), 2015), 2026)::VARCHAR",
    }
    res = []
    for name, expr in covs.items():
        d = Q(f"""WITH np AS (SELECT customer_id, count(*) nprod, max((ptype LIKE 'Tarjeta%')::INT) has_card,
                                  max((ptype LIKE 'Cuenta%')::INT) has_acc FROM pr GROUP BY 1)
                  SELECT p.ptype, coalesce({expr}, 'NULL') lvl, t.ttype, count(*) n
                  FROM tx t JOIN pr p USING(product_id) LEFT JOIN cu c ON c.customer_id = t.customer_id
                  LEFT JOIN np ON np.customer_id = t.customer_id GROUP BY 1,2,3""")
        for pt, g in d.groupby('ptype'):
            tb = g.pivot(index='lvl', columns='ttype', values='n').fillna(0)
            s = ctab_stats(tb.values)
            big = tb[tb.sum(1) >= 3000]
            sh = big.div(big.sum(1), axis=0) * 100
            rng = float((sh.max() - sh.min()).max()) if len(big) > 1 else np.nan
            res.append(dict(cov=name, ptype=pt, niveles=len(tb), n=int(s['n']), V=s['V'], V0=s['V0'], p=s['p'], rango_pp=rng))
    r = pd.DataFrame(res)
    print("V de Cramér (ttype x covariable) dentro de cada ptype:")
    print(r.pivot(index='cov', columns='ptype', values='V').round(4).to_string())
    print("V esperado bajo independencia (sqrt(dof/n/k)):")
    print(r.pivot(index='cov', columns='ptype', values='V0').round(4).to_string())
    print("p-values:")
    print(r.pivot(index='cov', columns='ptype', values='p').map(lambda x: f"{x:.2g}").to_string())
    print("rango máximo (pp) del % de un ttype entre niveles con n>=3000:")
    print(r.pivot(index='cov', columns='ptype', values='rango_pp').round(2).to_string())
    print("tests con p<0.001:", int((r.p < 1e-3).sum()), "de", len(r), "; p<0.05:", int((r.p < 0.05).sum()))

# ---------------------------------------------------------------------------------------------
if sec == 'C':
    print("== C. sobredispersión por producto (nulo simulado multinomial con los mismos n_i) ==")
    ks = ", ".join([f"sum((t.ttype='{k}')::INT) k_{k}" for k in TT])
    rng = np.random.default_rng(7)
    for fam, w in W.items():
        sup = list(w)
        d = Q(f"""SELECT t.product_id, count(*) n, {ks} FROM tx t JOIN pr p USING(product_id)
                 WHERE {FAMSQL} = '{fam}' GROUP BY 1""")
        n = d.n.values.astype(np.int64)
        K = np.c_[[d[f"k_{k}"].values for k in sup]].T.astype(np.int64)
        phat = K.sum(0) / n.sum()

        def disp(Kmat, nvec, pv):
            num = ((Kmat - np.outer(nvec, pv)) ** 2).sum(0)
            den = (np.outer(nvec, pv * (1 - pv))).sum(0)
            return num / den
        Dobs = disp(K, n, phat)
        sims = []
        for _ in range(30):
            # multinomial vectorizada por producto (binomiales condicionales secuenciales)
            rem = n.copy(); pr_rem = 1.0; cols = []
            for j, pj in enumerate(phat):
                if j == len(phat) - 1:
                    cols.append(rem.copy())
                else:
                    x = rng.binomial(rem, min(pj / pr_rem, 1.0)); cols.append(x); rem = rem - x; pr_rem -= pj
            Ks = np.column_stack(cols)
            ph = Ks.sum(0) / n.sum()
            sims.append(disp(Ks, n, ph))
        sims = np.array(sims)
        print(f"-- {fam}: productos={len(n)} tx={n.sum()} n_medio={n.mean():.2f} p_hat={dict(zip(sup, phat.round(4)))}")
        for j, k in enumerate(sup):
            print(f"   {k:11s} D_obs={Dobs[j]:.4f}  nulo sim: media={sims[:, j].mean():.4f} sd={sims[:, j].std():.4f}  z={(Dobs[j]-sims[:, j].mean())/sims[:, j].std():.2f}")
        # varianza de la fracción por producto entre productos grandes vs binomial
        big = n >= 25
        if big.sum() > 100:
            f = K[big] / n[big, None]
            print(f"   productos con n>=25: {big.sum()}; sd observada de la fracción por producto vs binomial esperada:",
                  {k: (round(f[:, j].std(), 4), round(np.sqrt((phat[j] * (1 - phat[j]) / n[big]).mean()), 4)) for j, k in enumerate(sup)})
        del d, K

# ---------------------------------------------------------------------------------------------
if sec == 'D':
    print("== D. Markov dentro del producto ==")
    m = Q("""WITH s AS (SELECT p.ptype, t.ttype, t.ts, lag(t.ttype, 1) OVER w prev1, lag(t.ttype, 2) OVER w prev2, lag(t.ts) OVER w pts
                        FROM tx t JOIN pr p USING(product_id)
                        WINDOW w AS (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id))
             SELECT ptype, coalesce(prev2, '-') prev2, prev1, ttype, count(*) n, sum((ts = pts)::INT) empates
             FROM s WHERE prev1 IS NOT NULL GROUP BY ALL""")
    print(f"pares consecutivos dentro de producto: {int(m.n.sum())}; con ts idéntico: {int(m.empates.sum())}")
    rows = []
    for pt, g in m.groupby('ptype'):
        t1 = g.groupby(['prev1', 'ttype']).n.sum().unstack(fill_value=0)
        s1 = ctab_stats(t1.values)
        rp = t1.div(t1.sum(1), axis=0); mg = t1.sum(0) / t1.values.sum()
        maxdev = float(((rp - mg).abs().max().max()) * 100)
        lift = rp / mg
        H = -(mg[mg > 0] * np.log2(mg[mg > 0])).sum()
        g2 = g[g.prev2 != '-']
        c2s, dfs = 0.0, 0
        for _, h in g2.groupby('prev1'):
            tb = h.groupby(['prev2', 'ttype']).n.sum().unstack(fill_value=0).values
            tb = tb[tb.sum(1) > 0][:, tb.sum(0) > 0]
            if min(tb.shape) >= 2:
                c2, _, dof, _ = chi2_contingency(tb, correction=False); c2s += c2; dfs += dof
        rows.append(dict(ptype=pt, n_pares=int(s1['n']), V_lag1=round(s1['V'], 4), V_nulo=round(s1['V0'], 4), chi2=round(s1['chi2'], 1),
                         dof=s1['dof'], p_lag1=round(s1['p'], 4), max_dev_pp=round(maxdev, 3),
                         lift_min=round(float(lift.values[np.isfinite(lift.values)].min()), 4), lift_max=round(float(lift.values[np.isfinite(lift.values)].max()), 4),
                         MI_bits=f"{mi_bits(t1.values):.2e}", H_bits=round(H, 3), p_orden2_cond=round(chi2d.sf(c2s, dfs), 4)))
    r = pd.DataFrame(rows)
    print(r.to_string())
    # lift pooled (sin estratificar por ptype) para Adjustment->Adjustment y análogos: composición
    pool = m.groupby(['prev1', 'ttype']).n.sum().unstack(fill_value=0)
    rp = pool.div(pool.sum(1), axis=0); mg = pool.sum(0) / pool.values.sum()
    L = rp / mg
    print("pooled (todos los ptypes) lift diag:", {k: round(L.loc[k, k], 2) for k in L.index})
    # esperado por composición: sum_ptype w(prev|ptype) share -> P(next|prev) = sum_pt P(pt|prev) P(next|pt)
    tpt = m.groupby(['ptype', 'ttype']).n.sum().unstack(fill_value=0)
    ppt = tpt.div(tpt.sum(1), axis=0)
    prevpt = m.groupby(['prev1', 'ptype']).n.sum().unstack(fill_value=0)
    prevpt = prevpt.div(prevpt.sum(1), axis=0)
    expP = prevpt @ ppt.loc[prevpt.columns]
    print("pooled P(next|prev) observado vs esperado solo por composición ptype (máx |dif| pp): %.3f" % float(((rp - expP.loc[rp.index, rp.columns]).abs().max().max()) * 100))
    print("Adjustment->Adjustment: obs=%.4f  esperado composición=%.4f  marginal=%.4f" % (rp.loc['Adjustment', 'Adjustment'], expP.loc['Adjustment', 'Adjustment'], mg['Adjustment']))
    del m

if sec == 'D2':
    print("== D2. log-loss held-out: P(next|ptype,prev) vs P(next|ptype); split 50/50 por cliente, bootstrap por cliente ==")
    base = """WITH s AS (SELECT t.customer_id, p.ptype, t.ttype, lag(t.ttype) OVER w prev, (hash(t.customer_id) % 2) fold
                        FROM tx t JOIN pr p USING(product_id)
                        WINDOW w AS (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id))"""
    tr = Q(base + " SELECT ptype, prev, ttype, count(*) n FROM s WHERE prev IS NOT NULL AND fold = 0 GROUP BY ALL")
    a = 0.5
    rows = []
    for pt, g in tr.groupby('ptype'):
        sup = list(W[FAM[pt]])
        tb = g.pivot(index='prev', columns='ttype', values='n').reindex(index=sup, columns=sup).fillna(0)
        pm = (tb + a).div(tb.sum(1) + a * len(sup), axis=0)
        pb = (tb.sum(0) + a) / (tb.values.sum() + a * len(sup))
        for pv_ in sup:
            for nx in sup:
                rows.append(dict(ptype=pt, prev=pv_, ttype=nx, gain=np.log2(pm.loc[pv_, nx]) - np.log2(pb[nx])))
    gt = pd.DataFrame(rows)
    con.register('gt', gt)
    pc = Q(base + """ SELECT s.customer_id, count(*) n, sum(g.gain) gain FROM s JOIN gt g ON g.ptype = s.ptype AND g.prev = s.prev AND g.ttype = s.ttype
                     WHERE s.prev IS NOT NULL AND s.fold = 1 GROUP BY 1""")
    N = pc.n.sum(); mean_gain = pc.gain.sum() / N
    rng = np.random.default_rng(11)
    bs = []
    nv, gv = pc.n.values, pc.gain.values
    for _ in range(1000):
        idx = rng.integers(0, len(pc), len(pc))
        bs.append(gv[idx].sum() / nv[idx].sum())
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"clientes test={len(pc)} pares test={N}; ganancia media del modelo Markov-1 vs solo-ptype = {mean_gain*1000:.4f} mbits/tx  IC95 [{lo*1000:.4f}, {hi*1000:.4f}]")
    # entropía de referencia
    print("(referencia: entropía de ttype|ptype ~1.3-1.9 bits por tx; una ganancia de 0.001 bits = 0.05-0.08%)")

# ---------------------------------------------------------------------------------------------
if sec == 'E':
    print("== E. ciclos depósito->retiro en cuentas ==")
    base = """WITH s AS (SELECT t.currency, t.ttype, t.amount, lag(t.ttype) OVER w prev, lag(t.amount) OVER w pamt,
                               epoch(t.ts - lag(t.ts) OVER w) / 86400.0 gap
                        FROM tx t JOIN pr p USING(product_id) WHERE p.ptype LIKE 'Cuenta%'
                        WINDOW w AS (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id))"""
    d = Q(base + """ SELECT CASE WHEN gap < 1.0/24 THEN '1 <1h' WHEN gap < 1 THEN '2 <1d' WHEN gap < 7 THEN '3 <7d' WHEN gap < 30 THEN '4 <30d' ELSE '5 >=30d' END gapbin,
                            (prev = 'Deposit') prev_dep, count(*) n, avg((ttype = 'Withdrawal')::INT) p_wd, avg((ttype = 'Transfer')::INT) p_tr,
                            avg((ttype = 'Deposit')::INT) p_dep
                     FROM s WHERE prev IS NOT NULL GROUP BY ALL ORDER BY 1, 2""")
    piv = d.pivot(index='gapbin', columns='prev_dep', values=['n', 'p_wd', 'p_tr', 'p_dep'])
    piv.columns = [f"{a}_{'trasDep' if b else 'trasOtro'}" for a, b in piv.columns]
    piv['RR_wd'] = piv['p_wd_trasDep'] / piv['p_wd_trasOtro']
    piv['RR_tr'] = piv['p_tr_trasDep'] / piv['p_tr_trasOtro']
    print(piv.round(4).to_string())
    g = Q(base + """ SELECT prev, ttype, count(*) n, approx_quantile(gap, 0.5) med_gap_d, avg(gap) mean_gap_d, avg((gap < 1)::INT) f_lt1d
                     FROM s WHERE prev IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2""")
    print("gap por par prev->next (días):\n", g.round(3).to_string())
    # relación de montos: ¿el retiro 'vacía' el depósito anterior? dentro de moneda
    a = Q(base + """ SELECT currency, prev, count(*) n, corr(ln(amount), ln(pamt)) corr_log,
                            avg((abs(amount / pamt - 1) < 0.02)::INT) f_monto_2pct, avg((amount <= pamt)::INT) f_menor_igual
                     FROM s WHERE prev IS NOT NULL AND ttype = 'Withdrawal' AND amount > 0 AND pamt > 0 GROUP BY 1, 2 ORDER BY 1, 2""")
    print("retiros según tipo de la tx anterior (montos, por moneda):\n", a.round(4).to_string())

# ---------------------------------------------------------------------------------------------
if sec == 'F':
    print("== F. día del mes (nómina/quincena) ==")
    rng_ = Q("SELECT min(ts)::DATE mn, max(ts)::DATE mx FROM tx"); print(rng_)
    cal = Q(f"""SELECT day(x) d, count(*) ndays FROM (SELECT unnest(generate_series(DATE '{rng_.mn[0]}', DATE '{rng_.mx[0]}', INTERVAL 1 DAY)) x) GROUP BY 1 ORDER BY 1""").set_index('d').ndays
    dd = Q("""SELECT day(t.ts) d, count(*) n_cta, sum((t.ttype='Deposit')::INT) n_dep FROM tx t JOIN pr p USING(product_id)
              WHERE p.ptype LIKE 'Cuenta%' GROUP BY 1 ORDER BY 1""").set_index('d')
    dep_pct = dd.n_dep / dd.n_dep.sum() * 100
    exp_pct = cal / cal.sum() * 100
    ratio = dep_pct / exp_pct
    print("%% de depósitos por día (1-30): min=%.3f max=%.3f ; ratio obs/calendario (1-31): min=%.4f max=%.4f" % (
        dep_pct.loc[1:30].min(), dep_pct.loc[1:30].max(), ratio.min(), ratio.max()))
    o = dd.n_dep; e = exp_pct / 100 * o.sum()
    c2 = float(((o - e) ** 2 / e).sum()); print(f"GOF depósitos vs calendario: chi2={c2:.1f} dof=30 p={chi2d.sf(c2, 30):.3g}")
    share = dd.n_dep / dd.n_cta * 100
    s = ctab_stats(np.c_[dd.n_dep.values, (dd.n_cta - dd.n_dep).values])
    print("share de Deposit entre tx de cuentas por día: min=%.3f%% (día %d) max=%.3f%% (día %d); V=%.4f V_nulo=%.4f p=%.3g" % (
        share.min(), share.idxmin(), share.max(), share.idxmax(), s['V'], s['V0'], s['p']))
    print(pd.DataFrame({'dep_pct': dep_pct, 'esperado_cal': exp_pct, 'ratio': ratio, 'share_dep_en_cuentas': share}).loc[[1, 2, 14, 15, 16, 28, 29, 30, 31]].round(3).T.to_string())
    q = Q("""SELECT (day(t.ts) IN (1, 15, 16) OR day(t.ts) >= day(last_day(t.ts)) - 1) quincena, count(*) n, avg((t.ttype='Deposit')::INT) p_dep
             FROM tx t JOIN pr p USING(product_id) WHERE p.ptype LIKE 'Cuenta%' GROUP BY 1 ORDER BY 1""")
    print(q, "\nRR quincena/resto = %.4f" % (q.p_dep[q.quincena].values[0] / q.p_dep[~q.quincena].values[0]))

# ---------------------------------------------------------------------------------------------
if sec == 'G':
    print("== G. nivel cliente (secuencia del cliente cruzando productos) ==")
    d = Q(f"""WITH s AS (SELECT {FAMSQL} fam, t.ttype, t.product_id, t.ts,
                          lag(t.ttype) OVER w prev, lag({FAMSQL}) OVER w pfam, lag(t.product_id) OVER w pprod, lag(t.ts) OVER w pts
                        FROM tx t JOIN pr p USING(product_id)
                        WINDOW w AS (PARTITION BY t.customer_id ORDER BY t.ts, t.transaction_id))
              SELECT pfam, fam, (pprod = product_id) mismo_prod, CASE WHEN epoch(ts - pts) < 86400 THEN '<1d' ELSE '>=1d' END gap,
                     prev, ttype, count(*) n
              FROM s WHERE prev IS NOT NULL GROUP BY ALL""")
    print("pares cliente:", int(d.n.sum()), "; mismo producto: %.4f" % (d[d.mismo_prod].n.sum() / d.n.sum()))
    rows = []
    for key, h in d.groupby(['mismo_prod', 'pfam', 'fam', 'gap']):
        tb = h.pivot_table(index='prev', columns='ttype', values='n', aggfunc='sum').fillna(0).values
        s = ctab_stats(tb)
        if s['dof'] > 0:
            rows.append(dict(mismo_prod=key[0], pfam=key[1], fam=key[2], gap=key[3], n=int(s['n']), V=s['V'], V0=s['V0'], chi2=s['chi2'], dof=s['dof'], p=s['p']))
    r = pd.DataFrame(rows)
    print(r.round(4).to_string())
    print("total estratificado: chi2=%.1f dof=%d p=%.3g; tests=%d, min p=%.3g" % (r.chi2.sum(), r.dof.sum(), chi2d.sf(r.chi2.sum(), r.dof.sum()), len(r), r.p.min()))
    # caso típico de 'ciclo' entre productos: tras un depósito en cuenta, ¿la siguiente tx en tarjeta es más a menudo Withdrawal/Payment?
    h = d[(d.pfam == 'Cuenta') & (d.fam == 'Tarjeta') & (~d.mismo_prod)]
    t = h.pivot_table(index='prev', columns='ttype', values='n', aggfunc='sum').fillna(0)
    print("Cuenta -> Tarjeta (producto distinto): P(next|prev)%\n", (t.div(t.sum(1), axis=0) * 100).round(2).assign(n=t.sum(1).astype(int)).to_string())
    # composición: P(siguiente tx en el mismo ptype) observado
    del d

# ---------------------------------------------------------------------------------------------
if sec == 'F2':
    print("== F2. ¿la desviación del día del mes vs calendario es propia de depósitos o de todo el volumen? ==")
    # esperado ponderando cada fecha del calendario por el volumen del mes (crecimiento/meses parciales)
    dm = Q("""SELECT ts::DATE dt, count(*) n, sum((ttype='Deposit')::INT) n_dep FROM tx GROUP BY 1""")
    dm['dt'] = pd.to_datetime(dm.dt)
    dm['d'] = dm.dt.dt.day; dm['ym'] = dm.dt.dt.to_period('M')
    by_d = dm.groupby('d')[['n', 'n_dep']].sum()
    cal = pd.Series(pd.date_range(dm.dt.min(), dm.dt.max(), freq='D'))
    ec = cal.dt.day.value_counts().sort_index()
    # esperado 2: cada fecha pesa lo que pesa su mes (volumen medio diario del mes) -> controla crecimiento y bordes
    mvol = dm.groupby('ym').n.sum() / cal.groupby(cal.dt.to_period('M')).size()
    w2 = cal.dt.to_period('M').map(mvol)
    e2 = pd.Series(w2.values, index=cal.dt.day.values).groupby(level=0).sum()
    out = pd.DataFrame({'tot_pct': by_d.n / by_d.n.sum() * 100, 'dep_pct': by_d.n_dep / by_d.n_dep.sum() * 100,
                        'cal_pct': ec / ec.sum() * 100, 'cal_vol_pct': e2 / e2.sum() * 100})
    out['r_tot_cal'] = out.tot_pct / out.cal_pct; out['r_tot_calvol'] = out.tot_pct / out.cal_vol_pct; out['r_dep_tot'] = out.dep_pct / out.tot_pct
    print(out.round(3).T.to_string())
    for col, ref in [('n', 'cal_pct'), ('n', 'cal_vol_pct'), ('n_dep', 'cal_pct'), ('n_dep', 'cal_vol_pct')]:
        o = by_d[col]; e = out[ref] / 100 * o.sum(); c2 = float(((o - e) ** 2 / e).sum())
        print(f"GOF {col} vs {ref}: chi2={c2:.1f} dof=30 p={chi2d.sf(c2, 30):.3g}")
    s = ctab_stats(np.c_[by_d.n_dep.values, (by_d.n - by_d.n_dep).values])
    print("share Deposit/total por día del mes: V=%.4f V0=%.4f p=%.3g" % (s['V'], s['V0'], s['p']))
    print("volumen por mes (primeros/últimos):\n", dm.groupby('ym').n.sum().iloc[[0, 1, 2, 17, 18, -3, -2, -1]].to_string())

if sec == 'F3':
    print("== F3. sobredispersión del volumen diario (explica el GOF del día del mes) ==")
    dm = Q("""SELECT ts::DATE dt, dayofweek(ts) dw, count(*) n, sum((ttype='Deposit')::INT) n_dep FROM tx
              WHERE ts >= TIMESTAMP '2023-06-18' AND ts < TIMESTAMP '2026-06-17' GROUP BY 1, 2""")
    print(f"días={len(dm)} media diaria={dm.n.mean():.1f} sd={dm.n.std():.1f} sd_Poisson={np.sqrt(dm.n.mean()):.1f} (índice dispersión={dm.n.var()/dm.n.mean():.2f})")
    print("volumen medio por día de semana (0=dom):", dm.groupby('dw').n.mean().round(1).to_dict())
    r = dm.groupby('dw').n.mean(); print("máx/mín día de semana = %.3f" % (r.max() / r.min()))
    # quitar día de semana y mes: residuo de dispersión
    dm['ym'] = pd.to_datetime(dm.dt).dt.to_period('M')
    fit = dm.groupby('dw').n.transform('mean') * dm.groupby('ym').n.transform('mean') / dm.n.mean()
    print("índice de dispersión tras ajustar dow y mes: %.2f" % (((dm.n - fit) ** 2).sum() / fit.sum()))
    # depósitos: share diario de Deposit vs binomial
    p = dm.n_dep.sum() / dm.n.sum()
    D = ((dm.n_dep - dm.n * p) ** 2).sum() / (dm.n * p * (1 - p)).sum()
    print("dispersión del share diario de Deposit vs binomial: %.3f (≈1 => sin efecto de fecha propio de depósitos)" % D)

if sec == 'B2':
    print("== B2. mezcla dentro de ptype vs calendario fino (dow, hora, día del mes) ==")
    res = []
    for name, expr in {'dow': "dayofweek(t.ts)", 'hora': "hour(t.ts)", 'dia_mes': "day(t.ts)"}.items():
        d = Q(f"SELECT p.ptype, {expr}::VARCHAR lvl, t.ttype, count(*) n FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2,3")
        for pt, g in d.groupby('ptype'):
            s = ctab_stats(g.pivot(index='lvl', columns='ttype', values='n').fillna(0).values)
            res.append(dict(cov=name, ptype=pt, n=int(s['n']), V=round(s['V'], 4), V0=round(s['V0'], 4), p=round(s['p'], 3)))
    r = pd.DataFrame(res); print(r.to_string()); print("p<0.01:", int((r.p < 0.01).sum()), "de", len(r))
