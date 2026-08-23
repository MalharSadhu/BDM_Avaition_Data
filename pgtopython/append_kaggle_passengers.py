import os
import psycopg2
import pandas as pd
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

# 1. Load .env
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
CSV_PATH = Path(__file__).resolve().parent.parent / "passengers.csv"

def append_records():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return
    if not CSV_PATH.exists():
        print(f"passengers.csv not found at: {CSV_PATH}")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get max current passenger_id so new IDs start right after
    cur.execute("SELECT COALESCE(MAX(passenger_id), 0) FROM aviation.passengers;")
    start_id = cur.fetchone()[0] + 1
    print(f"Existing highest ID is {start_id - 1}. Starting new IDs from {start_id}...")

    # Read CSV
    df = pd.read_csv(CSV_PATH, header=None, skiprows=1)
    print(f"Read {len(df)} rows from passengers.csv")

    gender_map = {'F': 'Female', 'M': 'Male'}
    records = []

    for i, row in df.iterrows():
        p_id = start_id + i
        gender = gender_map.get(str(row[7]).strip(), str(row[7]))
        age = int(row[26]) if pd.notna(row[26]) else 30
        cust_type = "Returning" if bool(row[24]) else "First-time"
        trav_type = str(row[9]) if pd.notna(row[9]) else "Business"
        trav_class = str(row[25]) if pd.notna(row[25]) else "Economy"
        bag_rating = min(5, max(1, int(int(row[14]) / 6))) if pd.notna(row[14]) else 3
        satisfaction = "Satisfied" if bool(row[24]) else "Neutral or Dissatisfied"

        records.append((
            p_id, gender, age, cust_type,
            trav_type, trav_class, bag_rating, satisfaction
        ))

    insert_sql = """
    INSERT INTO aviation.passengers (
        passenger_id, gender, age, customer_type,
        travel_type, travel_class, baggage_handling, satisfaction
    ) VALUES %s
    ON CONFLICT (passenger_id) DO NOTHING;
    """

    print("Appending rows into Supabase...")
    execute_values(cur, insert_sql, records, page_size=1000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM aviation.passengers;")
    print(f"Total rows now in aviation.passengers: {cur.fetchone()[0]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    append_records()