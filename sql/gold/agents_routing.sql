-- Agentes para el enrutamiento del handoff (idioma, especialidad, disponibilidad).
-- Solo los agentes Active atienden contactos en los datos.
SELECT
    agent_id, is_active, agent_status, agent_type, specialty,
    speaks_portuguese, speaks_english, experience_level,
    country_of_origin, native_accent, work_shift, avg_csat
FROM silver.service_agents
