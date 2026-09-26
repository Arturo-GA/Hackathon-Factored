"""Comercios: catálogo, mcat vs tcat, recurrencia cliente-comercio, intervalos (suscripciones)."""
from behavior_common import connect, q
con = connect()
print(q(con, "SELECT count(DISTINCT merchant_name) nm, count(merchant_name) n_non_null, count(*) n FROM tx"))
print(q(con, "SELECT ttype, count(merchant_name) nm, count(*) n, count(mcat) nmc, count(tcat) ntc FROM tx GROUP BY 1"))
print(q(con, "SELECT merchant_name, mcat, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 60"))
print(q(con, "SELECT tcat, mcat, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2 ORDER BY 1,3 DESC LIMIT 60"))
