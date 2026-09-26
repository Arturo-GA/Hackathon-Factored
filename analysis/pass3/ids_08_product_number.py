# ids_08: formato de product_number por tipo de producto; validez Luhn y prefijo BIN en tarjetas; duplicados; employee_code/branch_code
import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select ptype, regexp_replace(regexp_replace(product_number,'[A-Z]','A','g'),'[0-9]','9','g') pat, count(*) n from pr group by all order by ptype, n desc"""))
print(q("""select ptype, left(product_number, 4) pref, count(*) n from pr where ptype not like 'Cuenta%' and ptype not like 'Tarjeta%' group by all order by ptype, n desc limit 12"""))
print(q("""select ptype, left(product_number,1) d1, count(*) n from pr where ptype like 'Tarjeta%' group by all order by ptype, n desc"""))
print(q("""select count(*) n, count(distinct product_number) nd from pr"""))
print(q("""with d as (select product_number, count(*) k, count(distinct customer_id) nc, count(distinct ptype) nt from pr group by 1 having count(*)>1)
   select count(*) dup_numbers, sum(k) nrows, avg((nc>1)::int) diff_cust, avg((nt>1)::int) diff_type from d"""))
# Luhn en tarjetas
df = con.execute("select ptype, product_number from pr where ptype like 'Tarjeta%' using sample 100000").fetchdf()
def luhn(s):
    d=[int(x) for x in s][::-1]; t=0
    for i,x in enumerate(d):
        if i%2==1:
            x*=2
            if x>9: x-=9
        t+=x
    return t%10==0
df['luhn']=df.product_number.map(lambda s: luhn(s) if s.isdigit() else None)
print(df.groupby('ptype').luhn.agg(['mean','count']))
# cuentas de 10 dígitos: Luhn?
df2 = con.execute("select ptype, product_number from pr where length(product_number)=10 and regexp_full_match(product_number,'[0-9]+') using sample 50000").fetchdf()
df2['luhn']=df2.product_number.map(luhn); print(df2.groupby('ptype').luhn.agg(['mean','count']))
print(q("select count(*) n, count(distinct employee_code) nd, min(employee_code), max(employee_code) from ag"))
print(q("select count(*) n, count(distinct branch_code) nd, min(branch_code), max(branch_code) from br"))
