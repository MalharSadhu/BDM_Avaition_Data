import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

# Automatically finds .env even if inside a subfolder
load_dotenv(find_dotenv(), override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def test_connection():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found. Verify your .env file is in the Capstone root folder.")
        return

    connection = None
    try:
        username = DATABASE_URL.split(":")[1].replace("//", "")
        print(f"Attempting to connect with username: {username}")

        connection = psycopg2.connect(DATABASE_URL)
        print("Connection successful!")
        
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"Connected to: {db_version[0]}")
        cursor.close()

    except Exception as e:
        print(f"Connection failed with error: {e}")
    finally:
        if connection:
            connection.close()
            print("Connection closed.")

if __name__ == "__main__":
    test_connection()