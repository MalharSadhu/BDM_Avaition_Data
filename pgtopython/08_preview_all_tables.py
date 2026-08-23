import os
import psycopg2
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Set display options for wide console output
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 30)

# 1. Load environment variables
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def preview_schema():
    if not DATABASE_URL:
        print("Error: DATABASE_URL is missing from .env")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get all tables in the 'aviation' schema
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'aviation' 
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]

    if not tables:
        print("No tables found in the 'aviation' schema.")
        return

    print("=" * 80)
    print(f" AVIATION SCHEMA DATABASE SUMMARY ({len(tables)} tables found)")
    print("=" * 80)

    for table in tables:
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM aviation.{table};")
        row_count = cur.fetchone()[0]

        print(f"\n Table: aviation.{table}  |  Total Rows: {row_count}")
        print("-" * 80)

        if row_count > 0:
            df = pd.read_sql_query(f"SELECT * FROM aviation.{table} LIMIT 3;", conn)
            print(df.to_string(index=False))
        else:
            print("(Table is empty)")

    cur.close()
    conn.close()

if __name__ == "__main__":
    preview_schema()