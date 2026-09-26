# H11: escala del monto de tx vs atributos del producto (bal, credit_limit) y del cliente (income) dentro de moneda
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table s as select t.amount, t.currency, t.ttype, t.status, p.ptype, p.bal, p.credit_limit, c.income, c.credit_score, c.segment, c.country
  from (select * from tx using sample 300000) t join pr p using(product_id) join cu c on c.customer_id=t.customer_id""")
print(q("""select currency, count(*) n, round(corr(ln(amount), ln(abs(bal)+1)),3) r_bal, round(corr(ln(amount), ln(credit_limit+1)),3) r_lim,
  round(corr(ln(amount), ln(income+1)),3) r_inc, round(corr(ln(amount), credit_score),3) r_cs, round(regr_r2(ln(amount), ln(abs(bal)+1)),3) r2bal
  from s group by 1"""))
print(q("""select currency, ptype, count(*) n, round(median(amount),1) med, round(corr(ln(amount), ln(abs(bal)+1)),3) r_bal,
  round(corr(ln(amount), ln(credit_limit+1)),3) r_lim, round(median(amount/nullif(abs(bal),0)),4) med_ratio_bal from s group by 1,2 order by 1,3 desc"""))
print(q("""select currency, ttype, count(*) n, round(median(amount),1) med, round(corr(ln(amount), ln(abs(bal)+1)),3) r_bal from s group by 1,2 order by 1,2"""))
print(q("""select currency, segment, round(median(amount),1) med, count(*) n from s group by 1,2 order by 1,2"""))
