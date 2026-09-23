import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def run_window_functions():
    conn = psycopg2.connect(DATABASE_URL)
    
    query = """
    SELECT 
        f.schedule_date,
        f.airline_iata,
        f.flight_name,
        COUNT(b.bag_tag_number) AS flight_bag_count,
        COALESCE(SUM(b.excess_fee_eur), 0) AS baggage_penalty_eur,
        
        -- Window 1: Rank flight penalty within airline
        DENSE_RANK() OVER (
            PARTITION BY f.airline_iata 
            ORDER BY COALESCE(SUM(b.excess_fee_eur), 0) DESC
        ) AS carrier_penalty_rank,

        -- Window 2: Running total across schedule date
        SUM(COALESCE(SUM(b.excess_fee_eur), 0)) OVER (
            PARTITION BY f.schedule_date 
            ORDER BY f.flight_name
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_daily_penalty_total,

        -- Window 3: Lag analysis against prior flight in group
        LAG(COUNT(b.bag_tag_number), 1, 0) OVER (
            PARTITION BY f.airline_iata 
            ORDER BY f.flight_name
        ) AS prev_flight_bag_count

    FROM aviation.flights f
    LEFT JOIN aviation.baggage b ON f.flight_api_id = b.flight_api_id
    GROUP BY f.schedule_date, f.airline_iata, f.flight_name
    ORDER BY f.schedule_date DESC, baggage_penalty_eur DESC
    LIMIT 25;
    """
    df = pd.read_sql_query(query, conn)
    print("--- WINDOW FUNCTIONS: DENSE_RANK, RUNNING TOTAL, AND LAG ---")
    print(df.to_string(index=False))
    conn.close()

if __name__ == "__main__":
    run_window_functions()