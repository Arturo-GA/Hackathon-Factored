-- Tarjetas del cliente para la herramienta "estado de mi tarjeta" (se identifican por los últimos 4 dígitos).
WITH tx AS (
    SELECT product_id,
        MAX(process_date)                                                                   AS last_tx_date,
        COUNT(*) FILTER (WHERE process_date > DATE '{{snapshot_date}}' - INTERVAL 90 DAY)   AS tx_90d,
        COUNT(*) FILTER (WHERE status = 'Declined'
                         AND process_date > DATE '{{snapshot_date}}' - INTERVAL 90 DAY)     AS declined_90d
    FROM silver.transactions GROUP BY product_id
)
SELECT
    p.product_id, p.customer_id, p.product_type, p.card_last4, p.product_status,
    p.opening_date, p.expiration_date, p.is_expired, p.dq_expired_but_active,
    p.currency, p.balance, p.credit_limit, p.credit_utilization, p.days_past_due, p.has_linked_app,
    tx.last_tx_date,
    COALESCE(tx.tx_90d, 0)       AS tx_90d,
    COALESCE(tx.declined_90d, 0) AS declined_90d
FROM silver.products p
LEFT JOIN tx ON tx.product_id = p.product_id
WHERE p.is_card
