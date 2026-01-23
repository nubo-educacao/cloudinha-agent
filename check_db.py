import os
import json
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY/SUPABASE_KEY in .env")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

USER_ID = '6f6bf62b-cb16-41ec-a228-243ad7e3ce1b'

print(f"Checking user_preferences for user_id: {USER_ID}")

try:
    response = supabase.table("user_preferences").select("*").eq("user_id", USER_ID).execute()
    
    if not response.data:
        print("!!! No user_preferences record found for this user.")
    else:
        record = response.data[0]
        wf_data = record.get("workflow_data", {})
        print("\n--- WORKFLOW DATA ---")
        print(json.dumps(wf_data, indent=2, ensure_ascii=False))
        
        last_ids = wf_data.get("last_course_ids", [])
        if last_ids:
            print(f"\n!!! Found {len(last_ids)} persisted course IDs.")
        else:
            print("\n!!! workflow_data exists but 'last_course_ids' is empty or missing.")

except Exception as e:
    print(f"Error querying Supabase: {e}")
