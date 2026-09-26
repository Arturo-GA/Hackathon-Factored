# Verificacion independiente (parte C): dosis-respuesta y AUC (Mann-Whitney, IC Hanley-McNeil)
import duckdb, numpy as np, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250)


def q(title, s):
    print('==', title)
    print(con.execute(s).df().to_string(), '\n', flush=True)


def auc(title, base, score, y):
    """AUC de 'score' para predecir 'y' (booleano) sobre la consulta base (alias t,p)."""
    s = f"""with x as (select {score} s, ({y})::int y {base}),
            r as (select y, rank() over (order by s) + (count(*) over (partition by s) - 1) / 2.0 ar from x)
            select sum(ar) filter (where y=1) sr, count(*) filter (where y=1) n1, count(*) filter (where y=0) n0 from r"""
    sr, n1, n0 = con.execute(s).fetchone()
    a = (sr - n1 * (n1 + 1) / 2) / (n1 * n0)
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    se = np.sqrt((a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0))
    print(f'AUC {title}: {a:.4f} [{a - 1.96 * se:.4f}, {a + 1.96 * se:.4f}]  n1={n1:,} n0={n0:,}', flush=True)


CC = """from tx t join pr p using(product_id) where p.ptype='Tarjeta Crédito' and p.credit_limit is not null
        and t.ttype in ('Purchase','Withdrawal')"""
RC = "case when p.credit_limit - p.bal <= 0 then 1e12 else t.amount / (p.credit_limit - p.bal) end"
AC = """from tx t join pr p using(product_id) where p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito')
        and t.ttype in ('Withdrawal','Purchase','Transfer')"""
RA = "case when p.bal <= 0 then 1e12 else t.amount / p.bal end"

q('E1 TC: deciles de monto/disponible', f"""with x as (select {RC} r, t.status, t.code {CC}), y as (select *, ntile(10) over (order by r) d from x)
   select d, count(*) n, round(min(r),3) rmin, round(max(r),3) rmax, round(100*avg((status='Declined')::int),3) decl_pct,
   round(100*sum((code='51')::int)/count(*),3) c51_pct from y group by 1 order by 1""")
q('E2 cuentas/debito: deciles de monto/saldo', f"""with x as (select {RA} r, t.status, t.code {AC}), y as (select *, ntile(10) over (order by r) d from x)
   select d, count(*) n, round(min(r),3) rmin, round(max(r),3) rmax, round(100*avg((status='Declined')::int),3) decl_pct,
   round(100*sum((code='51')::int)/count(*),3) c51_pct from y group by 1 order by 1""")
q('E3 tarjetas con expires: codigo 54 por anios desde vencimiento', """select least(greatest(date_diff('day', p.expires, t.ts::date) // 365, -6), 5) anios_desde_venc,
   count(*) n, round(100*avg((t.status='Declined')::int),3) decl_pct, round(100*sum((t.code='54')::int)/count(*),3) c54_pct
   from tx t join pr p using(product_id) where p.expires is not null group by 1 order by 1""")
q('E4 todas: rechazo y codigo 14 por anios antes de apertura', """select least(date_diff('day', t.ts::date, p.opened) // 365, 3) anios_antes_apertura,
   count(*) n, round(100*avg((t.status='Declined')::int),3) decl_pct, round(100*sum((t.code='14')::int)/count(*),3) c14_pct
   from tx t join pr p using(product_id) where t.ts::date < p.opened group by 1 order by 1""")

auc('TC monto/disponible -> Declined', CC, RC, "t.status='Declined'")
auc('TC monto/disponible -> codigo 51', CC, RC, "coalesce(t.code='51', false)")
auc('Cuentas monto/saldo -> Declined', AC, RA, "t.status='Declined'")
auc('Cuentas monto/saldo -> codigo 51', AC, RA, "coalesce(t.code='51', false)")
auc('Dias desde vencimiento -> codigo 54', "from tx t join pr p using(product_id) where p.expires is not null",
    "date_diff('day', p.expires, t.ts::date)", "coalesce(t.code='54', false)")
auc('Dias antes de apertura -> Declined', "from tx t join pr p using(product_id)",
    "date_diff('day', t.ts::date, p.opened)", "t.status='Declined'")
