from typing import Optional, Dict
import time
from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution

# --- Cache Configuration ---
_PROFILE_CACHE = {}
CACHE_TTL_SECONDS = 300 # 5 minutes

def get_cached_profile(user_id: str) -> Optional[Dict]:
    """Retrieve profile from cache if valid."""
    if user_id in _PROFILE_CACHE:
        entry = _PROFILE_CACHE[user_id]
        if time.time() - entry['timestamp'] < CACHE_TTL_SECONDS:
            return entry['data']
        else:
            del _PROFILE_CACHE[user_id] # Expired
    return None

def set_cached_profile(user_id: str, data: Dict):
    """Save profile to cache."""
    _PROFILE_CACHE[user_id] = {
        'data': data,
        'timestamp': time.time()
    }

def invalidate_profile_cache(user_id: str):
    """Remove user from cache."""
    if user_id in _PROFILE_CACHE:
        del _PROFILE_CACHE[user_id]
        # print(f"!!! [CACHE INVALIDATED] User {user_id}")

@safe_execution(error_type="tool_error", default_return={})
def getStudentProfileTool(user_id: str) -> Dict:
    """Recupera as informações socioeconômicas e de perfil do estudante salvas."""

    # --- Cache Disabled for Chat Real-time updates ---
    # cached = get_cached_profile(user_id)
    # if cached:
    #     return cached

    # Fetch user profile
    profile_data = None
    # Use simple select and handle list manually to avoid maybe_single 406 issues
    profile_response = supabase.table("user_profiles") \
        .select("full_name, city, age, education, onboarding_completed, active_workflow") \
        .eq("id", user_id) \
        .execute()
    
    if profile_response and hasattr(profile_response, 'data') and profile_response.data:
        if len(profile_response.data) > 0:
            profile_data = profile_response.data[0]
    
    # print(f"!!! [DEBUG READ] getStudentProfileTool raw profile for {user_id}: {profile_data}")

    # Fetch detailed scores history
    scores_history = []
    
    scores_response = supabase.table("user_enem_scores") \
        .select("year, nota_linguagens, nota_ciencias_humanas, nota_ciencias_natureza, nota_matematica, nota_redacao") \
        .eq("user_id", user_id) \
        .order("year", desc=True) \
        .execute()
    
    if scores_response and hasattr(scores_response, 'data'):
        scores_history = scores_response.data

    # Fetch user preferences
    preferences_data = None
    preferences_response = supabase.table("user_preferences") \
        .select("enem_score, family_income_per_capita, quota_types, course_interest, location_preference, state_preference, preferred_shifts, university_preference, workflow_data, device_latitude, device_longitude, program_preference, registration_step") \
        .eq("user_id", user_id) \
        .execute()
        
    if preferences_response and hasattr(preferences_response, 'data') and preferences_response.data:
            if len(preferences_response.data) > 0:
            # Fixed indentation
                preferences_data = preferences_response.data[0]
    
    # Calculate onboarding status
    onboarding_completed = False
    if profile_data:
        if profile_data.get("onboarding_completed"):
            onboarding_completed = True
        else:
                onboarding_completed = bool(
                profile_data.get("full_name") and 
                profile_data.get("city") and 
                profile_data.get("education") and
                profile_data.get("age") 
            )

    result = {
        "user_id": user_id,
        "onboarding_completed": onboarding_completed,
        "active_workflow": profile_data.get("active_workflow") if profile_data else None,
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
        "workflow_data": preferences_data.get("workflow_data") if preferences_data else {},
        "registration_step": preferences_data.get("registration_step") if preferences_data else None
    }

    # Save to cache (Disabled)
    # set_cached_profile(user_id, result)
    
    return result
