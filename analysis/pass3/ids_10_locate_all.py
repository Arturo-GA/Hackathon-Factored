# ids_10: posición en el flujo MT(seed=42) del primer ID de cada tabla y de sus primeras ~300 filas (orden de archivo)
# -> ¿cada tabla re-siembra con 42 (bucle separado) o se generan juntas (IDs intercalados)?
import sys, numpy as np, duckdb, collections
sys.path.insert(0, 'analysis/pass3')
from ids_rng import words, chars_per_word, locate
c = chars_per_word(words(3_000_000))
con = duckdb.connect(); con.execute("SET memory_limit='500MB'; SET threads=2")
specs = {'transactions':'transaction_id','call_center_interactions':'interaction_id','call_transcripts':'transcript_id',
         'complaints':'complaint_id','satisfaction_surveys':'survey_id','digital_events':'event_id','campaign_sends':'send_id'}
for t,col in specs.items():
    ids = [r[0] for r in con.execute(f"select {col} from read_parquet('data/bronze/{t}.parquet', file_row_number=true) where file_row_number<300 order by file_row_number").fetchall()]
    pos=[]; prev=0
    for v in ids:
        p = locate(c, v.split('-',1)[1], start=prev, maxpos=prev+100000); pos.append(p)
        if p>=0: prev=p+1
    pos=np.array(pos); ok=pos>=0; g=np.diff(pos[ok])
    print(f"{t}: ubicadas {ok.sum()}/{len(ids)} primera_pos={pos[0]} gap_med={np.median(g) if len(g) else None} min={g.min() if len(g) else None} max={g.max() if len(g) else None} top={collections.Counter(g).most_common(4)}")
# segundas columnas tipo ID generadas en la fila: session_id
ids = [r[0] for r in con.execute("select session_id from read_parquet('data/bronze/digital_events.parquet', file_row_number=true) where file_row_number<50 order by file_row_number").fetchall()]
print('session first', ids[:3], [locate(c, v.split('-',1)[1], 0, 200000) for v in ids[:10]])
