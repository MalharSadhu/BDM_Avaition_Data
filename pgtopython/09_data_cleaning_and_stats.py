import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def execute_cleaning_and_stats():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("--- 1. IN-DATABASE DATA CLEANING (SQL via psycopg2) ---")
    cleaning_sql = """
    -- Clean baggage weights: impute missing/negative with baseline 18.0 kg
    UPDATE aviation.baggage
    SET weight_kg = COALESCE(weight_kg, 18.0)
    WHERE weight_kg IS NULL OR weight_kg < 0;

    -- Standardize terminal nomenclature in retail
    UPDATE aviation.retail
    SET terminal = UPPER(TRIM(terminal))
    WHERE terminal IS NOT NULL;

    -- Standardize satisfaction strings
    UPDATE aviation.passengers
    SET satisfaction = 'neutral or dissatisfied'
    WHERE satisfaction IS NULL;
    """
    cur.execute(cleaning_sql)
    conn.commit()
    print("Database cleaning rules applied successfully.")

    print("\n--- 2. PARAMETRIC & NON-PARAMETRIC STATISTICAL PROFILING ---")
    stats_query = """
    SELECT 
        'Baggage Weight (kg)' AS metric_dimension,
        COUNT(weight_kg) AS sample_size,
        ROUND(AVG(weight_kg)::numeric, 2) AS mean,
        ROUND(STDDEV(weight_kg)::numeric, 2) AS std_dev,
        ROUND(VARIANCE(weight_kg)::numeric, 2) AS sample_variance,
        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY weight_kg)::numeric, 2) AS median_p50,
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY weight_kg)::numeric, 2) AS p90_threshold,
        ROUND(
            (PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY weight_kg) - 
             PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY weight_kg))::numeric, 2
        ) AS interquartile_range_iqr
    FROM aviation.baggage
    UNION ALL
    SELECT 
        'Retail Transaction (EUR)',
        COUNT(amount_eur),
        ROUND(AVG(amount_eur)::numeric, 2),
        ROUND(STDDEV(amount_eur)::numeric, 2),
        ROUND(VARIANCE(amount_eur)::numeric, 2),
        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY amount_eur)::numeric, 2),
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY amount_eur)::numeric, 2),
        ROUND(
            (PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY amount_eur) - 
             PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY amount_eur))::numeric, 2
        )
    FROM aviation.retail;
    """
    df_stats = pd.read_sql_query(stats_query, conn)
    print(df_stats.to_string(index=False))

    print("\n--- 3. CORRELATION & REGRESSION (Native SQL) ---")
    reg_query = """
    WITH flight_metrics AS (
        SELECT 
            f.flight_api_id,
            COALESCE(AVG(p.departure_delay), 0) AS avg_delay_mins,
            COALESCE(SUM(r.amount_eur), 0) AS total_retail_spend
        FROM aviation.flights f
        LEFT JOIN aviation.passengers p ON p.departure_delay IS NOT NULL
        LEFT JOIN aviation.retail r ON f.flight_api_id = r.flight_api_id
        GROUP BY f.flight_api_id
        HAVING COUNT(r.transaction_id) > 0
    )
    SELECT 
        ROUND(CORR(total_retail_spend, avg_delay_mins)::numeric, 4) AS pearson_correlation,
        ROUND(REGR_R2(total_retail_spend, avg_delay_mins)::numeric, 4) AS r_squared,
        ROUND(REGR_SLOPE(total_retail_spend, avg_delay_mins)::numeric, 4) AS regression_slope,
        ROUND(REGR_INTERCEPT(total_retail_spend, avg_delay_mins)::numeric, 2) AS regression_intercept
    FROM flight_metrics;
    """
    df_reg = pd.read_sql_query(reg_query, conn)
    print(df_reg.to_string(index=False))

    print("\n--- 4. STATISTICAL OUTLIER Z-SCORE VIEW ---")
    cur.execute("""
    CREATE OR REPLACE VIEW aviation.vw_retail_statistical_anomalies AS
    WITH category_stats AS (
        SELECT 
            transaction_id,
            terminal,
            item_category,
            amount_eur,
            AVG(amount_eur) OVER (PARTITION BY terminal, item_category) AS mean_amt,
            STDDEV(amount_eur) OVER (PARTITION BY terminal, item_category) AS std_amt
        FROM aviation.retail
    )
    SELECT 
        transaction_id,
        terminal,
        item_category,
        amount_eur,
        ROUND(mean_amt::numeric, 2) AS benchmark_mean,
        ROUND(std_amt::numeric, 2) AS benchmark_std,
        ROUND(((amount_eur - mean_amt) / NULLIF(std_amt, 0))::numeric, 2) AS z_score,
        CASE 
            WHEN ABS((amount_eur - mean_amt) / NULLIF(std_amt, 0)) > 3.0 THEN 'CRITICAL_OUTLIER'
            WHEN ABS((amount_eur - mean_amt) / NULLIF(std_amt, 0)) > 2.0 THEN 'SUSPICIOUS_HIGH'
            ELSE 'NORMAL'
        END AS anomaly_classification
    FROM category_stats;
    """)
    conn.commit()
    print("Anomaly view deployed successfully.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    execute_cleaning_and_stats()