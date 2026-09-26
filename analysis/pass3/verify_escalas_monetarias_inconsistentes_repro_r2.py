# Verificacion independiente (ronda 2) del hallazgo "escalas_monetarias_inconsistentes".
# Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_escalas_monetarias_inconsistentes_repro_r2.py A B C D E
#   A = escala del ingreso (factor K exacto, rangos por segmento, regla segmento<->ingreso)
#   B = moneda de productos / tx por pais del cliente y escala de montos tx
#   C = cociente gasto mensual / ingreso (crudo, mixto y normalizado)
#   D = cp.claimed (escala, uniformidad, case_type, moneda vs pais, enlaces con tx + linea base por azar)
#   E = de.event_value (escala, uniformidad, enlaces con tx en base completa + controles, correlacion actividad)
import sys, duckdb, numpy as np, pandas as pd
from scipy import stats
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 80)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(s, title=None):
    if title: print('==', title)
    df = con.execute(s).df(); print(df.to_string(index=False), '\n'); return df
SECS = set(sys.argv[1:]) or set('ABCDE')
KC = "(case {c} when 'Argentina' then 350.0 when 'Colombia' then 4000.0 when 'México' then 17.0 end)"      # por pais
KM = "(case {c} when 'ARS' then 350.0 when 'COP' then 4000.0 when 'MXN' then 17.0 when 'USD' then 1.0 end)"  # por moneda

# ---------------------------------------------------------------- A. ingreso
if 'A' in SECS:
    cu = con.execute("select customer_id, country, segment, income from cu").df()
    print('A0 filas cu', len(cu), '| income nulo:', cu.income.isna().sum(), '| income<=0:', (cu.income <= 0).sum())
    # decimales: ingreso crudo y ingreso/K
    K = cu.country.map({'Argentina': 350.0, 'Colombia': 4000.0, 'México': 17.0})
    cu['norm'] = cu.income / K
    def frac_dec(x, d):  # fraccion de valores con <= d decimales
        x = x.dropna(); return np.mean(np.abs(x * 10**d - np.round(x * 10**d)) < 1e-6)
    for c in ['México', 'Argentina', 'Colombia']:
        s = cu[cu.country == c]
        print(f'A0 {c}: crudo con <=2 dec {frac_dec(s.income,2):.4f}, entero {frac_dec(s.income,0):.4f} | norm con <=2 dec {frac_dec(s.norm,2):.4f}')
    # A1: cocientes AR/MX y CO/MX por segmento en min/p10/mediana/p90/max (sin suponer K)
    g = cu.groupby(['segment', 'country']).income.describe(percentiles=[.1, .5, .9])[['count', 'min', '10%', '50%', '90%', 'max']]
    print('A1 ingreso crudo por segmento x pais\n', g.round(1).to_string(), '\n')
    rows = []
    for seg in sorted(cu.segment.unique()):
        mx = g.loc[(seg, 'México')]
        for c in ['Argentina', 'Colombia']:
            o = g.loc[(seg, c)]
            rows.append([seg, c + '/MX'] + [o[k] / mx[k] for k in ['min', '10%', '50%', '90%', 'max']])
    print('A1 cocientes (esperado AR/MX=350/17=20.588, CO/MX=4000/17=235.294)\n',
          pd.DataFrame(rows, columns=['segment', 'par', 'min', 'p10', 'med', 'p90', 'max']).round(3).to_string(index=False), '\n')
    # A2: ingreso normalizado por segmento x pais
    gn = cu.groupby(['segment', 'country']).norm.describe(percentiles=[.5])[['count', 'min', '50%', 'max']]
    print('A2 ingreso/K por segmento x pais\n', gn.round(2).to_string(), '\n')
    # A3: horquilla de K exacto suponiendo cotas redondas del segmento: max/ub <= K <= min/lb
    B = {'Basic': (800, 2800), 'Plus': (3000, 10500), 'Premium': (8000, 28000), 'Student': (300, 1050)}
    for c in ['México', 'Argentina', 'Colombia']:
        lo, hi = -np.inf, np.inf
        for seg, (lb, ub) in B.items():
            s = cu[(cu.country == c) & (cu.segment == seg)].income
            lo = max(lo, s.max() / ub); hi = min(hi, s.min() / lb)
        print(f'A3 {c}: K en [{lo:.4f}, {hi:.4f}]')
    # A4: KS de ingreso normalizado entre paises, por segmento (misma distribucion?)
    for seg in B:
        a, b, d = [cu[(cu.segment == seg) & (cu.country == c)].norm.dropna() for c in ['México', 'Argentina', 'Colombia']]
        print(f'A4 {seg}: KS MX-AR D={stats.ks_2samp(a, b).statistic:.4f} p={stats.ks_2samp(a, b).pvalue:.3f} | MX-CO D={stats.ks_2samp(a, d).statistic:.4f} p={stats.ks_2samp(a, d).pvalue:.3f}'
              f' | KS vs U({B[seg][0]},{B[seg][1]}) todos: D={stats.kstest(cu[cu.segment == seg].norm.dropna(), "uniform", args=(B[seg][0], B[seg][1]-B[seg][0])).statistic:.4f}')
    # A5: consistencia de la regla segmento <-> rango de ingreso normalizado; solapamientos
    nn = cu[cu.norm.notna()].copy()
    inr = nn.apply(lambda r: B[r.segment][0] <= r.norm <= B[r.segment][1], axis=1)
    print('A5 ingreso nulo por pais:', cu[cu.income.isna()].country.value_counts().to_dict(), '| por segmento:', cu[cu.income.isna()].segment.value_counts().to_dict())
    print('A5 (no nulos, n=%d) fraccion dentro del rango de su segmento:' % len(nn), round(inr.mean(), 6), '| fuera:', int((~inr).sum()))
    n_amb = sum(((nn.norm >= lb) & (nn.norm <= ub)) for lb, ub in B.values())
    print('A5 no nulos cuyo ingreso normalizado cae en >1 rango de segmento (ambiguos):', int((n_amb > 1).sum()), f'({(n_amb > 1).mean():.3%})')
    print('A5 segmento inferido por rango unico: acierto en no ambiguos =',
          round(np.mean([[s for s, (lb, ub) in B.items() if lb <= v <= ub][0] == seg for v, seg, k in zip(nn.norm, nn.segment, n_amb) if k == 1]), 6))
    # A6: tipo de cambio de referencia
    q("""select src, dst, count(*) n, min(rate) mn, median(rate) med, max(rate) mx from fx where src='USD' and dst in ('MXN','ARS','COP') group by all order by dst""", 'A6 fx USD->local')

# ---------------------------------------------------------------- B. monedas de pr/tx
if 'B' in SECS:
    q("""select cu.country, p.currency, count(*) n, round(count(*)/sum(count(*)) over (partition by cu.country),4) pct
         from pr p join cu using(customer_id) group by 1,2 order by 1,2""", 'B1 moneda de productos por pais del cliente')
    q("""select cu.country, t.currency, count(*) n, round(count(*)/sum(count(*)) over (partition by cu.country),4) pct
         from tx t join cu using(customer_id) group by 1,2 order by 1,2""", 'B2 moneda de tx por pais del cliente')
    q(f"""select ttype, currency, count(*) n, round(median(amount),1) med_raw, round(median(amount/{KM.format(c='currency')}),2) med_usd_eq,
              round(min(amount/{KM.format(c='currency')}),2) min_usd_eq, round(max(amount/{KM.format(c='currency')}),2) max_usd_eq
          from tx where ttype in ('Purchase','Withdrawal','Transfer') group by all order by 1,2""", 'B3 escala de montos tx por moneda (USD-eq = amount/K)')

# ---------------------------------------------------------------- C. gasto / ingreso
if 'C' in SECS:
    kc = KC.format(c='cu.country'); km = KM.format(c='currency')
    _c1 = q(f"""with t as (select customer_id, sum(amount)/36.0 m_raw, sum(amount/{km})/36.0 m_usd,
                      sum(amount) filter (where status='Approved')/36.0 m_raw_ok, sum(amount/{km}) filter (where status='Approved')/36.0 m_usd_ok
               from tx where ttype in ('Purchase','Withdrawal') group by 1)
          select cu.country, count(*) n,
             median(t.m_raw/cu.income)          r_crudo_vs_crudo,
             median(t.m_usd/cu.income)          r_usd_vs_crudo,
             median(t.m_usd/(cu.income/{kc}))   r_normalizado,
             median(t.m_raw_ok/cu.income)       r_crudo_vs_crudo_aprob,
             median(t.m_usd_ok/(cu.income/{kc})) r_normalizado_aprob
          from t join cu using(customer_id) where cu.income>0 group by 1 order by 1""", 'C1 mediana por cliente de gasto mensual (Purchase+Withdrawal)/ingreso')
    d = _c1.set_index('country')
    for col in ['r_crudo_vs_crudo', 'r_usd_vs_crudo', 'r_normalizado']:
        mx = d.loc['México', col]
        print(f'C2 {col}: MX/AR = {mx / d.loc["Argentina", col]:.3f}  MX/CO = {mx / d.loc["Colombia", col]:.3f}  (valores: ' +
              ', '.join(f'{c} {d.loc[c, col]:.3e}' for c in d.index) + ')')

# ---------------------------------------------------------------- D. cp.claimed
if 'D' in SECS:
    q("""select coalesce(currency,'(nulo)') currency, count(*) n, count(claimed) n_claimed, round(min(claimed),2) mn, round(quantile_cont(claimed,.25),1) p25,
            round(median(claimed),1) med, round(quantile_cont(claimed,.75),1) p75, round(max(claimed),2) mx from cp group by 1 order by 1""", 'D1 claimed por moneda')
    q("""select case_type, count(*) n, count(claimed) n_claimed, round(avg((claimed is not null)::int),4) pct from cp group by 1 order by 2 desc""", 'D2 claimed por case_type')
    cl = con.execute("select claimed, coalesce(currency,'(nulo)') currency from cp where claimed is not null").df()
    h, _ = np.histogram(cl.claimed, bins=10, range=(50, 5000))
    print('D3 histograma 10 tramos 50-5000:', h.tolist(), '| chi2 p =', round(stats.chisquare(h).pvalue, 3),
          '| KS vs U(50,5000) D =', round(stats.kstest(cl.claimed, 'uniform', args=(50, 4950)).statistic, 4))
    grp = [g.claimed.values for _, g in cl.groupby('currency')]
    print('D3 Kruskal-Wallis entre monedas p =', round(stats.kruskal(*grp).pvalue, 3),
          '| medianas:', cl.groupby('currency').claimed.median().round(0).to_dict())
    ct = q("""select cu.country, coalesce(cp.currency,'(nulo)') cur, count(*) n from cp join cu using(customer_id) group by all order by 1,2""", 'D4 moneda del reclamo vs pais del cliente')
    tab = ct.pivot(index='country', columns='cur', values='n').fillna(0).values
    chi2 = stats.chi2_contingency(tab)[0]; V = np.sqrt(chi2 / (tab.sum() * (min(tab.shape) - 1)))
    print('D4 V de Cramer pais cliente x moneda reclamo =', round(V, 4))
    q("""select (select count(*) from pr where currency='MXN') pr_mxn, (select count(*) from tx where currency='MXN') tx_mxn,
                (select count(*) from cp where currency='MXN') cp_mxn, (select count(*) from cp where currency='MXN' and claimed is not null) cp_mxn_claimed,
                (select count(*) from cp where currency is null and claimed is not null) cp_sin_moneda_con_claimed""", 'D5 MXN')
    # D6: enlaces con tx del mismo cliente
    con.execute("create temp table c as select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null")
    km = KM.format(c='t.currency'); kcl = KM.format(c='c.currency')
    con.execute(f"""create temp table t as select t.customer_id, t.ts, t.amount, t.currency, t.amount_usd, t.amount/{km} usd_k
                    from tx t where t.customer_id in (select customer_id from c)""")
    print('D6 reclamos con claimed:', con.execute('select count(*), count(distinct customer_id) from c').fetchone(),
          '| tx de esos clientes:', con.execute('select count(*) from t').fetchone()[0])
    def nmatch(cond, src='c'):
        return con.execute(f"select count(distinct c.complaint_id) from {src} c join t on t.customer_id=c.customer_id and {cond}").fetchone()[0]
    print('D6 exacto al centavo, monto original, cualquier fecha :', nmatch("abs(t.amount-c.claimed)<0.005"))
    print('D6 exacto al centavo, amount/K (USD-eq)              :', nmatch("abs(t.usd_k-c.claimed)<0.005"))
    print('D6 exacto al centavo, amount_usd                     :', nmatch("abs(t.amount_usd-c.claimed)<0.005"))
    print('D6 exacto, claimed*K(moneda reclamo) vs monto orig.  :', nmatch(f"abs(t.amount-c.claimed*coalesce({kcl},1.0))<0.005"))
    w90 = "t.ts between c.ts - interval 90 day and c.ts"
    print('D6 +-1% monto orig., 90d previos                     :', nmatch(f"abs(t.amount/c.claimed-1)<0.01 and {w90}"))
    print('D6 +-1% USD-eq vs claimed/K(moneda reclamo), 90d     :', nmatch(f"abs(t.usd_k/(c.claimed/coalesce({kcl},1.0))-1)<0.01 and {w90}"))
    # linea base: permutar clientes entre reclamos (mismo monto y fecha, otro cliente reclamante)
    con.execute("""create temp table cperm as with a as (select complaint_id, claimed, currency, ts, row_number() over (order by hash(complaint_id||'x')) r from c),
                   b as (select customer_id, row_number() over (order by hash(customer_id||complaint_id||'y')) r from c)
                   select a.complaint_id, a.claimed, a.currency, a.ts, b.customer_id from a join b using(r)""")
    print('D6 BASE permutada +-1% monto orig., 90d              :', nmatch(f"abs(t.amount/c.claimed-1)<0.01 and {w90}", 'cperm'))
    print('D6 BASE permutada +-1% USD-eq, 90d                   :', nmatch(f"abs(t.usd_k/(c.claimed/coalesce({kcl},1.0))-1)<0.01 and {w90}", 'cperm'))
    # D7: coincidencia exacta con cualquier tx USD de cualquier cliente vs esperado por cobertura de centavos
    r = con.execute("""with u as (select distinct round(amount*100)::bigint cents from tx where currency='USD' and amount between 50 and 5000)
                       select (select count(*) from u) n_cents_distintos,
                              (select count(*) from c where round(claimed*100)::bigint in (select cents from u)) n_match""").fetchone()
    cover = r[0] / (495000 + 1)
    print(f'D7 centavos distintos con tx USD en [50,5000]: {r[0]:,} de 495,001 (cobertura {cover:.4f}) | reclamos que coinciden: {r[1]:,} '
          f'| esperado por azar: {21751*cover:,.0f}')

# ---------------------------------------------------------------- E. de.event_value
if 'E' in SECS:
    q("""select event_type, count(*) n, count(event_value) n_val, count(event_value) filter (where customer_id is not null) n_val_cli,
            round(min(event_value),2) mn, round(median(event_value),1) med, round(max(event_value),2) mx
         from de group by 1 order by 2 desc""", 'E1 event_value por event_type')
    q("""select cu.country, count(*) n, round(min(d.event_value),2) mn, round(quantile_cont(d.event_value,.25),1) p25, round(median(d.event_value),1) med,
            round(quantile_cont(d.event_value,.75),1) p75, round(max(d.event_value),2) mx
         from de d join cu using(customer_id) where d.event_value is not null group by 1 order by 1""", 'E2 event_value por pais del cliente (sin escala?)')
    hist = q("""select least(floor((event_value-10)/499),9)::int bin, count(*) n from de where event_value is not null group by 1 order by 1""", 'E3 histograma 10 tramos 10-5000')
    print('E3 chi2 uniformidad p =', round(stats.chisquare(hist.n.values).pvalue, 3))
    # E4: enlace con tx del mismo cliente, +-1 dia, +-1%, base completa, con controles
    con.execute("create temp table e as select event_id, customer_id, event_type, event_value v, ts from de where event_value is not null and customer_id is not null")
    ne = con.execute("select count(*), count(distinct customer_id) from e").fetchone(); print('E4 eventos con valor y cliente:', ne)
    km = KM.format(c='t.currency')
    def ematch(src='e', shift=0, usd=True):
        amt = f"t.amount/{km}" if usd else "t.amount"
        return con.execute(f"""select count(distinct e.event_id) from {src} e join tx t on t.customer_id=e.customer_id
                               and abs(epoch(t.ts)-epoch(e.ts + interval ({shift}) day))<86400 and abs({amt}/e.v-1)<0.01""").fetchone()[0]
    print('E4 +-1d +-1% monto orig.        :', ematch(usd=False))
    print('E4 +-1d +-1% USD-eq             :', ematch())
    for s in (-365, 365):
        print(f'E4 CONTROL desplazado {s:+d}d USD-eq:', ematch(shift=s))
    con.execute("""create temp table eperm as with a as (select event_id, event_type, v, ts, row_number() over (order by hash(event_id||'x')) r from e),
                   b as (select customer_id, row_number() over (order by hash(event_id||customer_id||'y')) r from e)
                   select a.event_id, a.event_type, a.v, a.ts, b.customer_id from a join b using(r)""")
    print('E4 CONTROL clientes permutados USD-eq:', ematch('eperm'))
    # por tipo de evento (Purchase deberia enlazar mas si hubiera vinculo)
    q(f"""select e.event_type, count(distinct e.event_id) n_match from e join tx t on t.customer_id=e.customer_id
          and abs(epoch(t.ts)-epoch(e.ts))<86400 and abs(t.amount/{km}/e.v-1)<0.01 group by 1""", 'E4 coincidencias USD-eq por tipo de evento')
    # E5: correlacion actividad digital vs numero de tx por cliente
    q("""with d as (select customer_id, count(*) nde, count(*) filter (where event_type='Purchase') npur from de where customer_id is not null group by 1),
              x as (select customer_id, count(*) ntx, count(*) filter (where channel in ('App','Web')) ndig from tx group by 1),
              j as (select d.*, x.ntx, x.ndig from d join x using(customer_id)),
              r as (select *, rank() over (order by nde) rd, rank() over (order by ntx) rx from j)
         select count(*) n, round(corr(nde, ntx),4) pearson_all, round(corr(rd, rx),4) spearman_all, round(corr(npur, ndig),4) pearson_purchase_vs_txdigital from r""",
      'E5 actividad digital vs n tx por cliente')
