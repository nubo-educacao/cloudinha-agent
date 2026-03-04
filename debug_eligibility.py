import asyncio
from src.tools.evaluatePassportEligibility import evaluatePassportEligibilityTool
from src.lib.supabase import supabase

# fetch a user ID
res = supabase.table("user_profiles").select("id").limit(1).execute()
if res.data:
    user_id = res.data[0]["id"]
    print(f"Testing for user {user_id}")
    out = evaluatePassportEligibilityTool(user_id)
    print("OUTPUT:", out)
    
    # Check what got saved
    check = supabase.table("user_profiles").select("eligibility_results").eq("id", user_id).execute()
    print("SAVED IN DB:", check.data)
else:
    print("No users found.")
