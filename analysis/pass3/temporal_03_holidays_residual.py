"""H6: feriados por país y días anómalos. Esperado = media del mismo día de semana en el mismo país
en ventana ±28 días (excluyendo el día). z Poisson. Lista feriados MX/CO/AR y compara.
H7: ¿la semana se define por process_date o por ts::DATE? (nitidez del efecto fin de semana)."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

# H7
w = con.execute("""SELECT 'process_date' base, dayofweek(process_date) dw, count(*) n FROM tx GROUP BY 1,2
  UNION ALL SELECT 'ts_date', dayofweek(ts::DATE), count(*) FROM tx GROUP BY 1,2
  UNION ALL SELECT 'ts_minus6h', dayofweek(CAST(ts - INTERVAL 6 HOUR AS DATE)), count(*) FROM tx GROUP BY 1,2""").fetchdf()
p = w.pivot(index='dw', columns='base', values='n'); print((p/p.mean()).round(4))
# hora dentro del día local vs fin de semana: ¿el perfil horario (ts) cambia sáb vs lun?
print(con.execute("""SELECT (hour(ts - INTERVAL 6 HOUR)) h_local, avg((dayofweek(process_date) IN (0,6))::INT) share_weekend, count(*) n
  FROM tx GROUP BY 1 ORDER BY 1""").fetchdf().T.round(4).to_string())

d = con.execute("SELECT country, process_date d, count(*) n FROM tx WHERE country IN ('México','Colombia','Argentina') GROUP BY ALL").fetchdf()
d['d'] = pd.to_datetime(d.d)
res = []
for c, g in d.groupby('country'):
    s = g.set_index('d').n.reindex(pd.date_range('2023-06-17', '2026-06-17'), fill_value=0)
    for dt in s.index:
        win = s[(s.index >= dt - pd.Timedelta(days=28)) & (s.index <= dt + pd.Timedelta(days=28)) & (s.index.dayofweek == dt.dayofweek) & (s.index != dt)]
        e = win.mean(); res.append((c, dt, s[dt], e))
r = pd.DataFrame(res, columns=['country', 'd', 'n', 'exp']); r['ratio'] = r.n/r.exp; r['z'] = (r.n-r.exp)/np.sqrt(r.exp)
print("dispersión de z por país (Poisson => sd≈1.0x ~1.05 por error de la media):"); print(r.groupby('country').z.agg(['mean', 'std', 'min', 'max']).round(3))
print("días con |z|>4:", int((r.z.abs() > 4).sum()), "de", len(r)); print(r.loc[r.ratio.sub(1).abs().nlargest(6).index].to_string(index=False))

H = {
 'México': ['2023-09-16','2023-11-20','2023-12-12','2023-12-25','2024-01-01','2024-02-05','2024-03-18','2024-03-28','2024-03-29','2024-05-01','2024-09-16','2024-10-01','2024-11-18','2024-12-12','2024-12-25','2025-01-01','2025-02-03','2025-03-17','2025-04-17','2025-04-18','2025-05-01','2025-09-16','2025-11-17','2025-12-12','2025-12-25','2026-01-01','2026-02-02','2026-03-16','2026-04-02','2026-04-03','2026-05-01'],
 'Colombia': ['2023-06-19','2023-07-03','2023-07-20','2023-08-07','2023-08-21','2023-10-16','2023-11-06','2023-11-13','2023-12-08','2023-12-25','2024-01-01','2024-01-08','2024-03-25','2024-03-28','2024-03-29','2024-05-01','2024-05-13','2024-06-03','2024-06-10','2024-07-01','2024-07-20','2024-08-07','2024-08-19','2024-10-14','2024-11-04','2024-11-11','2024-12-08','2024-12-25','2025-01-01','2025-01-06','2025-03-24','2025-04-17','2025-04-18','2025-05-01','2025-06-02','2025-06-23','2025-06-30','2025-07-20','2025-08-07','2025-08-18','2025-10-13','2025-11-03','2025-11-17','2025-12-08','2025-12-25','2026-01-01','2026-01-12','2026-03-23','2026-04-02','2026-04-03','2026-05-01','2026-05-18','2026-06-08','2026-06-15'],
 'Argentina': ['2023-06-17','2023-06-20','2023-07-09','2023-08-21','2023-10-13','2023-10-16','2023-11-20','2023-12-08','2023-12-25','2024-01-01','2024-02-12','2024-02-13','2024-03-24','2024-03-28','2024-03-29','2024-04-02','2024-05-01','2024-05-25','2024-06-17','2024-06-20','2024-06-21','2024-07-09','2024-08-17','2024-10-11','2024-11-18','2024-12-08','2024-12-25','2025-01-01','2025-03-03','2025-03-04','2025-03-24','2025-04-02','2025-04-18','2025-05-01','2025-05-25','2025-06-16','2025-06-20','2025-07-09','2025-08-15','2025-11-21','2025-11-24','2025-12-08','2025-12-25','2026-01-01','2026-02-16','2026-02-17','2026-03-24','2026-04-02','2026-04-03','2026-05-01','2026-05-25','2026-06-15'],
}
for c, hl in H.items():
    rr = r[r.country == c]; mask = rr.d.isin(pd.to_datetime(hl))
    h = rr[mask]; nh = rr[~mask]
    # comparar solo días de semana (lun-vie) para no mezclar composición
    hw = h[h.d.dt.dayofweek < 5]; nhw = nh[nh.d.dt.dayofweek < 5]
    print(f"{c}: feriados={mask.sum()} (lun-vie {len(hw)}) ratio obs/esp feriados lun-vie={hw.n.sum()/hw.exp.sum():.4f}  no feriados={nhw.n.sum()/nhw.exp.sum():.4f}  z medio feriados={hw.z.mean():.2f}")
# Navidad / Año nuevo / 24 y 31 dic todos los países
for md in ['12-24', '12-25', '12-31', '01-01', '05-01', '11-01', '11-02', '02-14', '05-10']:
    rr = r[r.d.dt.strftime('%m-%d') == md]
    print(md, "ratio obs/esp (3 países):", round(rr.n.sum()/rr.exp.sum(), 4), "n días", len(rr))
