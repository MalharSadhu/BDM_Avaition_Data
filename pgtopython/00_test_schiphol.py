import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# 1. Locate and load .env file from the Capstone root folder
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# 2. Read keys from environment, with your direct keys as fallbacks
APP_ID = os.getenv("SCHIPHOL_APP_ID") or "c7975fa0"
APP_KEY = os.getenv("SCHIPHOL_APP_KEY") or "3659e1db02308c95f9e5b706c71d2faf"

print(f"Using APP_ID: {APP_ID}")
print("Connecting to Schiphol Public Flights API...")

url = "https://api.schiphol.nl/public-flights/flights"

headers = {
    "Accept": "application/json",
    "app_id": APP_ID.strip(),
    "app_key": APP_KEY.strip(),
    "ResourceVersion": "v4"
}

try:
    response = requests.get(url, headers=headers)
    
    print(f"HTTP Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        flights = data.get("flights", [])
        print(f"Success! Retrieved {len(flights)} real flight records from Schiphol.\n")
        
        if flights:
            print("--- Sample Flight Record (First Item) ---")
            print(json.dumps(flights[0], indent=2))
    else:
        print(f"Request failed with response:\n{response.text}")

except Exception as e:
    print(f"Error during API request: {e}")