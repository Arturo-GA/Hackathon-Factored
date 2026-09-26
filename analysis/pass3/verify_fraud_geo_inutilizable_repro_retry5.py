"""Verificación independiente (reintento) de 'fraud_geo_inutilizable'.
Parte 5: diagnóstico del artefacto débil en fraude (|dlon| concentrado, dprev menor, dnext no).
¿Forma de la distribución? ¿correlación con la tx previa/siguiente? ¿lo explica el hueco temporal?
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_fraud_geo_inutilizable_repro_retry5.py
"""
import duckdb, pandas as pd, numpy as np
from scipy import stats
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
con.execute("""create temp table anc as
select cu.country cc, (min(t.lat)+max(t.lat))/2 alat, (min(t.lon)+max(t.lon))/2 alon
from tx t join cu using(customer_id) where t.lat is not null group by 1""")
d = con.execute("""
with base as (
  select t.customer_id, t.transaction_id, t.ts, t.fraud, t.fscore, t.channel, cu.country cc, t.lat-a.alat dlat, t.lon-a.alon dlon
  from tx t join cu using(customer_id) join anc a on a.cc=cu.country where t.lat is not null and t.lon is not null),
w as (select *, lag(dlat) over v pdlat, lag(dlon) over v pdlon, lead(dlat) over v ndlat, lead(dlon) over v ndlon,
        lag(fraud) over v pfraud, lead(fraud) over v nfraud,
        date_diff('hour', lag(ts) over v, ts) hprev, date_diff('hour', ts, lead(ts) over v) hnext
      from base window v as (partition by customer_id order by ts, transaction_id))
select * from w where fraud or hash(transaction_id)%10=0""").df()
f = d[d.fraud]; l = d[~d.fraud]
print(f'fraudes {len(f)}, legítimas (muestra 10%) {len(l)}\n')
print('## histograma |dlon| (10 bins de 0.1) — fraude vs legítima (proporciones)')
bins = np.linspace(0, 1, 11)
hf = np.histogram(f.dlon.abs(), bins)[0]; hl = np.histogram(l.dlon.abs(), bins)[0]
print(pd.DataFrame({'bin': [f'{a:.1f}-{b:.1f}' for a, b in zip(bins[:-1], bins[1:])], 'n_fraude': hf,
                    'p_fraude': (hf/hf.sum()).round(4), 'p_legit': (hl/hl.sum()).round(4)}).to_string(index=False))
print(f'chi2 fraude vs uniforme (10 bins): p={stats.chisquare(hf).pvalue:.4g}\n')
print(f'## dlon con signo, fraude: media={f.dlon.mean():.4f} (ee {0.577/np.sqrt(len(f)):.4f}); legít: {l.dlon.mean():.4f}\n')

for side, a, b in [('previa', 'pdlat', 'pdlon'), ('siguiente', 'ndlat', 'ndlon')]:
    ff = f.dropna(subset=[a, b]); ll = l.dropna(subset=[a, b])
    print(f'## correlación con la tx {side} con coords: fraude corr(dlat)={np.corrcoef(ff.dlat, ff[a])[0,1]:.4f} corr(dlon)={np.corrcoef(ff.dlon, ff[b])[0,1]:.4f} (n={len(ff)}, ee~{1/np.sqrt(len(ff)):.3f}); '
          f'legít corr(dlat)={np.corrcoef(ll.dlat, ll[a])[0,1]:.4f} corr(dlon)={np.corrcoef(ll.dlon, ll[b])[0,1]:.4f}')
    print(f'    media |dlon-{side}| fraude={np.abs(ff.dlon-ff[b]).mean():.4f} legít={np.abs(ll.dlon-ll[b]).mean():.4f} (esperado 2/3); '
          f'|dlat-{side}| fraude={np.abs(ff.dlat-ff[a]).mean():.4f} legít={np.abs(ll.dlat-ll[a]).mean():.4f}')
    # ¿la diferencia se explica por la |dlon| propia del fraude? E|X-Y| con Y~U(-1,1) = (1+X^2)/2
    print(f'    esperado |dlon-{side}| dado dlon del fraude y vecino uniforme: {((1+ff.dlon**2)/2).mean():.4f}')
    # la tx vecina de un fraude: ¿su |dlon| es rara?
    print(f'    |dlon| de la tx {side} de un fraude: media={ff[b].abs().mean():.4f} (esperado 0.5, ee {0.2887/np.sqrt(len(ff)):.4f})\n')
print('## hueco temporal a la previa/siguiente (horas): fraude vs legítima')
print(pd.DataFrame({'fraude': [f.hprev.median(), f.hnext.median()], 'legit': [l.hprev.median(), l.hnext.median()]}, index=['mediana_h_prev', 'mediana_h_next']).round(1).to_string())
print()
f2 = f.assign(band=pd.cut(f.fscore.fillna(-1), [-2, -0.5, 50, 101], labels=['fscore_nulo', 'fscore<50', 'fscore>=50']))
print('## |dlon| de fraude por tramo de fscore')
print(f2.groupby('band', observed=True).agg(n=('dlon', 'size'), media_adlon=('dlon', lambda x: x.abs().mean())).round(4).to_string())
