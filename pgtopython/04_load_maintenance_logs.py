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
CSV_PATH = Path(__file__).resolve().parent.parent / "maintenance_logs.csv"

def load_maintenance_logs():
    if not DATABASE_URL:
        print("Error: DATABASE_URL missing from .env")
        return
    if not CSV_PATH.exists():
        print(f"Error: maintenance_logs.csv not found at {CSV_PATH}")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 2. Create aviation.maintenance_logs table if not exists
    print("Creating aviation.maintenance_logs table if needed...")
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS aviation;

        CREATE TABLE IF NOT EXISTS aviation.maintenance_logs (
            work_order_id VARCHAR(50) PRIMARY KEY,
            flight_api_id VARCHAR(64) REFERENCES aviation.flights(flight_api_id) ON DELETE CASCADE,
            aircraft_registration VARCHAR(30),
            maintenance_type VARCHAR(50),
            technician_id VARCHAR(50),
            logged_at TIMESTAMP,
            completed_at TIMESTAMP,
            severity_level INT,
            hangar_bay INT,
            defect_description VARCHAR(150),
            part_serviced VARCHAR(100),
            duration_hours NUMERIC(4, 1),
            station_code VARCHAR(50),
            is_aog BOOLEAN,
            caused_delay BOOLEAN
        );
    """)
    conn.commit()

    # 3. Fetch active Schiphol flights from database
    print("Fetching active Schiphol flights from database...")
    cur.execute("SELECT flight_api_id FROM aviation.flights WHERE flight_api_id IS NOT NULL;")
    schiphol_flight_ids = [r[0] for r in cur.fetchall()]

    if not schiphol_flight_ids:
        print("Error: No flights found in aviation.flights. Load Schiphol flights first!")
        cur.close()
        conn.close()
        return

    print(f"Found {len(schiphol_flight_ids)} Schiphol flights to link maintenance logs to.")

    # 4. Read Kaggle CSV and map to Schiphol flight IDs
    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, header=None, skiprows=1)

    records = []
    for i, row in df.iterrows():
        mapped_flight_id = schiphol_flight_ids[i % len(schiphol_flight_ids)]
        
        records.append((
            str(row[0])[:50],                                          # work_order_id
            mapped_flight_id,                                          # flight_api_id (Schiphol)
            str(row[1])[:30] if pd.notna(row[1]) else None,            # aircraft_registration
            str(row[3])[:50] if pd.notna(row[3]) else 'Inspection',   # maintenance_type
            str(row[4])[:50] if pd.notna(row[4]) else None,            # technician_id
            str(row[5]) if pd.notna(row[5]) else None,                 # logged_at
            str(row[6]) if pd.notna(row[6]) else None,                 # completed_at
            int(row[7]) if pd.notna(row[7]) else 1,                    # severity_level
            int(row[8]) if pd.notna(row[8]) else None,                 # hangar_bay
            str(row[9])[:150] if pd.notna(row[9]) else None,           # defect_description
            str(row[10])[:100] if pd.notna(row[10]) else None,        # part_serviced
            float(row[11]) if pd.notna(row[11]) else 1.0,              # duration_hours
            str(row[12])[:50] if pd.notna(row[12]) else None,          # station_code
            bool(row[13]) if pd.notna(row[13]) else False,             # is_aog
            bool(row[14]) if pd.notna(row[14]) else False              # caused_delay
        ))

    # 5. Insert mapped maintenance logs
    insert_sql = """
    INSERT INTO aviation.maintenance_logs (
        work_order_id, flight_api_id, aircraft_registration, maintenance_type,
        technician_id, logged_at, completed_at, severity_level, hangar_bay,
        defect_description, part_serviced, duration_hours, station_code,
        is_aog, caused_delay
    ) VALUES %s
    ON CONFLICT (work_order_id) DO NOTHING;
    """

    print(f"Inserting {len(records)} mapped maintenance records into Supabase...")
    execute_values(cur, insert_sql, records, page_size=1000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM aviation.maintenance_logs;")
    total_count = cur.fetchone()[0]
    print(f"Success! aviation.maintenance_logs now has {total_count} rows.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    load_maintenance_logs()