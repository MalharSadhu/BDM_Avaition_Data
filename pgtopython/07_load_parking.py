import os
import random
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

# 1. Environment configuration
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def generate_parking_records():
    if not DATABASE_URL:
        print("Error: DATABASE_URL missing from .env")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 2. Setup aviation.parking table
    print("Setting up aviation.parking table in Supabase...")
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS aviation;

        DROP TABLE IF EXISTS aviation.parking CASCADE;

        CREATE TABLE aviation.parking (
            ticket_id VARCHAR(50) PRIMARY KEY,
            passenger_id INT REFERENCES aviation.passengers(passenger_id) ON DELETE CASCADE,
            parking_zone VARCHAR(50),
            spot_number VARCHAR(20),
            vehicle_type VARCHAR(30),
            is_ev_charging BOOLEAN,
            entry_time TIMESTAMP,
            exit_time TIMESTAMP,
            duration_hours NUMERIC(6, 1),
            rate_per_hour_eur NUMERIC(6, 2),
            total_amount_eur NUMERIC(8, 2),
            payment_method VARCHAR(50),
            payment_status VARCHAR(30)
        );
    """)
    conn.commit()

    # 3. Fetch passengers from database to maintain relational integrity
    print("Fetching passenger IDs from aviation.passengers...")
    cur.execute("SELECT passenger_id FROM aviation.passengers ORDER BY passenger_id ASC;")
    passenger_ids = [r[0] for r in cur.fetchall()]

    if not passenger_ids:
        print("Error: No passengers found in aviation.passengers. Load passengers first!")
        cur.close()
        conn.close()
        return

    print(f"Found {len(passenger_ids)} passengers. Generating realistic Schiphol parking records...")

    # 4. Schiphol Parking Zones and Rate Tiers (EUR)
    zone_profiles = {
        "P1 Short Stop (0-48h)": {"rate": 6.50, "daily_max": 47.50, "prefix": "P1"},
        "P3 Long Term Sheltered": {"rate": 4.00, "daily_max": 24.50, "prefix": "P3S"},
        "P3 Long Term Open Lot": {"rate": 3.50, "daily_max": 21.00, "prefix": "P3O"},
        "P6 Valet Parking": {"rate": 8.00, "daily_max": 59.00, "prefix": "P6V"},
        "Privium Excellence VIP": {"rate": 12.00, "daily_max": 85.00, "prefix": "PRV"}
    }

    vehicle_types = ["Electric (EV)", "Compact", "SUV", "Sedan", "Hatchback"]
    payment_methods = ["iDEAL", "Credit Card", "Debit Card", "Apple Pay"]

    # Sample ~40% of passengers who used airport parking
    sampled_passengers = random.sample(passenger_ids, k=int(len(passenger_ids) * 0.40))

    base_reference_date = datetime(2024, 12, 1, 8, 0, 0)
    records = []

    for i, p_id in enumerate(sampled_passengers):
        ticket_id = f"AMS-PRK-{100000 + i}"
        zone_name = random.choice(list(zone_profiles.keys()))
        profile = zone_profiles[zone_name]

        # Parking duration between 2 hours and 120 hours (5 days)
        if "Short" in zone_name:
            duration_hrs = round(random.uniform(2.0, 36.0), 1)
        else:
            duration_hrs = round(random.uniform(24.0, 168.0), 1)

        # Timestamps
        days_offset = random.randint(0, 30)
        hours_offset = random.randint(0, 23)
        entry_time = base_reference_date + timedelta(days=days_offset, hours=hours_offset, minutes=random.randint(0, 59))
        exit_time = entry_time + timedelta(hours=duration_hrs)

        # Spot & Vehicle
        spot_number = f"{profile['prefix']}-{random.choice(['A','B','C','D'])}-{random.randint(101, 499)}"
        v_type = random.choice(vehicle_types)
        is_ev = True if v_type == "Electric (EV)" else (random.random() < 0.15)

        # Price calculation with daily caps
        days_full = int(duration_hrs // 24)
        rem_hours = duration_hrs % 24
        computed_price = (days_full * profile["daily_max"]) + min(rem_hours * profile["rate"], profile["daily_max"])
        total_amount = round(computed_price, 2)

        pm = random.choice(payment_methods)
        p_status = "Pre-booked Online" if random.random() < 0.65 else "Paid at Terminal"

        records.append((
            ticket_id,
            p_id,
            zone_name,
            spot_number,
            v_type,
            is_ev,
            entry_time,
            exit_time,
            duration_hrs,
            profile["rate"],
            total_amount,
            pm,
            p_status
        ))

    # 5. Insert parking records
    insert_sql = """
    INSERT INTO aviation.parking (
        ticket_id, passenger_id, parking_zone, spot_number,
        vehicle_type, is_ev_charging, entry_time, exit_time,
        duration_hours, rate_per_hour_eur, total_amount_eur,
        payment_method, payment_status
    ) VALUES %s
    ON CONFLICT (ticket_id) DO NOTHING;
    """

    print(f"Inserting {len(records)} synthesized parking records into Supabase...")
    execute_values(cur, insert_sql, records, page_size=1000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM aviation.parking;")
    total_count = cur.fetchone()[0]
    print(f"Success! aviation.parking now has {total_count} rows.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    generate_parking_records()