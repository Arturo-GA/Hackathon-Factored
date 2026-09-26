"""Construye data/analysis.duckdb: las 13 tablas bronze con tipos correctos.

Bronze guarda todo como STRING; aquí se castea una sola vez (TRY_CAST, así un valor
inválido queda NULL en vez de romper) para que los análisis consulten tablas tipadas
y livianas. Varios procesos pueden abrir el archivo en modo read_only a la vez.

Uso: python analysis/build_analysis_db.py
"""
import os

import duckdb

B = "data/bronze"
DB = "data/analysis.duckdb"

TABLES = {
    "tx": f"""SELECT transaction_id, TRY_CAST(transaction_date AS TIMESTAMP) ts, TRY_CAST(process_date AS DATE) process_date,
        product_id, customer_id, transaction_type ttype, transaction_category tcat, TRY_CAST(amount AS DOUBLE) amount,
        currency, TRY_CAST(amount_usd AS DOUBLE) amount_usd, channel, branch_id, merchant_name, merchant_category mcat,
        transaction_country country_raw,
        CASE WHEN transaction_country='Mexico' THEN 'México' ELSE transaction_country END country,
        transaction_city city, transaction_status status, response_code code, is_fraud='True' fraud,
        TRY_CAST(fraud_score AS DOUBLE) fscore, TRY_CAST(latitude AS DOUBLE) lat, TRY_CAST(longitude AS DOUBLE) lon
      FROM '{B}/transactions.parquet'""",
    "cc": f"""SELECT interaction_id, TRY_CAST(interaction_date AS TIMESTAMP) ts, TRY_CAST(process_date AS DATE) process_date,
        customer_id, agent_id, interaction_type itype, channel, contact_reason, reason_category cat,
        TRY_CAST(duration_seconds AS DOUBLE) dur, TRY_CAST(wait_time_seconds AS DOUBLE) wait,
        was_resolved='True' resolved, requires_followup='True' followup, detected_sentiment sent,
        TRY_CAST(sentiment_score AS DOUBLE) sent_score, customer_detected_accent c_acc, agent_used_accent a_acc,
        was_escalated='True' escalated, mentioned_products, has_transcript='True' has_transcript, has_recording='True' has_recording
      FROM '{B}/call_center_interactions.parquet'""",
    "tr": f"""SELECT transcript_id, interaction_id, TRY_CAST(process_date AS DATE) process_date, customer_id, agent_id,
        full_text, customer_text, agent_text, detected_language, detected_accent, TRY_CAST(accent_confidence AS DOUBLE) accent_conf,
        detected_keywords, mentioned_entities, detected_intents, main_topics, transcription_model, audio_quality,
        TRY_CAST(duration_seconds AS DOUBLE) dur
      FROM '{B}/call_transcripts.parquet'""",
    "cu": f"""SELECT customer_id, document_number, document_type, first_name, last_name, TRY_CAST(date_of_birth AS DATE) dob,
        gender, email, mobile_phone, landline_phone, address, city, state, country, postal_code, detected_accent, segment,
        TRY_CAST(credit_score AS DOUBLE) credit_score, TRY_CAST(estimated_monthly_income AS DOUBLE) income, occupation,
        marital_status, education_level, TRY_CAST(registration_date AS TIMESTAMP) registration_date,
        registration_branch_id, customer_status cstatus, TRY_CAST(last_updated AS TIMESTAMP) last_updated,
        accepts_marketing='True' mkt
      FROM '{B}/customers.parquet'""",
    "pr": f"""SELECT product_id, customer_id, product_type ptype, product_number, currency, TRY_CAST(current_balance AS DOUBLE) bal,
        TRY_CAST(credit_limit AS DOUBLE) credit_limit, TRY_CAST(interest_rate AS DOUBLE) rate, TRY_CAST(opening_date AS DATE) opened,
        TRY_CAST(expiration_date AS DATE) expires, opening_branch_id, product_status pstatus, opening_channel,
        has_linked_app='True' app, TRY_CAST(days_past_due AS DOUBLE) dpd, TRY_CAST(last_transaction_date AS TIMESTAMP) last_tx,
        TRY_CAST(last_updated AS TIMESTAMP) last_updated
      FROM '{B}/products.parquet'""",
    "cp": f"""SELECT complaint_id, TRY_CAST(creation_date AS TIMESTAMP) ts, TRY_CAST(process_date AS DATE) process_date,
        customer_id, case_type, category, subcategory, reception_channel rchan, affected_product_id, related_branch_id,
        origin_interaction_id, description, TRY_CAST(claimed_amount AS DOUBLE) claimed, currency, priority, status,
        assigned_agent_id, TRY_CAST(assignment_date AS TIMESTAMP) assigned_at, TRY_CAST(first_response_date AS TIMESTAMP) first_resp_at,
        TRY_CAST(resolution_date AS TIMESTAMP) resolved_at, TRY_CAST(closing_date AS TIMESTAMP) closed_at,
        sla_breached='True' sla, TRY_CAST(resolution_days AS DOUBLE) rdays, resolution,
        TRY_CAST(compensation_granted AS DOUBLE) compensation, TRY_CAST(resolution_satisfaction AS DOUBLE) res_sat,
        is_repeat_complainer='True' repeat
      FROM '{B}/complaints.parquet'""",
    "sv": f"""SELECT survey_id, TRY_CAST(survey_date AS TIMESTAMP) ts, TRY_CAST(process_date AS DATE) process_date, interaction_id,
        customer_id, agent_id, survey_type, send_channel, TRY_CAST(main_score AS DOUBLE) score, nps_category,
        question_1_text q1_text, TRY_CAST(question_1_response AS DOUBLE) q1, question_2_text q2_text,
        TRY_CAST(question_2_response AS DOUBLE) q2, question_3_text q3_text, TRY_CAST(question_3_response AS DOUBLE) q3,
        open_comments, comment_sentiment, TRY_CAST(response_time_hours AS DOUBLE) resp_hours,
        TRY_CAST(campaign_response_rate AS DOUBLE) campaign_response_rate
      FROM '{B}/satisfaction_surveys.parquet'""",
    "ag": f"""SELECT agent_id, employee_code, first_name, last_name, email, phone, native_accent, country_of_origin,
        assigned_branch_id, agent_type, experience_level, languages, specialty, TRY_CAST(hire_date AS DATE) hire_date,
        TRY_CAST(avg_csat AS DOUBLE) avg_csat, TRY_CAST(total_monthly_interactions AS DOUBLE) monthly_interactions,
        agent_status, work_shift
      FROM '{B}/service_agents.parquet'""",
    "br": f"""SELECT branch_id, branch_code, branch_name, branch_type, address, city, state, country, postal_code,
        geographic_zone, phone, email, opening_time, closing_time, has_atms='True' has_atms, TRY_CAST(atm_count AS INT) atm_count,
        TRY_CAST(latitude AS DOUBLE) lat, TRY_CAST(longitude AS DOUBLE) lon, TRY_CAST(branch_opening_date AS DATE) opened,
        branch_status
      FROM '{B}/branches.parquet'""",
    "de": f"""SELECT event_id, TRY_CAST(event_date AS TIMESTAMP) ts, customer_id, session_id, event_type, event_category,
        channel, platform, browser, app_version, page_url, page_title, action, element_id, product_id,
        TRY_CAST(event_value AS DOUBLE) event_value, TRY_CAST(duration_seconds AS DOUBLE) dur, ip_address, ip_country,
        ip_city, is_mobile='True' is_mobile, referrer, utm_source, utm_medium, utm_campaign
      FROM '{B}/digital_events.parquet'""",
    "cs": f"""SELECT send_id, TRY_CAST(send_date AS TIMESTAMP) ts, campaign_id, customer_id, send_channel, template_used,
        subject, send_status, was_delivered='True' delivered, was_opened='True' opened, TRY_CAST(open_date AS TIMESTAMP) open_ts,
        was_clicked='True' clicked, had_conversion='True' conv, TRY_CAST(conversion_date AS TIMESTAMP) conv_ts,
        TRY_CAST(conversion_value AS DOUBLE) conv_value, failure_reason, TRY_CAST(send_cost AS DOUBLE) send_cost
      FROM '{B}/campaign_sends.parquet'""",
    "mc": f"""SELECT campaign_id, campaign_name, description, campaign_type, campaign_objective objective, promoted_product,
        target_segment, target_country, TRY_CAST(start_date AS DATE) start_date, TRY_CAST(end_date AS DATE) end_date,
        TRY_CAST(budget AS DOUBLE) budget, campaign_status, TRY_CAST(expected_conversion_rate AS DOUBLE) expected_cr
      FROM '{B}/marketing_campaigns.parquet'""",
    "fx": f"""SELECT TRY_CAST(date AS DATE) date, source_currency src, target_currency dst, TRY_CAST(exchange_rate AS DOUBLE) rate,
        TRY_CAST(buy_rate AS DOUBLE) buy, TRY_CAST(sell_rate AS DOUBLE) sell, source
      FROM '{B}/daily_exchange_rates.parquet'""",
}


def main():
    os.makedirs("data/duckdb_tmp", exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    con = duckdb.connect(DB)
    con.execute("SET memory_limit='3GB'; SET threads=6; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
    for name, sql in TABLES.items():
        con.execute(f"CREATE TABLE {name} AS {sql}")
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"{name:<3} {n:>12,} filas", flush=True)
    con.execute("CHECKPOINT")
    con.close()
    print(f"Listo: {DB} ({os.path.getsize(DB)/1e9:.2f} GB)")


if __name__ == "__main__":
    main()
