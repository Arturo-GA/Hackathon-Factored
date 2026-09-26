-- Perfil semanal: contactos promedio por día de semana y motivo, e índice vs el promedio del motivo.
-- (Las horas del día son planas por construcción; el día de semana es el único patrón real.)
WITH daily AS (
    SELECT process_date, weekday_num, category, COUNT(*) AS contacts
    FROM silver.call_center_interactions
    GROUP BY process_date, weekday_num, category
),
by_weekday AS (
    SELECT weekday_num, category, COUNT(*) AS days, AVG(contacts) AS avg_contacts_per_day
    FROM daily
    GROUP BY weekday_num, category
)
SELECT
    weekday_num,
    CASE weekday_num WHEN 1 THEN 'lunes' WHEN 2 THEN 'martes' WHEN 3 THEN 'miércoles' WHEN 4 THEN 'jueves'
                     WHEN 5 THEN 'viernes' WHEN 6 THEN 'sábado' ELSE 'domingo' END AS weekday_name,
    category,
    days,
    avg_contacts_per_day,
    avg_contacts_per_day / AVG(avg_contacts_per_day) OVER (PARTITION BY category) AS index_vs_category_mean
FROM by_weekday
ORDER BY weekday_num, category
