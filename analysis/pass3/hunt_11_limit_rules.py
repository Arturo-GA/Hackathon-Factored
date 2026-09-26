"""hunt_11: credit_limit / bal / rate / dpd vs segment, income, credit_score (reglas de generacion de producto)."""
import duckdb
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
F = "CASE p.currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END"
INC = "c.income / CASE c.country WHEN 'Colombia' THEN 4000.0 WHEN 'Argentina' THEN 350.0 ELSE 17.0 END"
print(con.execute(f"""
SELECT p.ptype, count(*) n, count(p.credit_limit) n_lim,
 corr(ln(p.credit_limit/{F}), ln({INC})) r_lim_inc, corr(p.credit_limit/{F}, c.credit_score) r_lim_cs,
 corr(ln(1+abs(p.bal)/{F}), ln({INC})) r_bal_inc, corr(p.rate, c.credit_score) r_rate_cs, corr(p.rate, ln({INC})) r_rate_inc,
 corr(p.dpd, c.credit_score) r_dpd_cs, corr(p.dpd, ln({INC})) r_dpd_inc,
 median(p.credit_limit/{F}) lim_med, min(p.credit_limit/{F}) lim_min, max(p.credit_limit/{F}) lim_max,
 min(p.rate) rmin, max(p.rate) rmax, min(p.bal/{F}) bmin, median(p.bal/{F}) bmed, max(p.bal/{F}) bmax
FROM pr p JOIN cu c USING (customer_id) GROUP BY 1 ORDER BY 2 DESC""").df().to_string(float_format=lambda x: f'{x:.3f}'))
print(con.execute(f"""
SELECT p.ptype, c.segment, count(*) n, median(p.credit_limit/{F}) lim_med, median(p.bal/{F}) bal_med, avg(p.rate) rate, avg(p.dpd) dpd,
  avg(CASE WHEN p.dpd>0 THEN 1.0 ELSE 0 END) dpd_pos, avg(CASE WHEN p.pstatus<>'Active' THEN 1.0 ELSE 0 END) nonactive
FROM pr p JOIN cu c USING (customer_id) WHERE p.ptype IN ('Tarjeta Crédito','Préstamo Personal','Cuenta Ahorro') GROUP BY 1,2 ORDER BY 1,2""").df().to_string(float_format=lambda x: f'{x:.3f}'))
