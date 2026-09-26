-- Transacciones listas para la herramienta del agente: fecha contable, monto en USD, motivo del
-- rechazo en español y banderas que indican cuándo NO confiar en la explicación (derivar a humano).
-- SQL portable (se usa también para crear la vista en BigQuery).
SELECT
    transaction_id, customer_id, product_id, product_type, card_last4,
    process_date, ts, transaction_type, merchant_name, merchant_category,
    amount, currency, amount_usd, transaction_country, channel,
    status, response_code, response_description,
    CASE
        WHEN status = 'Approved' THEN 'La transacción fue aprobada.'
        WHEN status = 'Declined' AND response_code = '51' THEN 'La transacción fue rechazada por fondos insuficientes.'
        WHEN status = 'Declined' AND response_code = '54' THEN 'La transacción fue rechazada porque la tarjeta figuraba como vencida.'
        WHEN status = 'Declined' AND response_code = '14' THEN 'La transacción fue rechazada porque el número de tarjeta no fue reconocido.'
        WHEN status = 'Declined' AND response_code = '05' THEN 'La transacción fue rechazada: el banco emisor no la autorizó.'
        WHEN status = 'Declined' THEN 'La transacción fue rechazada; el motivo no está registrado.'
        WHEN status = 'Pending' THEN 'La transacción está pendiente de procesamiento.'
        WHEN status = 'Reversed' THEN 'La transacción fue revertida.'
    END AS status_message_es,
    fraud_risk_tier,
    (fraud_risk_tier = 'alto') AS requires_fraud_review,
    NOT (dq_code_semantics_inconsistent OR dq_decline_code_on_non_declined
         OR (status = 'Declined' AND dq_response_code_missing)) AS explanation_reliable,
    dq_before_product_open, dq_after_card_expiry, dq_customer_not_active
FROM silver.transactions
