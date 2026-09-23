import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def setup_views():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Deploying Standard View (aviation.vw_live_retail_audit)...")
    cur.execute("""
    CREATE OR REPLACE VIEW aviation.vw_live_retail_audit AS
    SELECT 
        r.transaction_id,
        r.transacted_at,
        r.terminal,
        r.item_category,
        r.amount_eur,
        f.flight_name,
        f.airline_iata,
        f.direction,
        f.flight_status,
        CASE 
            WHEN r.amount_eur >= 100 THEN 'Premium / Duty-Free High-Tier'
            WHEN r.amount_eur >= 30  THEN 'Standard Dining / Retail'
            ELSE 'Grab & Go Concession'
        END AS concession_bracket
    FROM aviation.retail r
    JOIN aviation.flights f ON r.flight_api_id = f.flight_api_id;
    """)

    print("Deploying 5-table Materialized View (aviation.mv_daily_operational_summary)...")
    cur.execute("""
    DROP MATERIALIZED VIEW IF EXISTS aviation.mv_daily_operational_summary CASCADE;

    CREATE MATERIALIZED VIEW aviation.mv_daily_operational_summary AS
    SELECT 
        f.schedule_date,
        COUNT(DISTINCT f.flight_api_id) AS total_flights,
        COALESCE(SUM(b.excess_fee_eur), 0) AS total_baggage_penalty_eur,
        COALESCE(SUM(r.amount_eur), 0) AS total_retail_spend_eur,
        COALESCE(SUM(p.total_amount_eur), 0) AS total_parking_intake_eur
    FROM aviation.flights f
    LEFT JOIN aviation.baggage b ON f.flight_api_id = b.flight_api_id
    LEFT JOIN aviation.retail r ON f.flight_api_id = r.flight_api_id
    LEFT JOIN aviation.parking p ON p.entry_time::DATE = f.schedule_date
    GROUP BY f.schedule_date
    WITH DATA;

    CREATE UNIQUE INDEX idx_mv_daily_ops_date 
    ON aviation.mv_daily_operational_summary (schedule_date);
    """)

    conn.commit()
    print("Views created and indexed successfully.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    setup_views()