"""Geo de la tx: clusters de lat/lon vs pais/ciudad de la tx y del cliente."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2_contingency
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250)
df = q("select round(lat) la, round(lon) lo, count(*) n from tx where lat is not null group by 1,2 order by 3 desc limit 15")
print(df.to_string())
ct = q("""select t.city, round(t.lat)||','||round(t.lon) cl, count(*) n from tx t where lat is not null group by 1,2""").pivot(index='city',columns='cl',values='n').fillna(0)
chi2=chi2_contingency(ct.values)[0]; print("V ciudad_tx x cluster_geo =", np.sqrt(chi2/(ct.values.sum()*(min(ct.shape)-1))).round(4), ct.shape)
ct = q("""select u.city, round(t.lat)||','||round(t.lon) cl, count(*) n from tx t join cu u using(customer_id) where lat is not null group by 1,2""").pivot(index='city',columns='cl',values='n').fillna(0)
chi2=chi2_contingency(ct.values)[0]; print("V ciudad_cliente x cluster_geo =", np.sqrt(chi2/(ct.values.sum()*(min(ct.shape)-1))).round(4), ct.shape)
print(q("select city, country, count(*) n from tx group by 1,2 order by 3 desc limit 40").to_string())
