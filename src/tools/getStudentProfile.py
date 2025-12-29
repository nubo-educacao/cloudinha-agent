from typing import Optional, Dict
from src.lib.supabase import supabase

def getStudentProfileTool(user_id: str) -> Dict:
    """Recupera as informações socioeconômicas e de perfil do estudante salvas."""

    # Fetch user profile
    profile_response = supabase.table("user_profiles") \
        .select("full_name, city, age, academic_goal") \
        .eq("id", user_id) \
        .maybe_single() \
        .execute()
    
    profile_data = profile_response.data
    
    if not profile_data:
        print(f"Error fetching user_profiles: No profile found for user_id {user_id}")

    # Fetch user preferences
    preferences_response = supabase.table("user_preferences") \
        .select("enem_score, family_income_per_capita, quota_types") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()

    preferences_data = preferences_response.data

    if not preferences_data:
        print(f"Error fetching user_preferences: No preferences found for user_id {user_id}")
    
    return {
        "user_id": user_id,
        "full_name": profile_data.get("full_name") if profile_data else None,
        "city_name": profile_data.get("city") if profile_data else None,
        "age": profile_data.get("age") if profile_data else None,
        "academic_goal": profile_data.get("academic_goal") if profile_data else None,
        "enem_score": preferences_data.get("enem_score") if preferences_data else None,
        "per_capita_income": preferences_data.get("family_income_per_capita") if preferences_data else None,
        "quota_types": preferences_data.get("quota_types", []) if preferences_data else []
    }
