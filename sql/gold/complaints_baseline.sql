-- Baseline de reclamos (PQR): volumen, SLA, tiempos y compensaciones por tipo, prioridad y canal.
SELECT
    category, subcategory, case_type, priority, reception_channel,
    COUNT(*)                                            AS complaints,
    AVG(CASE WHEN sla_breached THEN 1.0 ELSE 0 END)     AS sla_breach_rate,
    median(resolution_days)                             AS median_resolution_days,
    AVG(resolution_days)                                AS avg_resolution_days,
    AVG(CASE WHEN is_open THEN 1.0 ELSE 0 END)          AS open_rate,
    AVG(CASE WHEN is_repeat_complainer THEN 1.0 ELSE 0 END) AS repeat_complainer_rate,
    COUNT(compensation_granted)                         AS compensations,
    AVG(compensation_granted)                           AS avg_compensation
FROM silver.complaints
GROUP BY ALL
