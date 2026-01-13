from typing import Optional, Dict
from src.lib.supabase import supabase

def getStudentProfileTool(user_id: str) -> Dict:
    """Recupera as informações socioeconômicas e de perfil do estudante salvas."""

    # Fetch user profile
    # Fetch user profile
    profile_data = None
    try:
        # Use simple select and handle list manually to avoid maybe_single 406 issues
        profile_response = supabase.table("user_profiles") \
            .select("full_name, city, age, education, onboarding_completed, active_workflow") \
            .eq("id", user_id) \
            .execute()
        
        # Check if response exists and has data
        if profile_response and hasattr(profile_response, 'data') and profile_response.data:
            if len(profile_response.data) > 0:
                profile_data = profile_response.data[0]
        
        print(f"!!! [DEBUG READ] getStudentProfileTool raw profile for {user_id}: {profile_data}")
    except Exception as e:
        print(f"!!! [ERROR READ] getStudentProfileTool FAILED: {e}")
        profile_data = None

    # Fetch user preferences
    # Fetch user preferences
    preferences_data = None
    try:
        preferences_response = supabase.table("user_preferences") \
            .select("enem_score, family_income_per_capita, quota_types, course_interest, location_preference, state_preference") \
            .eq("user_id", user_id) \
            .execute()
            
        if preferences_response and hasattr(preferences_response, 'data') and preferences_response.data:
             if len(preferences_response.data) > 0:
                preferences_data = preferences_response.data[0]
    except Exception as e:
        print(f"!!! [ERROR READ] Preferences fetch failed: {e}")
        preferences_data = None
    
    # Calculate onboarding status
    # Prioritize DB flag, fallback to check
    onboarding_completed = False
    if profile_data:
        if profile_data.get("onboarding_completed"):
            onboarding_completed = True
        else:
             # Fallback logic (legacy)
             onboarding_completed = bool(
                profile_data.get("full_name") and 
                profile_data.get("city") and 
                profile_data.get("education")
            )

    return {
        "user_id": user_id,
        "onboarding_completed": onboarding_completed,
        "active_workflow": profile_data.get("active_workflow") if profile_data else None,
        "full_name": profile_data.get("full_name") if profile_data else None,
        "city_name": profile_data.get("city") if profile_data else None,
        "age": profile_data.get("age") if profile_data else None,
        "education": profile_data.get("education") if profile_data else None,
        "enem_score": preferences_data.get("enem_score") if preferences_data else None,
        "per_capita_income": preferences_data.get("family_income_per_capita") if preferences_data else None,
        "course_interest": preferences_data.get("course_interest") if preferences_data else None,
        "location_preference": preferences_data.get("location_preference") if preferences_data else None,
        "state_preference": preferences_data.get("state_preference") if preferences_data else None,
        "quota_types": preferences_data.get("quota_types", []) if preferences_data else []
    }
