import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
def cl(la,lo):
    return f"""case when abs({la}+34.6037)<=1.01 and abs({lo}+58.3816)<=1.01 then 'BA' when abs({la}-4.711)<=1.01 and abs({lo}+74.0721)<=1.01 then 'BOG' when abs({la})<=1.01 and abs({lo})<=1.01 then 'Z' else 'O' end"""
C=f"(select t.*, cu.country cc, {cl('lat','lon')} cl from tx t join cu using(customer_id) where lat is not null)"
q(f"select cc, {cl('lat','-58.3816')} latc, {cl('-34.6037','lon')} lonc_ba, count(*) n from {C} where cl='O' group by all order by n desc limit 20")
# classify lat center and lon center separately
q(f"""select cc, case when abs(lat+34.6037)<=1.01 then 'BA' when abs(lat-4.711)<=1.01 then 'BOG' when abs(lat)<=1.01 then 'Z' else '?' end latc,
 case when abs(lon+58.3816)<=1.01 then 'BA' when abs(lon+74.0721)<=1.01 then 'BOG' when abs(lon)<=1.01 then 'Z' else '?' end lonc, count(*) n
 from {C} where cl='O' group by all order by n desc""")
q(f"select cc, cl, fraud, count(*) n from {C} group by all order by 1,2,3")
q(f"select cl='O' other, count(*) n, avg(fraud::int)*1000 fraud_pm, avg((status='Declined')::int) decl, avg(fscore) fs, avg((country<>cc)::int) foreign_ from {C} group by all")
