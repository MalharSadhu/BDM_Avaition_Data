import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# 1. Locate and load .env from the root folder
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
SCHEMA_NAME = "aviation"

DDL_STATEMENTS = f"""
-- Create dedicated schema
CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};
SET search_path TO {SCHEMA_NAME};

-- Drop existing tables (clean restart)
DROP TABLE IF EXISTS parking CASCADE;
DROP TABLE IF EXISTS retail CASCADE;
DROP TABLE IF EXISTS baggage CASCADE;
DROP TABLE IF EXISTS passengers CASCADE;
DROP TABLE IF EXISTS flights CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS weather CASCADE;
DROP TABLE IF EXISTS airlines CASCADE;
DROP TABLE IF EXISTS airports CASCADE;

-- 1. Airports Master (Source: OpenFlights)
CREATE TABLE airports (
    airport_id INT PRIMARY KEY,
    name VARCHAR(150),
    city VARCHAR(100),
    country VARCHAR(100),
    iata_code VARCHAR(10),
    icao_code VARCHAR(10),
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    altitude INT
);

-- 2. Airlines Master (Source: OpenFlights)
CREATE TABLE airlines (
    airline_id INT PRIMARY KEY,
    name VARCHAR(150),
    alias VARCHAR(100),
    iata_code VARCHAR(10),
    icao_code VARCHAR(10),
    callsign VARCHAR(150),
    country VARCHAR(100),
    active_status CHAR(1)
);

-- 3. Routes Master (Source: OpenFlights)
CREATE TABLE routes (
    route_id SERIAL PRIMARY KEY,
    airline_code VARCHAR(10),
    source_airport VARCHAR(10),
    destination_airport VARCHAR(10),
    codeshare CHAR(1),
    stops INT,
    equipment VARCHAR(50)
);

-- 4. Weather Logs (Source: Open-Meteo API)
CREATE TABLE weather (
    weather_id SERIAL PRIMARY KEY,
    station_name VARCHAR(50),
    recorded_at TIMESTAMP,
    temperature_c NUMERIC(4, 1),
    relative_humidity INT,
    wind_speed_kmh NUMERIC(5, 2)
);

-- 5. Operational Flights (Source: Schiphol API)
CREATE TABLE flights (
    flight_api_id VARCHAR(64) PRIMARY KEY,
    flight_name VARCHAR(20) NOT NULL,
    flight_number INT,
    airline_iata VARCHAR(10),
    direction CHAR(1),
    schedule_date DATE NOT NULL,
    schedule_time TIME NOT NULL,
    scheduled_datetime TIMESTAMPTZ,
    flight_status VARCHAR(20),
    aircraft_type VARCHAR(20),
    destination_iata VARCHAR(10),
    is_operational BOOLEAN,
    service_type CHAR(1),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Passenger Master (Synthetic)
CREATE TABLE passengers (
    passenger_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    passport_number VARCHAR(50) UNIQUE,
    nationality VARCHAR(50)
);

-- 7. Baggage Operations (Synthetic)
CREATE TABLE baggage (
    baggage_tag_id VARCHAR(50) PRIMARY KEY,
    passenger_id INT REFERENCES passengers(passenger_id) ON DELETE CASCADE,
    flight_api_id VARCHAR(64) REFERENCES flights(flight_api_id) ON DELETE CASCADE,
    weight_kg NUMERIC(5, 2),
    status VARCHAR(50)
);

-- 8. Commercial Retail & POS (Synthetic)
CREATE TABLE retail (
    receipt_id SERIAL PRIMARY KEY,
    flight_api_id VARCHAR(64) REFERENCES flights(flight_api_id) ON DELETE SET NULL,
    terminal VARCHAR(10),
    store_name VARCHAR(100),
    amount_eur NUMERIC(10, 2),
    payment_method VARCHAR(30),
    transacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Parking & Ground Transportation (Synthetic)
CREATE TABLE parking (
    ticket_id SERIAL PRIMARY KEY,
    parking_lot VARCHAR(10),
    license_plate VARCHAR(20),
    entry_time TIMESTAMP,
    fee_eur NUMERIC(8, 2),
    status VARCHAR(20)
);
"""

def create_tables():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found. Check your .env file.")
        return

    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print(f"Creating schema '{SCHEMA_NAME}' and all 9 tables...")
    cur.execute(DDL_STATEMENTS)
    conn.commit()
    
    cur.close()
    conn.close()
    print("Schema and tables created successfully!")

if __name__ == "__main__":
    create_tables()