-- Demanda diaria del call center por país, canal y motivo (fecha contable).
-- Base para patrones de demanda, capacidad y el baseline del reto.
SELECT
    i.process_date                               AS contact_date,
    i.weekday_num,
    c.country,
    i.channel,
    i.category,
    COUNT(*)                                     AS contacts,
    SUM(CASE WHEN i.resolved THEN 1 ELSE 0 END)  AS resolved,
    SUM(CASE WHEN i.escalated THEN 1 ELSE 0 END) AS escalated,
    SUM(CASE WHEN i.requires_followup THEN 1 ELSE 0 END) AS requires_followup,
    AVG(i.duration_s)                            AS avg_duration_s,
    AVG(i.wait_s)                                AS avg_wait_s
FROM silver.call_center_interactions i
LEFT JOIN silver.customers c ON c.customer_id = i.customer_id
GROUP BY ALL
