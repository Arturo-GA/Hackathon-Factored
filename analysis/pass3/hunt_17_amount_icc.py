"""hunt_17: heterogeneidad por cliente/producto en montos, canal, hora, comercio y pais (ICC / exceso de varianza entre clientes).
Si ICC~0 los habitos por cliente no existen: 'monto inusual para este cliente' no es detectable."""
import duckdb
import numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
USD = "(amount / CASE currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END)"
for unit in ['customer_id', 'product_id']:
    r = con.execute(f"""WITH x AS (SELECT {unit} u, ttype, ln({USD}) y FROM tx WHERE {USD} > 0),
      g AS (SELECT ttype, u, count(*) n, avg(y) m, var_samp(y) v FROM x GROUP BY 1,2),
      t AS (SELECT ttype, avg(y) gm, var_samp(y) gv FROM x GROUP BY 1)
      SELECT g.ttype, sum(g.n) n, t.gv total_var, avg(g.v) FILTER (WHERE g.n>=3) within_var,
        -- varianza de medias de grupo vs esperada gv/n (exceso = varianza entre unidades)
        avg((g.m - t.gm)^2 - t.gv / g.n) FILTER (WHERE g.n>=3) between_var_excess
      FROM g JOIN t USING (ttype) GROUP BY g.ttype, t.gv ORDER BY 1""").df()
    r['ICC'] = r.between_var_excess / r.total_var
    print(unit); print(r.round(4).to_string(index=False))
# preferencia de canal/hora/comercio por cliente: chi2 de independencia cliente x categoria via exceso de dispersion en shares
for col in ['channel', 'merchant_name', 'hour(ts)', 'country', 'tcat', 'ttype']:
    r = con.execute(f"""WITH x AS (SELECT customer_id u, CAST({col} AS VARCHAR) k FROM tx WHERE {col} IS NOT NULL),
      nk AS (SELECT k, count(*)::DOUBLE / (SELECT count(*) FROM x) p FROM x GROUP BY 1),
      nu AS (SELECT u, count(*) n FROM x GROUP BY 1),
      c AS (SELECT u, k, count(*) o FROM x GROUP BY 1,2)
      SELECT sum((coalesce(c.o,0) - nu.n*nk.p)^2 / (nu.n*nk.p)) chi2, (SELECT count(*) FROM nu) nuu, (SELECT count(*) FROM nk) nkk
      FROM nu CROSS JOIN nk LEFT JOIN c ON c.u = nu.u AND c.k = nk.k""").fetchone()
    chi2, nu, nk = r
    dof = (nu - 1) * (nk - 1)
    print(f'{col}: chi2/dof = {chi2/dof:.4f} (1.0 = sin preferencia por cliente), unidades={nu}, categorias={nk}')
