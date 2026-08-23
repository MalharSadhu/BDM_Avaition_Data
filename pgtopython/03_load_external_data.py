import os
import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

# 1. Environment configuration
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# ==============================================================================
# SOURCE 1: OpenFlights Master Data (airports, airlines, routes)
# ==============================================================================
def load_openflights_data():
    print("\n[1/3] Downloading & Loading OpenFlights Master Data...")
    conn = get_db_connection()
    cur = conn.cursor()

    # --- 1A. Airports ---
    print("  -> Ingesting airports...")
    airports_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
    airport_cols = ['airport_id', 'name', 'city', 'country', 'iata', 'icao', 'lat', 'lon', 'alt', 'tz', 'dst', 'tz_db', 'type', 'source']
    df_airports = pd.read_csv(airports_url, names=airport_cols, na_values='\\N')
    
    # Filter valid rows and convert types
    df_airports = df_airports.dropna(subset=['airport_id', 'name', 'country'])
    df_airports['airport_id'] = df_airports['airport_id'].astype(int)
    
    airport_records = [
        (
            int(row.airport_id),
            str(row.name)[:150],
            str(row.city)[:100] if pd.notna(row.city) else None,
            str(row.country)[:100],
            str(row.iata)[:10] if pd.notna(row.iata) else None,
            str(row.icao)[:10] if pd.notna(row.icao) else None,
            float(row.lat) if pd.notna(row.lat) else None,
            float(row.lon) if pd.notna(row.lon) else None,
            int(row.alt) if pd.notna(row.alt) else None
        )
        for row in df_airports.itertuples(index=False)
    ]

    execute_values(cur, """
        INSERT INTO aviation.airports (airport_id, name, city, country, iata_code, icao_code, latitude, longitude, altitude)
        VALUES %s
        ON CONFLICT (airport_id) DO NOTHING;
    """, airport_records, page_size=2000)
    print(f"     Loaded {len(airport_records)} airports.")

    # --- 1B. Airlines ---
    print("  -> Ingesting airlines...")
    airlines_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"
    airline_cols = ['airline_id', 'name', 'alias', 'iata', 'icao', 'callsign', 'country', 'active']
    df_airlines = pd.read_csv(airlines_url, names=airline_cols, na_values='\\N')
    
    df_airlines = df_airlines.dropna(subset=['airline_id', 'name'])
    df_airlines = df_airlines[df_airlines['airline_id'] > 0]
    
    airline_records = [
        (
            int(row.airline_id),
            str(row.name)[:150],
            str(row.alias)[:100] if pd.notna(row.alias) else None,
            str(row.iata)[:10] if pd.notna(row.iata) else None,
            str(row.icao)[:10] if pd.notna(row.icao) else None,
            str(row.callsign)[:150] if pd.notna(row.callsign) else None,
            str(row.country)[:100] if pd.notna(row.country) else None,
            str(row.active)[:1] if pd.notna(row.active) else 'N'
        )
        for row in df_airlines.itertuples(index=False)
    ]

    execute_values(cur, """
        INSERT INTO aviation.airlines (airline_id, name, alias, iata_code, icao_code, callsign, country, active_status)
        VALUES %s
        ON CONFLICT (airline_id) DO NOTHING;
    """, airline_records, page_size=2000)
    print(f"     Loaded {len(airline_records)} airlines.")

    # --- 1C. Routes ---
    print("  -> Ingesting routes...")
    routes_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"
    route_cols = ['airline', 'airline_id', 'src_airport', 'src_airport_id', 'dest_airport', 'dest_airport_id', 'codeshare', 'stops', 'equipment']
    df_routes = pd.read_csv(routes_url, names=route_cols, na_values='\\N')

    route_records = [
        (
            str(row.airline)[:10] if pd.notna(row.airline) else None,
            str(row.src_airport)[:10] if pd.notna(row.src_airport) else None,
            str(row.dest_airport)[:10] if pd.notna(row.dest_airport) else None,
            str(row.codeshare)[:1] if pd.notna(row.codeshare) else 'N',
            int(row.stops) if pd.notna(row.stops) else 0,
            str(row.equipment)[:50] if pd.notna(row.equipment) else None
        )
        for row in df_routes.itertuples(index=False)
    ]

    execute_values(cur, """
        INSERT INTO aviation.routes (airline_code, source_airport, destination_airport, codeshare, stops, equipment)
        VALUES %s;
    """, route_records, page_size=5000)
    print(f"     Loaded {len(route_records)} routes.")

    conn.commit()
    cur.close()
    conn.close()

# ==============================================================================
# SOURCE 2: Open-Meteo Weather API (Amsterdam Schiphol Coordinates)
# ==============================================================================
def load_weather_data():
    print("\n[2/3] Fetching Weather data from Open-Meteo API...")
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=52.3086&longitude=4.7639&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m"
    )
    
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Weather API failed with status {resp.status_code}")
        return

    data = resp.json().get("hourly", {})
    times = data.get("time", [])
    temps = data.get("temperature_2m", [])
    humidities = data.get("relative_humidity_2m", [])
    winds = data.get("wind_speed_10m", [])

    records = []
    for t, temp, hum, wind in zip(times, temps, humidities, winds):
        records.append(("EHAM - Amsterdam Schiphol", t, temp, hum, wind))

    conn = get_db_connection()
    cur = conn.cursor()
    
    execute_values(cur, """
        INSERT INTO aviation.weather (station_name, recorded_at, temperature_c, relative_humidity, wind_speed_kmh)
        VALUES %s;
    """, records)

    conn.commit()
    cur.close()
    conn.close()
    print(f"Loaded {len(records)} hourly weather observations into aviation.weather.")

# ==============================================================================
# SOURCE 3: OpenSky Network API (Aircraft Telemetry)
# ==============================================================================
def load_opensky_aircraft():
    print("\n[3/3] Fetching Live Aircraft Telemetry from OpenSky Network API...")
    url = "https://opensky-network.org/api/states/all?lamin=50.75&lomin=3.2&lamax=53.7&lomax=7.22"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            states = resp.json().get("states", [])
            print(f"Retrieved {len(states)} active transponder states from OpenSky.")
            if states:
                print("Sample OpenSky Aircraft State Vector:")
                print(f"  ICAO24 Transponder : {states[0][0]}")
                print(f"  Callsign           : {states[0][1]}")
                print(f"  Origin Country     : {states[0][2]}")
                print(f"  Position (Lat/Lon) : {states[0][6]}, {states[0][5]}")
                print(f"  Velocity           : {states[0][9]} m/s")
        else:
            print(f"OpenSky status {resp.status_code} (Rate limit/service busy).")
    except Exception as e:
        print(f"OpenSky network check skipped: {e}")

if __name__ == "__main__":
    load_openflights_data()
    load_weather_data()
    load_opensky_aircraft()