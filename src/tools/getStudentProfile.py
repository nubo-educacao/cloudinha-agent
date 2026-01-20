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

    # Fetch detailed scores history
    scores_history = []
    try:
        scores_response = supabase.table("user_enem_scores") \
            .select("year, nota_linguagens, nota_ciencias_humanas, nota_ciencias_natureza, nota_matematica, nota_redacao") \
            .eq("user_id", user_id) \
            .order("year", desc=True) \
            .execute()
        
        if scores_response and hasattr(scores_response, 'data'):
            scores_history = scores_response.data
    except Exception as e:
        print(f"!!! [ERROR READ] Scores fetch failed: {e}")

    # Fetch user preferences
    preferences_data = None
    try:
        preferences_response = supabase.table("user_preferences") \
            .select("enem_score, family_income_per_capita, quota_types, course_interest, location_preference, state_preference, preferred_shifts, university_preference, workflow_data, device_latitude, device_longitude, program_preference, registration_step") \
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
        # Trust the DB flag if it's explicitly True
        if profile_data.get("onboarding_completed"):
            onboarding_completed = True
        else:
             # Fallback logic (legacy) - Keep consistent with frontend if needed
             # But if we rely on the flag, we should rely on the flag.
             # Let's keep the fallback for older users who might have data but no flag.
             onboarding_completed = bool(
                profile_data.get("full_name") and 
                profile_data.get("city") and 
                profile_data.get("education") and
                profile_data.get("age") # Added age check for completeness
            )

    return {
        "user_id": user_id,
        "onboarding_completed": onboarding_completed,
        "active_workflow": profile_data.get("active_workflow") if profile_data else None,
        # workflow_data moved to preferences
        "full_name": profile_data.get("full_name") if profile_data else None,
        "registered_city_name": profile_data.get("city") if profile_data else None,
        "age": profile_data.get("age") if profile_data else None,
        "education": profile_data.get("education") if profile_data else None,
        "enem_score": preferences_data.get("enem_score") if preferences_data else None,
        "enem_scores_history": scores_history,
        "per_capita_income": preferences_data.get("family_income_per_capita") if preferences_data else None,
        "course_interest": preferences_data.get("course_interest") if preferences_data else None,
        "location_preference": preferences_data.get("location_preference") if preferences_data else None,
        "state_preference": preferences_data.get("state_preference") if preferences_data else None,
        "quota_types": preferences_data.get("quota_types", []) if preferences_data else [],
        "preferred_shifts": preferences_data.get("preferred_shifts", []) if preferences_data else [],
        "university_preference": preferences_data.get("university_preference") if preferences_data else None,
        "program_preference": preferences_data.get("program_preference") if preferences_data else None,
        "device_latitude": preferences_data.get("device_latitude") if preferences_data else None,
        "device_longitude": preferences_data.get("device_longitude") if preferences_data else None,
        "device_longitude": preferences_data.get("device_longitude") if preferences_data else None,
        "workflow_data": preferences_data.get("workflow_data") if preferences_data else {},
        "registration_step": preferences_data.get("registration_step") if preferences_data else None
    }
