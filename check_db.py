from src.lib.supabase import supabase

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
