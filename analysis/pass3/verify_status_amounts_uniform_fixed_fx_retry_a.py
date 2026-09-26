"""Verificacion independiente (retry) de status_amounts_uniform_fixed_fx. Parte A: esquema, nulos, tasa fija."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def show(sql, title=None):
    if title: print("==", title)
    cur = con.execute(sql); cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for r in cur.fetchall(): print(" | ".join(str(v) for v in r))
show("select column_name, data_type from information_schema.columns where table_name='tx' and column_name in ('amount','amount_usd','currency','ts','process_date','ttype')", "tipos tx")
show("select column_name, data_type from information_schema.columns where table_name='fx'", "tipos fx")
show("""select currency, count(*) n, sum(case when amount_usd is null then 1 else 0 end) n_null,
 round(100.0*avg(case when amount_usd is null then 1 else 0 end),3) pct_null,
 sum(case when amount_usd is not null then 1 else 0 end) n_nonnull from tx group by 1 order by 1""", "nulos amount_usd por moneda")
show("select round(100.0*avg(case when amount_usd is null then 1 else 0 end),3) pct_null_total, count(*) n from tx", "nulos total")
K = "(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end)"
show(f"""select currency, count(*) n_nonnull,
 sum(case when amount_usd = round(amount/{K},2) then 1 else 0 end) eq_round2_exacto,
 sum(case when abs(amount_usd - round(amount/{K},2)) < 1e-6 then 1 else 0 end) eq_round2_tol1e6,
 sum(case when abs(amount_usd - amount/{K}) <= 0.005 + 1e-9 then 1 else 0 end) dentro_medio_centavo,
 sum(case when abs(amount_usd - amount/{K}) <= 0.01 then 1 else 0 end) dentro_1_centavo,
 max(abs(amount_usd - amount/{K})) max_abs_dif,
 sum(case when abs(amount_usd*100 - round(amount_usd*100)) > 1e-6 then 1 else 0 end) usd_con_mas_de_2_dec
 from tx where amount_usd is not null group by 1 order by 1""", "tasa fija 4000/350")
show(f"""select currency, count(*) n, min(amount/amount_usd) r_min, quantile_cont(amount/amount_usd,0.001) r_p001,
 median(amount/amount_usd) r_med, quantile_cont(amount/amount_usd,0.999) r_p999, max(amount/amount_usd) r_max
 from tx where amount_usd >= 10 group by 1 order by 1""", "ratio amount/amount_usd (amount_usd>=10)")
show("""select currency, count(*) n,
 sum(case when abs(amount*100 - round(amount*100)) > 1e-6 then 1 else 0 end) mas_de_2_dec,
 sum(case when amount = round(amount) then 1 else 0 end) enteros,
 sum(case when amount <= 0 then 1 else 0 end) no_positivos from tx group by 1 order by 1""", "decimales de amount")
