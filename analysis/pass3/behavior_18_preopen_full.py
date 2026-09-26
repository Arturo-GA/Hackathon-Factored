"""Verificación en población completa: tasa de fraude/rechazo en tx previas a apertura del producto / posteriores a vencimiento."""
from behavior_common import connect, q
con = connect()
print(q(con, """SELECT (t.ts::DATE < p.opened)::INT pre_open, coalesce((t.ts::DATE > p.expires)::INT,0) post_exp, count(*) n, sum(t.fraud::INT) nfraud,
  avg(t.fraud::INT)*1000 fraud_per_mil, avg((t.status='Declined')::INT)*100 decl_pct, avg((t.code='54')::INT)*100 code54_pct
  FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2 ORDER BY 1,2"""))
