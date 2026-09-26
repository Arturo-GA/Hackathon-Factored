# Verificador escéptico (reintento r2) del hallazgo "comercio_categoria_determinista".
# Intenta refutar: variantes ocultas / nulos disfrazados, tautología tcat=mcat, independencia de nulos
# (también frente a otras variables: canal, país, tiempo, cliente, comercio), valor real de la imputación,
# semántica de la categoría en Payment, utilidad de la categoría y la independencia canal x ttype.
# Todo agregado en SQL; a pandas solo llegan tablas pequeñas.
# Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_comercio_categoria_determinista_skeptic_r2.py [secciones]
#      secciones: A B C D E F G H I J K (por defecto todas)
import sys, time
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency, chisquare

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
SECS = set(sys.argv[1:]) or set('ABCDEFGHIJK')
T0 = time.time()

def df(s):
    return con.execute(s).df()

def show(title, s):
    print('==', title)
    print(df(s).to_string(), '\n', flush=True)

def cramers_v(ct):
    ct = np.asarray(ct, dtype=float)
    ct = ct[ct.sum(1) > 0][:, ct.sum(0) > 0]
    chi2 = chi2_contingency(ct)[0]
    n = ct.sum()
    return float(np.sqrt(chi2 / (n * (min(ct.shape) - 1))))

MAP = """m as (select merchant_name, mode(mcat) mc from tx where merchant_name is not null and mcat is not null group by 1)"""

# ---------------------------------------------------------------- A. valores crudos / nulos disfrazados
if 'A' in SECS:
    show('A1. unicidad de transaction_id', "select count(*) n, count(distinct transaction_id) n_ids from tx")
    show('A2. valores de mcat y tcat (todas las filas), incluyendo cadenas vacías/raras', """
      select 'mcat' col, coalesce(mcat,'<NULL>') v, count(*) n from tx group by 1,2
      union all select 'tcat', coalesce(tcat,'<NULL>'), count(*) from tx group by 1,2 order by 1,3 desc""")
    show('A3. comercios: crudos vs normalizados (lower/trim/sin acentos), y cadenas sospechosas', """
      select count(distinct merchant_name) n_raw,
             count(distinct lower(trim(strip_accents(merchant_name)))) n_norm,
             sum((trim(merchant_name) = '')::int) n_vacios,
             sum((lower(trim(merchant_name)) in ('nan','none','null','n/a','na','-','unknown','desconocido'))::int) n_pseudo_nulos,
             sum((merchant_name <> trim(merchant_name))::int) n_con_espacios
      from tx where merchant_name is not null""")

# ---------------------------------------------------------------- B. mapa comercio -> categoría
if 'B' in SECS:
    show('B1. mapa comercio -> mcat (n categorías, filas, primera/última fecha)', """
      select any_value(mcat) filter (where mcat is not null) mcat_any, merchant_name,
             count(distinct mcat) n_mcat, count(*) n, count(mcat) n_con_mcat,
             min(ts)::date primera, max(ts)::date ultima
      from tx where merchant_name is not null group by merchant_name order by 1, 2""")
    show('B2. comercios por categoría y estabilidad temporal (comercios distintos por semestre)', """
      select date_trunc('quarter', ts)::date trimestre, count(distinct merchant_name) n_comercios,
             count(distinct (merchant_name, mcat)) n_pares, count(*) n
      from tx where merchant_name is not null and mcat is not null group by 1 order by 1""")
    show('B3. ¿existe "Uber" o algún comercio de marca real? (búsqueda por patrón)', """
      select merchant_name, count(*) n from tx
      where merchant_name ilike '%uber%' or merchant_name ilike '%oxxo%' or merchant_name ilike '%netflix%' or merchant_name ilike '%rappi%'
      group by 1""")

# ---------------------------------------------------------------- C. tcat vs mcat vs mapa
if 'C' in SECS:
    show('C1. tcat vs mcat cuando ambas existen (toda la tabla, por ttype)', f"""
      select ttype, count(*) n_tx, sum((tcat is not null and mcat is not null)::int) n_ambas,
             sum((tcat is not null and mcat is not null and tcat<>mcat)::int) n_distintas
      from tx group by 1 order by 2 desc""")
    show('C2. tcat vs mapa(comercio) cuando mcat es nula (valida la imputación de forma independiente)', f"""
      with {MAP}
      select count(*) n_mcat_nula_con_comercio_y_tcat, sum((m.mc = t.tcat)::int) coinciden, sum((m.mc <> t.tcat)::int) difieren
      from tx t join m using(merchant_name) where t.mcat is null and t.tcat is not null""")
    show('C3. mapa entrenado en ts<2025-01-01 y evaluado en ts>=2025-01-01 (mcat observada)', f"""
      with m as (select merchant_name, mode(mcat) mc from tx where ts < timestamp '2025-01-01'
                 and merchant_name is not null and mcat is not null group by 1)
      select count(*) n_eval, sum((m.mc = t.mcat)::int) aciertos, sum((m.mc is null)::int) sin_mapa
      from tx t left join m using(merchant_name)
      where t.ts >= timestamp '2025-01-01' and t.merchant_name is not null and t.mcat is not null""")

# ---------------------------------------------------------------- D. presencia por ttype
if 'D' in SECS:
    show('D1. presencia de merchant/mcat/tcat por ttype', """
      select ttype, count(*) n, count(merchant_name) n_merch, count(mcat) n_mcat, count(tcat) n_tcat,
             round(100*count(merchant_name)/count(*),3) pct_merch, round(100*count(mcat)/count(*),3) pct_mcat,
             round(100*count(tcat)/count(*),3) pct_tcat
      from tx group by 1 order by 2 desc""")

# ---------------------------------------------------------------- E. independencia de nulos
if 'E' in SECS:
    j = df("""select (merchant_name is null)::int a, (mcat is null)::int b, (tcat is null)::int c, count(*) n
              from tx where ttype='Purchase' group by 1,2,3""")
    N = j.n.sum(); pa = j.loc[j.a == 1, 'n'].sum() / N; pb = j.loc[j.b == 1, 'n'].sum() / N; pc = j.loc[j.c == 1, 'n'].sum() / N
    j['esperado'] = N * np.where(j.a == 1, pa, 1 - pa) * np.where(j.b == 1, pb, 1 - pb) * np.where(j.c == 1, pc, 1 - pc)
    j['obs_esp'] = (j.n / j.esperado).round(3)
    print('== E1. patrón conjunto de nulos en Purchase (a=comercio, b=mcat, c=tcat; 1=nulo)')
    print(j.sort_values(['a', 'b', 'c']).to_string()); print('N=%d pa=%.5f pb=%.5f pc=%.5f\n' % (N, pa, pb, pc))
    for x, y in [('a', 'b'), ('a', 'c'), ('b', 'c')]:
        t = j.groupby([x, y]).n.sum().unstack().values.astype(float)
        o = t[1, 1] * t[0, 0] / (t[1, 0] * t[0, 1]); se = np.sqrt((1 / t).sum())
        print('   OR nulos %s~%s = %.3f IC95 [%.3f, %.3f]' % (x, y, o, np.exp(np.log(o) - 1.96 * se), np.exp(np.log(o) + 1.96 * se)))
    print()
    # nulos vs otras variables (en Purchase): tasa de nulo de mcat por grupo, razón máx/mín
    for col, expr in [('channel', 'channel'), ('country', 'country'), ('currency', 'currency'), ('status', 'status'),
                      ('anio_trim', "strftime(ts, '%Y-Q') || quarter(ts)::varchar"), ('dow', 'dayofweek(ts)'),
                      ('amount_usd_nulo', '(amount_usd is null)::int'), ('fscore_nulo', '(fscore is null)::int'),
                      ('lat_nulo', '(lat is null)::int'), ('city_nula', '(city is null)::int')]:
        g = df(f"""select {expr} g, count(*) n, avg((mcat is null)::int) p_mcat, avg((merchant_name is null)::int) p_merch,
                   avg((tcat is null)::int) p_tcat from tx where ttype='Purchase' group by 1""")
        g = g[g.n >= 5000]
        print('   E2 %-16s grupos=%2d  p_mcat nulo [%.4f, %.4f] ratio=%.3f | p_merch [%.4f, %.4f] ratio=%.3f | p_tcat [%.4f, %.4f] ratio=%.3f' % (
            col, len(g), g.p_mcat.min(), g.p_mcat.max(), g.p_mcat.max() / g.p_mcat.min(),
            g.p_merch.min(), g.p_merch.max(), g.p_merch.max() / g.p_merch.min(),
            g.p_tcat.min(), g.p_tcat.max(), g.p_tcat.max() / g.p_tcat.min()), flush=True)
    print()
    # nulo de mcat por comercio y nulo de comercio/tcat por categoría imputada (¿sesgo de categoría en los nulos?)
    show('E3. tasa de mcat nula por comercio (rango) y de comercio/tcat nulo por categoría imputada', f"""
      with {MAP}, t as (select t.*, coalesce(t.mcat, m.mc, t.tcat) cat from tx t left join m using(merchant_name) where t.ttype='Purchase')
      select 'mcat_nula_por_comercio' medida, min(p) p_min, max(p) p_max, max(p)/min(p) ratio, count(*) k from
        (select merchant_name, avg((mcat is null)::int) p from t where merchant_name is not null group by 1)
      union all
      select 'comercio_nulo_por_categoria', min(p), max(p), max(p)/min(p), count(*) from
        (select cat, avg((merchant_name is null)::int) p from t where cat is not null group by 1)
      union all
      select 'tcat_nula_por_categoria', min(p), max(p), max(p)/min(p), count(*) from
        (select cat, avg((tcat is null)::int) p from t where cat is not null group by 1)""")
    # agrupamiento por cliente: varianza de la tasa de nulos por cliente vs binomial
    show('E4. ¿los nulos se agrupan por cliente? var observada / var binomial esperada (clientes con >=20 compras)', """
      with c as (select customer_id, count(*) n, avg((mcat is null)::int) r_mcat, avg((merchant_name is null)::int) r_merch,
                 avg((tcat is null)::int) r_tcat from tx where ttype='Purchase' group by 1 having count(*) >= 20)
      select count(*) n_clientes, avg(n) compras_media,
             var_samp(r_mcat) / avg(avg_p_m*(1-avg_p_m)/n) ratio_var_mcat,
             var_samp(r_merch) / avg(avg_p_n*(1-avg_p_n)/n) ratio_var_merch,
             var_samp(r_tcat) / avg(avg_p_t*(1-avg_p_t)/n) ratio_var_tcat
      from c, (select avg((mcat is null)::int) avg_p_m, avg((merchant_name is null)::int) avg_p_n, avg((tcat is null)::int) avg_p_t
               from tx where ttype='Purchase') p""")

# ---------------------------------------------------------------- F. imputación
if 'F' in SECS:
    show('F1. imputación paso a paso (Purchase y Payment), en % de filas', f"""
      with {MAP}
      select t.ttype, count(*) n,
        round(100*avg((t.mcat is null)::int),4) pct_mcat_nula,
        round(100*avg((coalesce(t.mcat,t.tcat) is null)::int),4) pct_tras_tcat,
        round(100*avg((coalesce(t.mcat,m.mc) is null)::int),4) pct_tras_mapa,
        round(100*avg((coalesce(t.mcat,m.mc,t.tcat) is null)::int),4) pct_tras_ambos,
        sum((coalesce(t.mcat,t.tcat) is null)::int) n_nula_tras_tcat,
        sum((coalesce(t.mcat,m.mc,t.tcat) is null)::int) n_nula_final,
        round(100*avg((t.merchant_name is null)::int),4) pct_sin_comercio,
        round(100*avg((t.merchant_name is not null and coalesce(t.mcat,m.mc,t.tcat) is not null)::int),4) pct_comercio_y_cat
      from tx t left join m using(merchant_name) where t.ttype in ('Purchase','Payment') group by 1""")

# ---------------------------------------------------------------- G. pesos y uniformidad; tcat en Payment
if 'G' in SECS:
    show('G1. peso por categoría (compras, mcat observada) y comercios por categoría', """
      select mcat, count(distinct merchant_name) n_comercios, count(*) n, round(100*count(*)/sum(count(*)) over (),2) pct
      from tx where ttype='Purchase' and mcat is not null group by 1 order by n desc""")
    w = df("select mcat, merchant_name, count(*) n from tx where merchant_name is not null and mcat is not null group by 1,2")
    print('== G2. uniformidad de comercios dentro de cada categoría')
    for c, g in w.groupby('mcat'):
        s = chisquare(g.n.values)
        print('   %-14s k=%d n=%7d  max/min=%.4f  chi2 p=%.3g  comercios=%s' % (c, len(g), g.n.sum(), g.n.max() / g.n.min(), s.pvalue,
              ', '.join(g.sort_values('n', ascending=False).merchant_name.tolist())))
    print()
    d = df("""select ttype, tcat, count(*) n from tx where ttype in ('Purchase','Payment') and tcat is not null group by 1,2""")
    ct = d.pivot(index='tcat', columns='ttype', values='n').fillna(0)
    print('== G3. tcat en Purchase vs Payment (proporciones)'); print((ct / ct.sum()).round(4).to_string())
    print('   V tcat x {Purchase,Payment} = %.4f (n=%d)\n' % (cramers_v(ct.values), ct.values.sum()))
    d = df("""select p.ptype, t.tcat, count(*) n from tx t join pr p using(product_id)
              where t.ttype='Payment' and t.tcat is not null group by 1,2""")
    ct = d.pivot(index='ptype', columns='tcat', values='n').fillna(0)
    print('== G4. tcat de Payment por tipo de producto (proporciones por fila)'); print(ct.div(ct.sum(1), axis=0).round(3).assign(n=ct.sum(1).astype(int)).to_string())
    print('   V ptype x tcat (Payment) = %.4f\n' % cramers_v(ct.values))
    d = df("""select p.ptype, t.mcat, count(*) n from tx t join pr p using(product_id)
              where t.ttype='Purchase' and t.mcat is not null group by 1,2""")
    ct = d.pivot(index='ptype', columns='mcat', values='n').fillna(0)
    print('== G5. mcat de Purchase por tipo de producto'); print(ct.div(ct.sum(1), axis=0).round(3).assign(n=ct.sum(1).astype(int)).to_string())
    print('   V ptype x mcat (Purchase) = %.4f\n' % cramers_v(ct.values))

# ---------------------------------------------------------------- H. ¿la categoría/comercio aporta algo más que la etiqueta?
if 'H' in SECS:
    show('H1. por categoría imputada (compras): fraude, rechazo, monto por moneda', f"""
      with {MAP}, t as (select t.*, coalesce(t.mcat, m.mc, t.tcat) cat from tx t left join m using(merchant_name) where t.ttype='Purchase')
      select cat, count(*) n, round(100*avg(fraud::int),4) pct_fraude, round(100*avg((status='Declined')::int),3) pct_rech,
             round(100*avg((fscore>=50)::int),3) pct_fscore50,
             round(median(amount) filter (where currency='USD'),1) med_usd, round(median(amount) filter (where currency='COP'),0) med_cop,
             round(median(amount) filter (where currency='ARS'),0) med_ars,
             round(quantile_cont(amount, 0.9) filter (where currency='USD'),1) p90_usd
      from t group by 1 order by n desc""")
    for col in ['channel', 'country', 'status', 'currency']:
        d = df(f"""with {MAP} select coalesce(t.mcat, m.mc, t.tcat) cat, t.{col} g, count(*) n from tx t left join m using(merchant_name)
                  where t.ttype='Purchase' and coalesce(t.mcat, m.mc, t.tcat) is not null and t.{col} is not null group by 1,2""")
        ct = d.pivot(index='cat', columns='g', values='n').fillna(0)
        print('   H2 V categoría x %-8s = %.4f (n=%d)' % (col, cramers_v(ct.values), ct.values.sum()))
    d = df("""select merchant_name, country, count(*) n from tx where merchant_name is not null and country is not null group by 1,2""")
    ct = d.pivot(index='merchant_name', columns='country', values='n').fillna(0)
    print('   H3 V comercio x país = %.4f; países por comercio: min=%d max=%d; países=%s' % (
        cramers_v(ct.values), (ct > 0).sum(1).min(), (ct > 0).sum(1).max(), list(ct.columns)))
    show('H4. ciudades distintas por comercio y ciudades/países mezclados (¿comercio local?)', """
      select min(nc) min_ciudades, max(nc) max_ciudades, min(np_) min_paises, max(np_) max_paises from
       (select merchant_name, count(distinct city) nc, count(distinct country) np_ from tx where merchant_name is not null group by 1)""")

# ---------------------------------------------------------------- I. canal x ttype
if 'I' in SECS:
    g = df("select ttype, coalesce(channel,'(nulo)') channel, count(*) n from tx group by 1,2")
    ct = g.pivot(index='ttype', columns='channel', values='n').fillna(0).astype(int)
    print('== I1. conteos ttype x canal'); print(ct.to_string(), '\n')
    sh = ct.div(ct.sum(1), axis=0); tot = ct.sum(0) / ct.values.sum()
    print('== I2. proporción de canal dentro de cada ttype'); print(sh.round(4).to_string())
    print('   máx |prop(ttype) - prop global| = %.4f ; V ttype x canal = %.4f (N=%d)' % (
        float(np.abs(sh - tot).values.max()), cramers_v(ct.values), ct.values.sum()))
    for tt, ch, claimed in [('Withdrawal', 'Web', 144757), ('Withdrawal', 'App', 144402), ('Withdrawal', 'POS', 337693),
                            ('Deposit', 'POS', 213678), ('Purchase', 'ATM', 325993)]:
        print('   %s por %s: %d (hallazgo %d)  %.2f%% del tipo' % (tt, ch, ct.loc[tt, ch], claimed, 100 * sh.loc[tt, ch]))
    print()
    show('I3. coherencia interna del canal: branch_id / merchant / lat por canal (todas las tx)', """
      select channel, count(*) n, round(100*avg((branch_id is not null)::int),2) pct_branch, round(100*avg((lat is not null)::int),2) pct_lat,
             round(100*avg((merchant_name is not null)::int),2) pct_merch, round(100*avg((status='Declined')::int),2) pct_rech,
             round(100*avg(fraud::int),3) pct_fraude
      from tx group by 1 order by 2 desc""")
    d = df("""select merchant_name, channel, count(*) n from tx where merchant_name is not null and channel is not null group by 1,2""")
    ct = d.pivot(index='merchant_name', columns='channel', values='n').fillna(0)
    print('   I4 V comercio x canal = %.4f; compras en ATM por comercio: %.2f%%-%.2f%%' % (
        cramers_v(ct.values), 100 * (ct['ATM'] / ct.sum(1)).min(), 100 * (ct['ATM'] / ct.sum(1)).max()))
    print()

# ---------------------------------------------------------------- J. otros tipos: ¿Payment tiene alguna pista de destino?
if 'J' in SECS:
    show('J1. Payment: presencia de branch/lat/city y canal (¿hay algo que describa el pago?)', """
      select count(*) n, round(100*avg((tcat is not null)::int),2) pct_tcat, round(100*avg((branch_id is not null)::int),2) pct_branch,
             round(100*avg((city is not null)::int),2) pct_city, count(distinct tcat) n_tcat
      from tx where ttype='Payment'""")

# ---------------------------------------------------------------- K. ¿categoría/comercio predicen fraude o rechazo? AUC held-out por cliente
def auc_from_counts(score, pos, neg):
    # AUC de un score discreto a partir de conteos por nivel: P(s+ > s-) + 0.5 P(empate)
    o = np.argsort(score); s = np.asarray(score)[o]; p = np.asarray(pos, float)[o]; n = np.asarray(neg, float)[o]
    auc = 0.0; cum_neg = 0.0
    for i in range(len(s)):
        auc += p[i] * (cum_neg + 0.5 * n[i]); cum_neg += n[i]
    return auc / (p.sum() * n.sum())

if 'K' in SECS:
    rng = np.random.default_rng(7)
    for feat, target in [('cat', 'fraud'), ('merchant_name', 'fraud'), ('cat', "(status='Declined')"), ('merchant_name', "(status='Declined')")]:
        d = df(f"""with {MAP}, t as (select coalesce(t.mcat, m.mc, t.tcat) cat, t.merchant_name, t.fraud, t.status,
                     (hash(t.customer_id) % 2 = 0) tr from tx t left join m using(merchant_name) where t.ttype='Purchase')
                  select {feat} lvl, tr, sum(({target})::int) pos, sum((not ({target}))::int) neg from t where {feat} is not null group by 1,2""")
        trn = d[d.tr].set_index('lvl'); tst = d[~d.tr].set_index('lvl')
        rate = (trn.pos + 1) / (trn.pos + trn.neg + 2)  # tasa suavizada aprendida en clientes de entrenamiento
        tst = tst.join(rate.rename('score'), how='inner')
        auc = auc_from_counts(tst.score.values, tst.pos.values, tst.neg.values)
        boots = []
        for _ in range(500):  # bootstrap multinomial por clase (fraude es 0.1%: el agrupamiento por cliente es despreciable)
            bp = rng.multinomial(int(tst.pos.sum()), tst.pos / tst.pos.sum()); bn = rng.multinomial(int(tst.neg.sum()), tst.neg / tst.neg.sum())
            boots.append(auc_from_counts(tst.score.values, bp, bn))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        full = d.groupby('lvl')[['pos', 'neg']].sum(); r = full.pos / (full.pos + full.neg)
        chi_p = chi2_contingency(full[['pos', 'neg']].values)[1]
        print('   K %-14s -> %-20s AUC test=%.4f IC95 [%.4f, %.4f] | tasa por nivel [%.4f%%, %.4f%%] max/min=%.2f | chi2 p=%.3g | n_pos=%d' % (
            feat, target, auc, lo, hi, 100 * r.min(), 100 * r.max(), r.max() / r.min(), chi_p, int(full.pos.sum())), flush=True)
    print()

print('tiempo total %.1f s' % (time.time() - T0))
