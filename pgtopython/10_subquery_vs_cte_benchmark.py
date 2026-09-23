import os
import psycopg2
import time
import warnings
import pandas as pd
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def compare_subquery_vs_cte():
    conn = psycopg2.connect(DATABASE_URL)

    # ----------------------------------------------------
    # APPROACH A: NESTED CORRELATED SUBQUERY
    # ----------------------------------------------------
    subquery_sql = """
    SELECT 
        f.flight_api_id,
        f.airline_iata,
        f.schedule_date,
        (SELECT COUNT(*) FROM aviation.baggage b WHERE b.flight_api_id = f.flight_api_id) AS flight_bag_count
    FROM aviation.flights f
    WHERE f.airline_iata IS NOT NULL
      AND (SELECT COUNT(*) FROM aviation.baggage b WHERE b.flight_api_id = f.flight_api_id) >= (
        SELECT COALESCE(AVG(bag_count), 0)
        FROM (
            SELECT COUNT(b2.bag_tag_number) AS bag_count
            FROM aviation.flights f2
            JOIN aviation.baggage b2 ON f2.flight_api_id = b2.flight_api_id
            WHERE f2.airline_iata = f.airline_iata
            GROUP BY f2.flight_api_id
        ) sub_airline_avg
    )
    AND f.schedule_date IN (
        SELECT DISTINCT recorded_at::DATE 
        FROM aviation.weather 
        WHERE wind_speed_kmh >= (SELECT AVG(wind_speed_kmh) FROM aviation.weather)
    );
    """

    # ----------------------------------------------------
    # APPROACH B: MODULAR COMMON TABLE EXPRESSIONS (CTE)
    # ----------------------------------------------------
    cte_sql = """
    WITH adverse_weather_days AS (
        SELECT DISTINCT recorded_at::DATE AS weather_date
        FROM aviation.weather
        WHERE wind_speed_kmh >= (SELECT AVG(wind_speed_kmh) FROM aviation.weather)
    ),
    flight_baggage_totals AS (
        SELECT 
            flight_api_id, 
            COUNT(bag_tag_number) AS total_bags
        FROM aviation.baggage
        GROUP BY flight_api_id
    ),
    airline_benchmarks AS (
        SELECT 
            f.airline_iata,
            COALESCE(AVG(fbt.total_bags), 0) AS avg_carrier_bags
        FROM aviation.flights f
        JOIN flight_baggage_totals fbt ON f.flight_api_id = fbt.flight_api_id
        WHERE f.airline_iata IS NOT NULL
        GROUP BY f.airline_iata
    )
    SELECT 
        f.flight_api_id,
        f.airline_iata,
        f.schedule_date,
        fbt.total_bags,
        ROUND(ab.avg_carrier_bags, 2) AS benchmark_bags
    FROM aviation.flights f
    JOIN adverse_weather_days aw ON f.schedule_date = aw.weather_date
    JOIN flight_baggage_totals fbt ON f.flight_api_id = fbt.flight_api_id
    JOIN airline_benchmarks ab ON f.airline_iata = ab.airline_iata
    WHERE fbt.total_bags >= ab.avg_carrier_bags;
    """

    print("Running Approach A (Nested Subquery)...")
    t0 = time.perf_counter()
    df_sub = pd.read_sql_query(subquery_sql, conn)
    sub_duration = (time.perf_counter() - t0) * 1000

    print("Running Approach B (Common Table Expressions)...")
    t1 = time.perf_counter()
    df_cte = pd.read_sql_query(cte_sql, conn)
    cte_duration = (time.perf_counter() - t1) * 1000

    print("\n--- BENCHMARK RESULTS ---")
    print(f"Subquery Result Count: {len(df_sub)} rows | Exec Time: {sub_duration:.2f} ms")
    print(f"CTE Result Count:      {len(df_cte)} rows | Exec Time: {cte_duration:.2f} ms")
    
    if len(df_cte) > 0:
        print("\nSample Output (CTE):")
        print(df_cte.head(5).to_string(index=False))

    conn.close()

if __name__ == "__main__":
    compare_subquery_vs_cte()