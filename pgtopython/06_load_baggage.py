import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

# 1. Environment & Path Setup
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
CSV_PATH = Path(__file__).resolve().parent.parent / "baggage.csv"

def load_baggage():
    if not DATABASE_URL:
        print("Error: DATABASE_URL missing from .env")
        return
    if not CSV_PATH.exists():
        print(f"Error: baggage.csv not found at {CSV_PATH}")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 2. Setup aviation.baggage table
    print("Setting up aviation.baggage table in Supabase...")
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS aviation;

        DROP TABLE IF EXISTS aviation.baggage CASCADE;

        CREATE TABLE aviation.baggage (
            bag_tag_number VARCHAR(50) PRIMARY KEY,
            flight_api_id VARCHAR(64) REFERENCES aviation.flights(flight_api_id) ON DELETE CASCADE,
            booking_reference VARCHAR(30),
            passenger_reference VARCHAR(50),
            weight_kg NUMERIC(5, 2),
            dimensions VARCHAR(30),
            baggage_type VARCHAR(30),
            drop_counter VARCHAR(20),
            checked_in_at TIMESTAMP,
            loaded_at TIMESTAMP,
            carousel_number INT,
            handling_status VARCHAR(50),
            is_overweight BOOLEAN,
            excess_fee_eur NUMERIC(6, 2),
            handling_location VARCHAR(50),
            last_scanned_at TIMESTAMP,
            is_mishandled BOOLEAN
        );
    """)
    conn.commit()

    # 3. Fetch active Schiphol flights
    print("Fetching active Schiphol flights from database...")
    cur.execute("SELECT flight_api_id FROM aviation.flights WHERE flight_api_id IS NOT NULL;")
    schiphol_flight_ids = [r[0] for r in cur.fetchall()]

    if not schiphol_flight_ids:
        print("Error: No flights found in aviation.flights. Load Schiphol flights first!")
        cur.close()
        conn.close()
        return

    print(f"Found {len(schiphol_flight_ids)} Schiphol flights to link baggage records to.")

    # 4. Read Kaggle Baggage CSV and map columns
    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, header=None, skiprows=1)

    records = []
    for i, row in df.iterrows():
        mapped_flight_id = schiphol_flight_ids[i % len(schiphol_flight_ids)]
        weight = round(float(row[4]), 2) if pd.notna(row[4]) else 15.00
        
        # Calculate excess fee in EUR if overweight (> 23 kg)
        is_overweight = bool(row[12]) if pd.notna(row[12]) else (weight > 23.0)
        excess_fee = 40.00 if is_overweight else 0.00

        records.append((
            str(row[0])[:50],                                          # bag_tag_number
            mapped_flight_id,                                          # flight_api_id (Schiphol)
            str(row[1])[:30] if pd.notna(row[1]) else None,            # booking_reference
            str(row[3])[:50] if pd.notna(row[3]) else None,            # passenger_reference
            weight,                                                    # weight_kg
            str(row[5])[:30] if pd.notna(row[5]) else '55x40x23',     # dimensions
            str(row[6])[:30] if pd.notna(row[6]) else 'Check-in',      # baggage_type
            str(row[7])[:20] if pd.notna(row[7]) else 'C12',           # drop_counter
            str(row[8]) if pd.notna(row[8]) else None,                 # checked_in_at
            str(row[9]) if pd.notna(row[9]) else None,                 # loaded_at
            int(row[10]) if pd.notna(row[10]) else 1,                  # carousel_number
            str(row[11])[:50] if pd.notna(row[11]) else 'Loaded',      # handling_status
            is_overweight,                                             # is_overweight
            excess_fee,                                                # excess_fee_eur
            str(row[14])[:50] if pd.notna(row[14]) else 'Ramp',        # handling_location
            str(row[15]) if pd.notna(row[15]) else None,               # last_scanned_at
            bool(row[16]) if pd.notna(row[16]) else False              # is_mishandled
        ))

    # 5. Insert mapped baggage records
    insert_sql = """
    INSERT INTO aviation.baggage (
        bag_tag_number, flight_api_id, booking_reference, passenger_reference,
        weight_kg, dimensions, baggage_type, drop_counter,
        checked_in_at, loaded_at, carousel_number, handling_status,
        is_overweight, excess_fee_eur, handling_location,
        last_scanned_at, is_mishandled
    ) VALUES %s
    ON CONFLICT (bag_tag_number) DO NOTHING;
    """

    print(f"Inserting {len(records)} mapped baggage records into Supabase...")
    execute_values(cur, insert_sql, records, page_size=1000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM aviation.baggage;")
    total_count = cur.fetchone()[0]
    print(f"Success! aviation.baggage now has {total_count} rows.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    load_baggage()