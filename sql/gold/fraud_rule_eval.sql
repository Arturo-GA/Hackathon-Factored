-- Evaluación de la regla de riesgo de fraude por tramo de fraud_score (sustenta la regla de escalamiento).
SELECT
    fraud_risk_tier,
    COUNT(*)                                                        AS transactions,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)                       AS frauds,
    AVG(CASE WHEN is_fraud THEN 1.0 ELSE 0 END)                     AS precision_fraud_rate,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) * 1.0
        / SUM(SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)) OVER ()    AS share_of_all_frauds,
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER ()                          AS share_of_transactions,
    AVG(CASE WHEN status = 'Approved' THEN 1.0 ELSE 0 END)          AS approved_rate
FROM silver.transactions
GROUP BY fraud_risk_tier
ORDER BY fraud_risk_tier
