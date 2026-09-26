"""¿La ausencia de valores (nulos inyectados) se asocia con fraude/estado? Tasas por indicador de nulo."""
from behavior_common import connect, q
con = connect()
inds = {"city_null": "city IS NULL", "latlon_null": "lat IS NULL", "fscore_null": "fscore IS NULL", "branch_null_atm": "(channel IN ('ATM','Branch') AND branch_id IS NULL)",
        "merchant_null_pur": "(ttype='Purchase' AND merchant_name IS NULL)", "tcat_null_pay": "(ttype='Payment' AND tcat IS NULL)",
        "usd_null_nonusd": "(currency<>'USD' AND amount_usd IS NULL)", "country_null": "country IS NULL", "channel_null": "channel IS NULL"}
sel = ", ".join([f"avg(({v})::INT) {k}" for k, v in inds.items()])
print(q(con, f"SELECT fraud, count(*) n, {sel} FROM tx GROUP BY 1").T)
print(q(con, f"SELECT status, count(*) n, {sel} FROM tx GROUP BY 1").T)
print(q(con, "SELECT status, count(*) n, avg((code IS NULL)::INT) code_null, avg((code='00')::INT) c00 FROM tx GROUP BY 1"))
