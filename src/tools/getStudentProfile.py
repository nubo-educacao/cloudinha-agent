from typing import Optional, Dict
from src.lib.supabase import supabase

def getStudentProfileTool(user_id: str) -> Dict:
    """Recupera as informações socioeconômicas e de perfil do estudante salvas."""

    # Fetch user profile
    try:
        profile_response = supabase.table("user_profiles") \
            .select("full_name, city, age, education") \
            .eq("id", user_id) \
            .maybe_single() \
            .execute()
        profile_data = profile_response.data
        print(f"!!! [DEBUG READ] getStudentProfileTool raw profile for {user_id}: {profile_data}")
    except Exception as e:
        print(f"!!! [ERROR READ] getStudentProfileTool FAILED: {e}")
        profile_data = None

    # Fetch user preferences
    try:
        preferences_response = supabase.table("user_preferences") \
            .select("enem_score, family_income_per_capita, quota_types") \
            .eq("user_id", user_id) \
            .maybe_single() \
            .execute()
        preferences_data = preferences_response.data
    except Exception:
        preferences_data = None
    
    # Calculate onboarding status
    # Considered complete if basic profile info and education are present
    onboarding_completed = bool(
        profile_data and 
        profile_data.get("full_name") and 
        profile_data.get("city") and 
        profile_data.get("education")
    )

    return {
        "user_id": user_id,
        "onboarding_completed": onboarding_completed,
        "full_name": profile_data.get("full_name") if profile_data else None,
        "city_name": profile_data.get("city") if profile_data else None,
        "age": profile_data.get("age") if profile_data else None,
        "education": profile_data.get("education") if profile_data else None,
        "enem_score": preferences_data.get("enem_score") if preferences_data else None,
        "per_capita_income": preferences_data.get("family_income_per_capita") if preferences_data else None,
        "quota_types": preferences_data.get("quota_types", []) if preferences_data else []
    }
