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
CSV_PATH = Path(__file__).resolve().parent.parent / "retail_transactions.csv"

# Conversion Rate from INR to EUR (approx 1 EUR = 90 INR)
INR_TO_EUR_RATE = 90.0

def load_retail_transactions():
    if not DATABASE_URL:
        print("Error: DATABASE_URL missing from .env")
        return
    if not CSV_PATH.exists():
        print(f"Error: retail_transactions.csv not found at {CSV_PATH}")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 2. Recreate aviation.retail table with exact columns
    print("Setting up aviation.retail table in Supabase...")
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS aviation;

        DROP TABLE IF EXISTS aviation.retail CASCADE;

        CREATE TABLE aviation.retail (
            transaction_id VARCHAR(50) PRIMARY KEY,
            flight_api_id VARCHAR(64) REFERENCES aviation.flights(flight_api_id) ON DELETE CASCADE,
            pos_terminal_id VARCHAR(50),
            store_type VARCHAR(50),
            item_category VARCHAR(50),
            customer_reference VARCHAR(50),
            item_name VARCHAR(100),
            quantity INT,
            amount_eur NUMERIC(8, 2),
            net_amount_eur NUMERIC(8, 2),
            payment_method VARCHAR(50),
            currency VARCHAR(10) DEFAULT 'EUR',
            terminal VARCHAR(20),
            location_area VARCHAR(50),
            is_duty_free BOOLEAN,
            transacted_at TIMESTAMP
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

    print(f"Found {len(schiphol_flight_ids)} Schiphol flights to link retail transactions to.")

    # 4. Read Kaggle Retail CSV and convert amounts
    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, header=None, skiprows=1)

    records = []
    for i, row in df.iterrows():
        mapped_flight_id = schiphol_flight_ids[i % len(schiphol_flight_ids)]
        
        # Convert INR amounts to EUR
        raw_gross_inr = float(row[9]) if pd.notna(row[9]) else 0.0
        raw_net_inr = float(row[10]) if pd.notna(row[10]) else 0.0
        amount_eur = round(raw_gross_inr / INR_TO_EUR_RATE, 2)
        net_amount_eur = round(raw_net_inr / INR_TO_EUR_RATE, 2)

        # Normalize terminal naming for Schiphol
        raw_term = str(row[14]).strip() if pd.notna(row[14]) else "T1"
        term_map = {"T1": "Terminal 1", "T2": "Terminal 2", "T3": "Terminal 3"}
        terminal = term_map.get(raw_term, f"Terminal {raw_term.replace('T','')}")

        records.append((
            str(row[0])[:50],                                          # transaction_id
            mapped_flight_id,                                          # flight_api_id (Schiphol)
            str(row[1])[:50] if pd.notna(row[1]) else None,            # pos_terminal_id
            str(row[2])[:50] if pd.notna(row[2]) else 'Duty Free',     # store_type
            str(row[3])[:50] if pd.notna(row[3]) else 'Retail',        # item_category
            str(row[4])[:50] if pd.notna(row[4]) else None,            # customer_reference
            str(row[7])[:100] if pd.notna(row[7]) else 'Item',         # item_name
            int(row[8]) if pd.notna(row[8]) else 1,                    # quantity
            amount_eur,                                                # amount_eur
            net_amount_eur,                                            # net_amount_eur
            str(row[11])[:50] if pd.notna(row[11]) else 'Card',        # payment_method
            'EUR',                                                     # currency
            terminal,                                                  # terminal
            str(row[15])[:50] if pd.notna(row[15]) else 'Near Gate',   # location_area
            bool(row[16]) if pd.notna(row[16]) else True,              # is_duty_free
            str(row[6]) if pd.notna(row[6]) else None                  # transacted_at
        ))

    # 5. Insert mapped retail transactions
    insert_sql = """
    INSERT INTO aviation.retail (
        transaction_id, flight_api_id, pos_terminal_id, store_type,
        item_category, customer_reference, item_name, quantity,
        amount_eur, net_amount_eur, payment_method, currency,
        terminal, location_area, is_duty_free, transacted_at
    ) VALUES %s
    ON CONFLICT (transaction_id) DO NOTHING;
    """

    print(f"Inserting {len(records)} mapped retail transactions into Supabase...")
    execute_values(cur, insert_sql, records, page_size=1000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM aviation.retail;")
    total_count = cur.fetchone()[0]
    print(f"Success! aviation.retail now has {total_count} rows.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    load_retail_transactions()