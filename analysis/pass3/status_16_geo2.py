"""Geo: caja geografica de lat/lon segun pais del cliente y pais de la tx."""
import duckdb, pandas as pd, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250)
box = """case when abs(t.lat)<=2 and abs(t.lon)<=2 then 'NullIsland(0,0)'
 when t.lat between 0 and 13 and t.lon between -80 and -66 then 'Colombia'
 when t.lat between -56 and -21 and t.lon between -74 and -53 then 'Argentina'
 when t.lat between 14 and 33 and t.lon between -118 and -86 then 'Mexico' else 'otro' end"""
df = q(f"""select u.country cu_pais, t.country tx_pais, {box} caja, count(*) n from tx t join cu u using(customer_id) where t.lat is not null group by 1,2,3""")
df['foreign']=df.cu_pais!=df.tx_pais
print(df.groupby(['cu_pais','foreign','caja']).n.sum().unstack().fillna(0).astype(int).to_string())
print(q("select round(lat,1) la, round(lon,1) lo, count(*) n from tx t where abs(lat)<=2 and abs(lon)<=2 group by 1,2 order by 3 desc limit 8").to_string())
print(q("select min(lat), max(lat), min(lon), max(lon), stddev(lat), stddev(lon) from tx t where abs(lat)<=2 and abs(lon)<=2").to_string())
