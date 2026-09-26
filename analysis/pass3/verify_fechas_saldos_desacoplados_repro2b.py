# Verificacion independiente (parte B): rechazos/codigos vs fechas, saldo vs flujos, limite
import duckdb, numpy as np, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250)


def df(s):
    return con.execute(s).df()


def q(title, s):
    print('==', title)
    print(df(s).to_string(), '\n', flush=True)


def rr_table(title, s, grp):
    """s devuelve grp, n y sumas d (declined), c05, c14, c51, c54; imprime tasas y RR (True vs False) con IC95."""
    d = df(s).set_index(grp)
    print('==', title)
    out = []
    for col in ['d', 'c05', 'c14', 'c51', 'c54']:
        a, n1 = d.loc[True, col], d.loc[True, 'n']
        c, n0 = d.loc[False, col], d.loc[False, 'n']
        r1, r0 = a / n1, c / n0
        rr = r1 / r0
        se = np.sqrt(1 / a - 1 / n1 + 1 / c - 1 / n0)
        out.append([col, int(n1), round(100 * r1, 3), int(n0), round(100 * r0, 3), round(rr, 3),
                    round(rr * np.exp(-1.96 * se), 3), round(rr * np.exp(1.96 * se), 3)])
    print(pd.DataFrame(out, columns=['metrica', 'n_true', 'pct_true', 'n_false', 'pct_false', 'RR', 'lo95', 'hi95']).to_string(), '\n', flush=True)


M = """count(*) n, sum((t.status='Declined')::int) d, sum((t.code='05')::int) c05, sum((t.code='14')::int) c14,
       sum((t.code='51')::int) c51, sum((t.code='54')::int) c54"""


def FX(alias):
    return f"(case {alias}.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"


q('B0 codigo por status', """select status, count(*) n, avg((code is null)::int) nul, avg((code='05')::int) c05, avg((code='14')::int) c14,
   avg((code='51')::int) c51, avg((code='54')::int) c54 from tx group by 1 order by 2 desc""")
rr_table('B1 antes de apertura (True) vs despues',
         f"select (t.ts::date < p.opened) g, {M} from tx t join pr p using(product_id) group by 1", 'g')
rr_table('B2 tras vencimiento (True) vs vigente (solo productos con expires)',
         f"select (t.ts::date > p.expires) g, {M} from tx t join pr p using(product_id) where p.expires is not null group by 1", 'g')
q('B2b P(codigo | Declined) segun vencida', """select (t.ts::date > p.expires) after_exp, count(*) n_decl,
   avg((t.code='54')::int) c54_given_decl, avg((t.code='51')::int) c51_given_decl
   from tx t join pr p using(product_id) where p.expires is not null and t.status='Declined' group by 1""")
rr_table('B3 fuera de vigencia (antes de abrir o vencida) vs dentro',
         f"select ((t.ts::date < p.opened) or (p.expires is not null and t.ts::date > p.expires)) g, {M} from tx t join pr p using(product_id) group by 1", 'g')

# C. saldo vs flujos
q('C0 mezcla ttype por ptype (share)', """with a as (select p.ptype, t.ttype, count(*) n from tx t join pr p using(product_id) group by all)
   pivot (select ptype, ttype, round(n/sum(n) over (partition by ptype),3) sh from a) on ttype using first(sh) order by ptype""")
q('C1 corr(bal, flujos) por ptype x moneda, tx aprobadas (Pearson p_, Spearman s_)', """
   with f as (select product_id,
        sum(case when ttype='Deposit' then amount when ttype in ('Withdrawal','Purchase','Payment','Transfer') then -amount else 0 end) net,
        sum(amount) filter (where ttype='Deposit') dep, sum(amount) filter (where ttype<>'Deposit') deb, count(*) ntx
        from tx where status='Approved' group by 1),
   j as (select p.ptype, p.currency, p.bal, f.net, coalesce(f.dep,0) dep, coalesce(f.deb,0) deb, f.ntx from f join pr p using(product_id)),
   r as (select *, rank() over (partition by ptype, currency order by bal) rb, rank() over (partition by ptype, currency order by net) rn,
                rank() over (partition by ptype, currency order by dep) rd, rank() over (partition by ptype, currency order by ntx) rt from j)
   select ptype, currency, count(*) np, round(corr(net, bal),4) p_net, round(corr(rn, rb),4) s_net, round(corr(rd, rb),4) s_dep,
          round(corr(deb, bal),4) p_deb, round(corr(rt, rb),4) s_ntx
   from r group by all order by 1,2""")
q('C2 corr pooled USD-eq por ptype (como el hallazgo)', f"""
   with f as (select product_id,
        sum(case when ttype='Deposit' then 1 when ttype in ('Withdrawal','Purchase','Payment','Transfer') then -1 else 0 end * amount/{FX('tx')}) net,
        sum(case when ttype='Deposit' then 1 when ttype in ('Withdrawal','Purchase') then -1 else 0 end * amount/{FX('tx')}) net_sin_tp
        from tx where status='Approved' group by 1)
   select p.ptype, count(*) np, round(corr(f.net, p.bal/{FX('p')}),4) r_net, round(avg(f.net),1) mean_net_usd,
      round(avg(f.net_sin_tp),1) mean_net_sin_transf_pay, round(avg(p.bal/{FX('p')}),1) mean_bal_usd, min(p.bal) min_bal,
      round(avg((f.net<0)::int),3) sh_net_neg, round(avg((-f.net > p.bal/{FX('p')})::int),3) sh_salida_mayor_saldo
   from f join pr p using(product_id) group by 1 order by 2 desc""")

# D. limite de tarjeta y saldo
q('D1 tarjetas credito: bal>limite (productos) y cuantiles bal/limite', """select count(*) n_con_lim, sum((bal>credit_limit)::int) n_over,
   avg((bal>credit_limit)::int) sh_over, quantile_cont(bal/credit_limit, [0.01,0.25,0.5,0.75,0.99]) q_ratio, max(bal/credit_limit) max_ratio
   from pr where ptype='Tarjeta Crédito' and credit_limit is not null""")
q('D1b productos con limite: bal>limite por ptype', "select ptype, count(*) n, avg((bal>credit_limit)::int) sh_over from pr where credit_limit is not null group by 1")
rr_table('D2 tx en tarjetas con bal>limite (True) vs resto',
         f"select (p.bal>p.credit_limit) g, {M} from tx t join pr p using(product_id) where p.ptype='Tarjeta Crédito' and p.credit_limit is not null group by 1", 'g')
rr_table('D3 TC Purchase/Withdrawal: monto > disponible (limite-bal) (True) vs resto',
         f"""select (t.amount > p.credit_limit - p.bal) g, {M} from tx t join pr p using(product_id)
             where p.ptype='Tarjeta Crédito' and p.credit_limit is not null and t.ttype in ('Purchase','Withdrawal') group by 1""", 'g')
rr_table('D4 debito/ahorro/corriente W/P/T: monto > saldo (True) vs resto',
         f"""select (t.amount > p.bal) g, {M} from tx t join pr p using(product_id)
             where p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') and t.ttype in ('Withdrawal','Purchase','Transfer') group by 1""", 'g')
q('D4b por ptype', """select p.ptype, (t.amount > p.bal) over_bal, count(*) n, round(100*avg((t.status='Declined')::int),3) decl_pct,
   round(100*avg((t.code='51')::int),3) c51_pct
   from tx t join pr p using(product_id) where p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito')
   and t.ttype in ('Withdrawal','Purchase','Transfer') group by all order by 1,2""")
q('D4c solo debito/ahorro (sin corriente)', """select (t.amount > p.bal) over_bal, count(*) n, round(100*avg((t.status='Declined')::int),3) decl_pct,
   round(100*avg((t.code='51')::int),3) c51_pct
   from tx t join pr p using(product_id) where p.ptype in ('Cuenta Ahorro','Tarjeta Débito')
   and t.ttype in ('Withdrawal','Purchase','Transfer') group by all order by 1""")
