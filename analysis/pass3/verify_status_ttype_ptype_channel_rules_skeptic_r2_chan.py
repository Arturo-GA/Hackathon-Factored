"""Escéptico r2 (parte 3): ¿el canal es ruido también a nivel cliente/producto y en secuencia? (agregado en SQL)."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width', 250)

# Dispersión: chi2 de Pearson clientes x canal (y productos x canal) contra la mezcla global; cociente chi2/gl ~1 => multinomial iid
for key in ['customer_id', 'product_id']:
    r = q(f"""with g as (select channel, count(*)::double/(select count(*) from tx) p from tx group by 1),
      k as (select {key} k, count(*) tot from tx group by 1),
      o as (select {key} k, channel, count(*) n from tx group by 1,2),
      e as (select k.k, g.channel, k.tot*g.p ex from k cross join g)
      select sum(power(coalesce(o.n,0)-e.ex,2)/e.ex) chi2, (count(distinct e.k)-1)*5 gl, count(distinct e.k) nk
      from e left join o on o.k=e.k and o.channel=e.channel""")
    c2, gl = float(r.chi2[0]), float(r.gl[0])
    print(f"{key}: chi2/gl={c2/gl:.4f}  (n={int(r.nk[0])}, p={chi2.sf(c2, gl):.3f})")

# Secuencia: P(mismo canal que la tx previa del cliente) vs sum p^2
r = q("""with s as (select channel, lag(channel) over (partition by customer_id order by ts, transaction_id) prev from tx)
  select avg((channel=prev)::int) p_mismo, count(*) n from s where prev is not null""")
g = q("select count(*)::double/(select count(*) from tx) p from tx group by channel")
print(f"P(mismo canal que la previa)={r.p_mismo[0]:.4f}  esperado iid={float((g.p**2).sum()):.4f}  n={int(r.n[0])}")
