# BDM Aviation Data

A complete Aviation Data Warehouse integrating live REST APIs, public aviation networks, Kaggle datasets, and synthesized ground logistics into a unified PostgreSQL database on Supabase.

## Database Schema (10 Tables)

- **airports**: OpenFlights global airports reference.
- **airlines**: OpenFlights global carrier directory.
- **routes**: OpenFlights route network connectivity.
- **flights**: Live flight telemetry from Amsterdam Airport Schiphol REST API.
- **weather**: Hourly surface weather from Open-Meteo API.
- **passengers**: Passenger demographics and satisfaction survey profiles.
- **maintenance_logs**: Aircraft engineering logs mapped to active Schiphol flights.
- **retail**: Terminal POS concession transactions converted to EUR.
- **baggage**: Luggage handling logs with overweight fee logic.
- **parking**: Synthesized parking records based on official Schiphol tariffs (P1–P6, EV charging).

## Execution Sequence

```bash
python pgtopython/01_load_master_reference.py
python pgtopython/02_load_live_schiphol_flights.py
python pgtopython/03_load_weather_and_passengers.py
python pgtopython/04_load_maintenance_logs.py
python pgtopython/05_load_retail.py
python pgtopython/06_load_baggage.py
python pgtopython/07_load_parking.py
python pgtopython/08_preview_all_tables.py