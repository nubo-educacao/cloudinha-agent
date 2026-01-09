from dotenv import load_dotenv
import os
from supabase import create_client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

supabase = create_client(supabase_url, supabase_key)

response = supabase.table("user_profiles").select("id, full_name, onboarding_completed, active_workflow").limit(5).execute()

for user in response.data:
    print(user)
