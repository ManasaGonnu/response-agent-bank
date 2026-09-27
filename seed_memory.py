import json
import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()

API_KEY = os.getenv("HINDSIGHT_API_KEY")
API_URL = os.getenv("HINDSIGHT_API_URL")
BANK_ID = os.getenv("HINDSIGHT_BANK_ID")

client = Hindsight(
    api_key=API_KEY,
    base_url=API_URL
)

def seed():
    with open("incidents.json", "r") as f:
        incidents = json.load(f)

    for item in incidents:
        content = (
            f"Incident ID: {item['incident_id']}\n"
            f"Service: {item['service']}\n"
            f"Symptom: {item['symptom']}\n"
            f"Log Snippet: {item['log_snippet']}\n"
            f"Root Cause: {item['root_cause']}\n"
            f"Runbook Fix:\n{item['runbook_fix']}\n"
            f"Critical Warning: {item['warning']}"
        )
        
        print(f"Retaining {item['incident_id']}...")
        client.retain(
            bank_id=BANK_ID,
            content=content,
            metadata={
                "incident_id": item["incident_id"],
                "service": item["service"]
            }
        )
        print(f"Successfully retained {item['incident_id']}!")

if __name__ == "__main__":
    seed()