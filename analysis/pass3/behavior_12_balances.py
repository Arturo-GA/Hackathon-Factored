"""Saldos y límites: bal vs credit_limit, vs income, distribución por ptype/moneda; code 51 (fondos insuf.) vs bal."""
from behavior_common import connect, q
con = connect()
print(q(con, """SELECT ptype, currency, count(*) n, avg((bal<0)::INT) neg, avg((credit_limit IS NULL)::INT) cl_null,
  quantile_cont(bal,[0,0.5,1]) bal_q, quantile_cont(credit_limit,[0,0.5,1]) cl_q, avg((bal>credit_limit)::INT) bal_gt_cl,
  quantile_cont(rate,[0,0.5,1]) rate_q FROM pr GROUP BY 1,2 ORDER BY 1,2"""))
# escala con ingreso
print(q(con, """SELECT p.ptype, count(*) n, corr(ln(1+p.bal), ln(1+c.income)) c_bal_inc, corr(ln(1+p.credit_limit), ln(1+c.income)) c_cl_inc,
   corr(p.credit_limit, c.credit_score) c_cl_score, corr(p.rate, c.credit_score) c_rate_score FROM pr p JOIN cu c USING(customer_id) WHERE p.currency='USD' GROUP BY 1"""))
print(q(con, "SELECT country, quantile_cont(income,[0.01,0.5,0.99]) inc_q FROM cu GROUP BY 1"))
# tasa de rechazo/código 51 según bal relativo al monto
print(q(con, """SELECT CASE WHEN t.amount > p.bal THEN 'amt>bal' ELSE 'amt<=bal' END k, t.ttype IN ('Deposit') dep, count(*) n, avg((t.status='Declined')::INT) decl, avg((t.code='51')::INT) c51
   FROM tx t JOIN pr p USING(product_id) WHERE p.ptype IN ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') GROUP BY 1,2 ORDER BY 1,2"""))
print(q(con, """SELECT CASE WHEN t.amount > p.credit_limit - p.bal THEN 'amt>disp' ELSE 'amt<=disp' END k, count(*) n, avg((t.status='Declined')::INT) decl, avg((t.code='51')::INT) c51
   FROM tx t JOIN pr p USING(product_id) WHERE p.ptype='Tarjeta Crédito' GROUP BY 1"""))
