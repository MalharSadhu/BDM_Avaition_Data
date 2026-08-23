import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

# 1. Environment configuration
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
CSV_URL = "https://raw.githubusercontent.com/wessamsw/Airline_Passenger_Satisfaction/main/airline_passenger_satisfaction.csv"

def setup_and_load_passengers():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in .env")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 2. Re-create the passengers table to match the CSV schema
    print("Re-creating aviation.passengers table...")
    cur.execute("""
        DROP TABLE IF EXISTS aviation.baggage CASCADE;
        DROP TABLE IF EXISTS aviation.passengers CASCADE;

        CREATE TABLE aviation.passengers (
            passenger_id INT PRIMARY KEY,
            gender VARCHAR(10),
            age INT,
            customer_type VARCHAR(30),
            travel_type VARCHAR(30),
            travel_class VARCHAR(30),
            flight_distance INT,
            departure_delay INT,
            arrival_delay INT,
            checkin_service INT,
            online_boarding INT,
            gate_location INT,
            onboard_service INT,
            seat_comfort INT,
            leg_room_service INT,
            cleanliness INT,
            food_and_drink INT,
            inflight_service INT,
            inflight_wifi_service INT,
            inflight_entertainment INT,
            baggage_handling INT,
            satisfaction VARCHAR(30)
        );

        -- Recreate baggage with reference to passengers
        CREATE TABLE aviation.baggage (
            baggage_tag_id VARCHAR(50) PRIMARY KEY,
            passenger_id INT REFERENCES aviation.passengers(passenger_id) ON DELETE CASCADE,
            flight_api_id VARCHAR(64) REFERENCES aviation.flights(flight_api_id) ON DELETE CASCADE,
            weight_kg NUMERIC(5, 2),
            status VARCHAR(50)
        );
    """)
    conn.commit()

    # 3. Download and read CSV (loading first 5,000 records for fast indexing)
    print(f"Downloading CSV from raw repository...")
    df = pd.read_csv(CSV_URL, nrows=5000)
    
    # Fill NaN values in arrival delay
    df['Arrival Delay'] = df['Arrival Delay'].fillna(0)

    print(f"Preparing {len(df)} records for insertion...")
    
    records = [
        (
            int(row['ID']),
            str(row['Gender']),
            int(row['Age']),
            str(row['Customer Type']),
            str(row['Type of Travel']),
            str(row['Class']),
            int(row['Flight Distance']),
            int(row['Departure Delay']),
            int(row['Arrival Delay']),
            int(row['Check-in Service']),
            int(row['Online Boarding']),
            int(row['Gate Location']),
            int(row['On-board Service']),
            int(row['Seat Comfort']),
            int(row['Leg Room Service']),
            int(row['Cleanliness']),
            int(row['Food and Drink']),
            int(row['In-flight Service']),
            int(row['In-flight Wifi Service']),
            int(row['In-flight Entertainment']),
            int(row['Baggage Handling']),
            str(row['Satisfaction'])
        )
        for _, row in df.iterrows()
    ]

    # 4. Bulk insert using execute_values
    insert_query = """
    INSERT INTO aviation.passengers (
        passenger_id, gender, age, customer_type, travel_type, travel_class,
        flight_distance, departure_delay, arrival_delay, checkin_service,
        online_boarding, gate_location, onboard_service, seat_comfort,
        leg_room_service, cleanliness, food_and_drink, inflight_service,
        inflight_wifi_service, inflight_entertainment, baggage_handling, satisfaction
    ) VALUES %s
    ON CONFLICT (passenger_id) DO NOTHING;
    """

    print("Inserting into Supabase database...")
    execute_values(cur, insert_query, records, page_size=1000)
    conn.commit()

    print(f"Successfully loaded {len(records)} real passenger survey records into aviation.passengers!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    setup_and_load_passengers()