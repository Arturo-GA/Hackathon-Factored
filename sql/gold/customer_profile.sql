-- Perfil del cliente para las herramientas del agente y el handoff a humano.
-- Minimización de datos: sin documento en claro, email, teléfono ni dirección
-- (document_hash permite validar identidad en un servicio simulado).
-- Ventanas de 90 días respecto de SNAPSHOT_DATE (último día del dataset).
WITH prod AS (
    SELECT customer_id,
        COUNT(*) FILTER (WHERE product_status = 'Active')             AS active_products,
        COUNT(*) FILTER (WHERE is_card)                               AS cards,
        COUNT(*) FILTER (WHERE product_status = 'Blocked')            AS blocked_products,
        COUNT(*) FILTER (WHERE is_credit AND days_past_due >= 30)     AS credit_products_30dpd
    FROM silver.products GROUP BY customer_id
),
tx AS (
    SELECT customer_id,
        COUNT(*) FILTER (WHERE process_date > DATE '{{snapshot_date}}' - INTERVAL 90 DAY) AS tx_90d,
        COUNT(*) FILTER (WHERE status = 'Declined' AND process_date > DATE '{{snapshot_date}}' - INTERVAL 90 DAY) AS declined_90d,
        COUNT(*) FILTER (WHERE fraud_risk_tier = 'alto' AND process_date > DATE '{{snapshot_date}}' - INTERVAL 90 DAY) AS high_fraud_risk_90d,
        MAX(process_date)                                             AS last_tx_date
    FROM silver.transactions GROUP BY customer_id
),
cc AS (
    SELECT customer_id,
        COUNT(*)                                                      AS contacts_total,
        COUNT(*) FILTER (WHERE process_date > DATE '{{snapshot_date}}' - INTERVAL 90 DAY) AS contacts_90d,
        arg_max(category, ts)                                         AS last_contact_category,
        MAX(process_date)                                             AS last_contact_date,
        AVG(CASE WHEN resolved THEN 1.0 ELSE 0 END)                   AS fcr_rate
    FROM silver.call_center_interactions GROUP BY customer_id
),
cp AS (
    SELECT customer_id, COUNT(*) AS complaints_total, COUNT(*) FILTER (WHERE is_open) AS complaints_open
    FROM silver.complaints GROUP BY customer_id
),
sv AS (
    SELECT i.customer_id, AVG(s.score) FILTER (WHERE s.survey_type = 'CSAT') AS csat_avg
    FROM silver.satisfaction_surveys s
    JOIN silver.call_center_interactions i ON i.interaction_id = s.interaction_id
    GROUP BY i.customer_id
)
SELECT
    c.customer_id, c.first_name, c.document_hash, c.document_type, c.country, c.segment,
    c.customer_status, c.age, c.detected_accent, c.accepts_marketing,
    COALESCE(prod.active_products, 0)       AS active_products,
    COALESCE(prod.cards, 0)                 AS cards,
    COALESCE(prod.blocked_products, 0)      AS blocked_products,
    COALESCE(prod.credit_products_30dpd, 0) AS credit_products_30dpd,
    COALESCE(tx.tx_90d, 0)                  AS tx_90d,
    COALESCE(tx.declined_90d, 0)            AS declined_90d,
    COALESCE(tx.high_fraud_risk_90d, 0)     AS high_fraud_risk_90d,
    tx.last_tx_date,
    COALESCE(cc.contacts_total, 0)          AS contacts_total,
    COALESCE(cc.contacts_90d, 0)            AS contacts_90d,
    cc.last_contact_category, cc.last_contact_date, cc.fcr_rate,
    COALESCE(cp.complaints_total, 0)        AS complaints_total,
    COALESCE(cp.complaints_open, 0)         AS complaints_open,
    sv.csat_avg
FROM silver.customers c
LEFT JOIN prod ON prod.customer_id = c.customer_id
LEFT JOIN tx   ON tx.customer_id = c.customer_id
LEFT JOIN cc   ON cc.customer_id = c.customer_id
LEFT JOIN cp   ON cp.customer_id = c.customer_id
LEFT JOIN sv   ON sv.customer_id = c.customer_id
