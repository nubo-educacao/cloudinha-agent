import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

supabase = create_client(supabase_url, supabase_key)

user_id = "dac47479-079f-4878-bb43-009e4879fa8b"

with open("debug_output.txt", "w") as f:
    f.write(f"--- Checking Profile for {user_id} ---\n")
    profile = supabase.table("user_profiles").select("active_workflow").eq("id", user_id).execute()
    f.write(str(profile.data) + "\n\n")

    f.write(f"--- Checking Last 5 Messages for {user_id} ---\n")
    messages = supabase.table("chat_messages").select("content, sender, workflow").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
    for msg in messages.data:
        f.write(str(msg) + "\n")
print("Done writing to debug_output.txt")
