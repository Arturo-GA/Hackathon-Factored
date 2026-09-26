"""Verificacion (retry) status_amounts_uniform_fixed_fx. Parte D: por que COP*rate(COP->USD) coincide 9%: precision de la tasa inversa."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def show(sql, title=None):
    if title: print("==", title)
    cur = con.execute(sql); cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for r in cur.fetchall(): print(" | ".join(str(v) for v in r))
show("select src, dst, count(distinct rate) n_distintos, min(rate) mn, max(rate) mx from fx where dst='USD' group by 1,2", "precision tasas ->USD")
show("select rate, count(*) dias from fx where src='COP' and dst='USD' group by 1 order by 2 desc limit 6", "valores COP->USD mas frecuentes")
show("""with t as (select amount, amount_usd, cast(ts as date) d from tx where amount_usd is not null and currency='COP'),
 f2 as (select date, rate from fx where src='COP' and dst='USD')
 select (f2.rate = 0.00025) dia_tasa_inv_igual_fija, count(*) n,
   round(100.0*avg(case when abs(t.amount*f2.rate - t.amount_usd) <= 0.005+1e-9 then 1 else 0 end),3) pct_match_inv
 from t join f2 on f2.date=t.d group by 1 order by 1""", "match inverso segun si la tasa inversa redondeada = 1/4000")
show("""select count(*) dias, sum(case when rate=0.00025 then 1 else 0 end) dias_0_00025 from fx where src='COP' and dst='USD'""", "dias con COP->USD = 0.00025")
show("""select round(100.0*avg(case when f.rate=0.00025 then 1 else 0 end),2) pct_tx_en_dias_0_00025 from tx t join fx f on f.date=cast(t.ts as date) and f.src='COP' and f.dst='USD' where t.currency='COP' and t.amount_usd is not null""", "tx COP en esos dias")
