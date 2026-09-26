"""Verificacion independiente (retry) de status_amounts_uniform_fixed_fx. Parte B: desempates de redondeo y tabla fx."""
import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def show(sql, title=None):
    if title: print("==", title)
    cur = con.execute(sql); cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for r in cur.fetchall(): print(" | ".join(str(v) for v in r))
K = "(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end)"
# 1) Los no-iguales a round(amount/k,2): son empates x.xx5? Coinciden con round() de Python (half-even sobre float)?
rows = con.execute(f"select currency, amount, amount_usd from tx where amount_usd is not null and amount_usd <> round(amount/{K},2)").fetchall()
print("== desajustes vs round() de DuckDB:", len(rows))
kk = {'COP':4000,'ARS':350}
ok_py = sum(1 for c,a,u in rows if round(a/kk[c],2) == u)
tie = sum(1 for c,a,u in rows if abs(abs(a/kk[c]-u) - 0.005) < 1e-9)
print("   coinciden con round() de Python:", ok_py, "| son empates a medio centavo:", tie)
for r in rows[:5]: print("   ej:", r, "amount/k =", repr(r[1]/kk[r[0]]))
# verificacion global con round de Python sobre muestra grande (hash) para no cargar todo
smp = con.execute(f"select currency, amount, amount_usd from tx where amount_usd is not null and hash(transaction_id) % 5 = 0").fetchall()
okp = sum(1 for c,a,u in smp if round(a/kk[c],2) == u)
print("== muestra 1/5 no nulos: n=", len(smp), " coincide exacto con round(amount/k,2) de Python:", okp, f"({100*okp/len(smp):.4f}%)")
del smp
# 2) tabla fx
show("select src, dst, count(*) n, min(date) d0, max(date) d1, round(min(rate),4) mn, round(avg(rate),4) av, round(max(rate),4) mx, round(stddev(rate),4) sd, count(distinct source) nsrc from fx group by 1,2 order by 1,2", "fx por par")
show("select count(*) n_filas, count(distinct date) n_dias from fx", "fx dias")
show("select src,dst, sum(case when rate=4000 then 1 else 0 end) r4000, sum(case when rate=350 then 1 else 0 end) r350, sum(case when abs(rate-4000)<1 then 1 else 0 end) r4000_1, sum(case when abs(rate-350)<0.1 then 1 else 0 end) r350_01 from fx where (src='USD' and dst in ('COP','ARS')) group by 1,2", "fx dias con tasa ~fija")
show("select min(ts) t0, max(ts) t1, min(process_date) p0, max(process_date) p1 from tx", "rango tx")
