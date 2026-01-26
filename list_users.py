from src.lib.supabase import supabase

response = supabase.table("user_profiles").select("id, full_name, onboarding_completed, active_workflow").limit(5).execute()

for user in response.data:
    print(user)
