"""Parte 8: caracterizar la débil diferencia de |dlon| en fraude: signo, fscore, correlación con tx previa."""
import duckdb, pandas as pd, numpy as np
from scipy import stats
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
d = con.execute("""
with g as (select t.transaction_id, t.customer_id, t.ts, t.fraud, t.fscore, t.channel, t.ttype, t.amount, t.status, cu.country cc,
   t.lat - case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.711 else 0 end dlat,
   t.lon - case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end dlon
 from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null),
s as (select *, lag(dlat) over w pdlat, lag(dlon) over w pdlon, lag(fraud) over w pfraud from g window w as (partition by customer_id order by ts, transaction_id))
select * from s where fraud or pfraud or hash(transaction_id)%20=0""").df()
f = d[d.fraud]; l = d[~d.fraud & ~d.pfraud.fillna(False)]
print('fraudes', len(f), 'legit muestra', len(l))
print('dlon con signo fraude: media %.4f, sd %.4f (U(-1,1): 0, 0.5774); legit: %.4f, %.4f' % (f.dlon.mean(), f.dlon.std(), l.dlon.mean(), l.dlon.std()))
print('dlat con signo fraude: media %.4f, sd %.4f; legit: %.4f, %.4f' % (f.dlat.mean(), f.dlat.std(), l.dlat.mean(), l.dlat.std()))
print('hist dlon fraude (20 bins -1..1):', np.histogram(f.dlon, bins=np.linspace(-1, 1, 21))[0])
# by fscore band
f = f.assign(band=pd.cut(f.fscore.fillna(-1), [-2, -0.5, 30, 50, 101], labels=['nulo', '<=30', '30-50', '>=50']))
print(f.groupby('band', observed=True).agg(n=('dlon', 'size'), m_adlon=('dlon', lambda x: x.abs().mean()), m_adlat=('dlat', lambda x: x.abs().mean())).round(4))
print(f.groupby('channel').agg(n=('dlon', 'size'), m_adlon=('dlon', lambda x: x.abs().mean())).round(4))
print(f.groupby('status').agg(n=('dlon', 'size'), m_adlon=('dlon', lambda x: x.abs().mean())).round(4))
# correlation with previous tx jitter
ff = f.dropna(subset=['pdlon']); ll = l.dropna(subset=['pdlon'])
print('corr(dlon, dlon_prev) fraude: %.4f (n=%d)  legit: %.4f (n=%d)' % (np.corrcoef(ff.dlon, ff.pdlon)[0, 1], len(ff), np.corrcoef(ll.dlon, ll.pdlon)[0, 1], len(ll)))
print('corr(dlat, dlat_prev) fraude: %.4f  legit: %.4f' % (np.corrcoef(ff.dlat, ff.pdlat)[0, 1], np.corrcoef(ll.dlat, ll.pdlat)[0, 1]))
print('|dlon - dlon_prev| fraude media %.4f  legit %.4f (esperado 2/3=0.6667)' % ((ff.dlon - ff.pdlon).abs().mean(), (ll.dlon - ll.pdlon).abs().mean()))
print('|dlat - dlat_prev| fraude media %.4f  legit %.4f' % ((ff.dlat - ff.pdlat).abs().mean(), (ll.dlat - ll.pdlat).abs().mean()))
# If the prev-distance effect were only due to fraud concentration, |dlon-dlon_prev| expected for fraud given its own |dlon| dist:
sim = np.mean([np.abs(x - np.random.default_rng(i).uniform(-1, 1, 2000)).mean() for i, x in enumerate(ff.dlon.values[:400])])
print('esperado |dlon-prev| si prev es uniforme independiente, dada la dlon observada del fraude: %.4f' % sim)
# next tx for fraud: distance in lon
d2 = con.execute("""
with g as (select t.transaction_id, t.customer_id, t.ts, t.fraud,
   t.lon - case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end dlon
 from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null),
s as (select *, lead(dlon) over w ndlon from g window w as (partition by customer_id order by ts, transaction_id))
select dlon, ndlon from s where fraud and ndlon is not null""").df()
print('|dlon - dlon_next| fraude media %.4f (n=%d)' % ((d2.dlon - d2.ndlon).abs().mean(), len(d2)))
