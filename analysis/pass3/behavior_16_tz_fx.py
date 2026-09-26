"""(a) Desfase ts vs process_date por tabla (¿UTC vs local?) (b) tasas fijas de amount_usd vs tabla fx (c) rangos uniformes de amount_usd por ttype
(d) fraude por ptype/ttype (e) hora local de tx por país."""
from behavior_common import connect, q
con = connect()
for t in ['tx', 'cc', 'cp', 'sv']:
    cols = ", ".join([f"avg((process_date = (ts - INTERVAL {h} HOUR)::DATE)::INT) h{h}" for h in range(0, 11)])
    print(t, q(con, f"SELECT {cols} FROM (SELECT * FROM {t} WHERE process_date IS NOT NULL AND ts IS NOT NULL USING SAMPLE 200000)").round(4).to_dict('records'))
print(q(con, "SELECT src, dst, count(*) n, min(rate) mn, median(rate) med, max(rate) mx, min(date), max(date) FROM fx GROUP BY 1,2 ORDER BY 1,2"))
# tasa implícita en tx por año
print(q(con, "SELECT currency, year(ts) y, median(amount/amount_usd) r, stddev(amount/amount_usd) sd FROM tx WHERE amount_usd>0 GROUP BY 1,2 ORDER BY 1,2"))
# rango usd por ttype (normalizando a USD con tasas fijas)
print(q(con, """SELECT ttype, min(u) mn, max(u) mx, quantile_cont(u,[0.25,0.5,0.75]) q, avg(u) mean FROM (SELECT ttype, CASE currency WHEN 'USD' THEN amount WHEN 'COP' THEN amount/4000 ELSE amount/350 END u FROM tx) GROUP BY 1 ORDER BY 1"""))
print(q(con, "SELECT p.ptype, count(*) n, avg(t.fraud::INT)*1000 fraud_per_mil, avg((t.status='Declined')::INT) decl FROM tx t JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1"))
print(q(con, "SELECT ttype, count(*) n, avg(fraud::INT)*1000 fraud_per_mil FROM tx GROUP BY 1 ORDER BY 1"))
