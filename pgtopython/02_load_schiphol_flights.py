import os
import requests
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

# 1. Environment & credentials setup
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
APP_ID = os.getenv("SCHIPHOL_APP_ID") or "c7975fa0"
APP_KEY = os.getenv("SCHIPHOL_APP_KEY") or "3659e1db02308c95f9e5b706c71d2faf"

def fetch_and_insert_flights():
    if not DATABASE_URL:
        print("Error: DATABASE_URL is missing in .env")
        return

    # 2. Fetch data from Schiphol Public Flights API
    url = "https://api.schiphol.nl/public-flights/flights"
    headers = {
        "Accept": "application/json",
        "app_id": APP_ID.strip(),
        "app_key": APP_KEY.strip(),
        "ResourceVersion": "v4"
    }

    print("Fetching live flights from Schiphol API...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        print(f"Network request failed: {e}")
        return

    if response.status_code != 200:
        print(f"Schiphol API error (Status {response.status_code}): {response.text}")
        return

    flights_raw = response.json().get("flights", [])
    print(f"Successfully fetched {len(flights_raw)} flights from API.")

    # 3. Extract and map JSON fields to tuples
    records = []
    for f in flights_raw:
        flight_id = f.get("id")
        flight_name = f.get("flightName")
        if not flight_id or not flight_name:
            continue

        flight_num = f.get("flightNumber")
        prefix_iata = f.get("prefixIATA")
        direction = f.get("flightDirection")
        s_date = f.get("scheduleDate")
        s_time = f.get("scheduleTime")
        s_datetime = f.get("scheduleDateTime")
        
        # Nested status
        flight_states = f.get("publicFlightState", {}).get("flightStates", [])
        status = flight_states[0] if flight_states else None
        
        # Nested aircraft
        aircraft_main = f.get("aircraftType", {}).get("iataMain")
        
        # Nested route destinations
        destinations = f.get("route", {}).get("destinations", [])
        dest_iata = destinations[0] if destinations else None
        
        is_op = f.get("isOperationalFlight", False)
        svc_type = f.get("serviceType")

        records.append((
            str(flight_id),
            str(flight_name),
            int(flight_num) if flight_num is not None else None,
            str(prefix_iata) if prefix_iata else None,
            str(direction) if direction else None,
            s_date,
            s_time,
            s_datetime,
            str(status) if status else None,
            str(aircraft_main) if aircraft_main else None,
            str(dest_iata) if dest_iata else None,
            bool(is_op),
            str(svc_type) if svc_type else None
        ))

    if not records:
        print("No flight records extracted.")
        return

    # 4. Insert into PostgreSQL
    insert_query = """
    INSERT INTO aviation.flights (
        flight_api_id, flight_name, flight_number, airline_iata,
        direction, schedule_date, schedule_time, scheduled_datetime,
        flight_status, aircraft_type, destination_iata, is_operational, service_type
    ) VALUES %s
    ON CONFLICT (flight_api_id) DO UPDATE SET
        flight_status = EXCLUDED.flight_status,
        scheduled_datetime = EXCLUDED.scheduled_datetime;
    """

    print("Connecting to Supabase PostgreSQL and inserting flights...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    execute_values(cur, insert_query, records, page_size=500)
    conn.commit()
    
    print(f"Successfully inserted/updated {len(records)} flights in aviation.flights!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    fetch_and_insert_flights()