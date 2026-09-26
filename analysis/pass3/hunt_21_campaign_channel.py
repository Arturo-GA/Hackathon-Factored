"""hunt_21: la tasa de apertura por cliente (R2=0.15 en hunt_04) la explica el mix de canal de envio. Tasas por canal y por consentimiento."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='300MB'; SET threads=2")
print(con.execute("""SELECT send_channel, count(*) n, avg(CASE WHEN delivered THEN 1.0 ELSE 0 END) deliv, avg(CASE WHEN opened THEN 1.0 ELSE 0 END) open,
  avg(CASE WHEN clicked THEN 1.0 ELSE 0 END) click, avg(CASE WHEN conv THEN 1.0 ELSE 0 END) conv,
  avg(CASE WHEN opened THEN 1.0 ELSE 0 END) FILTER (WHERE delivered) open_given_deliv FROM cs GROUP BY 1 ORDER BY open DESC""").df().round(4).to_string())
print(con.execute("""SELECT c.mkt, c.segment, count(*) n, avg(CASE WHEN s.opened THEN 1.0 ELSE 0 END) open, avg(CASE WHEN s.conv THEN 1.0 ELSE 0 END) conv
  FROM cs s JOIN cu c USING (customer_id) GROUP BY 1,2 ORDER BY 1,2""").df().round(4).to_string())
