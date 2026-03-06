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
        .select("full_name, city, age, education, onboarding_completed, active_workflow, passport_phase, isdependent, parent_user_id, current_dependent_id, zip_code, state, street, street_number, complement") \
        .eq("id", user_id) \
        .execute()
    
    if profile_response and hasattr(profile_response, 'data') and profile_response.data:
        if len(profile_response.data) > 0:
            profile_data = profile_response.data[0]
    
    # print(f"!!! [DEBUG READ] getStudentProfileTool raw profile for {user_id}: {profile_data}")

    # (ENEM Scores History fetch removed to avoid agent confusion and optimize query)

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
    
    # Calculate onboarding status dynamically
    onboarding_completed = False
    if profile_data:
        # Check if all required fields are present
        has_name = bool(profile_data.get("full_name"))
        has_age = bool(profile_data.get("age"))
        has_city = bool(profile_data.get("city"))
        has_education = bool(profile_data.get("education"))
        has_zip = bool(profile_data.get("zip_code"))
        has_street_number = bool(profile_data.get("street_number"))
        
        onboarding_completed = has_name and has_age and has_city and has_education and has_zip and has_street_number

    result = {
        "user_id": user_id,
        "onboarding_completed": onboarding_completed,
        "active_workflow": profile_data.get("active_workflow") if profile_data else None,
        "passport_phase": profile_data.get("passport_phase", "INTRO") if profile_data else "INTRO",
        "isdependent": profile_data.get("isdependent", False) if profile_data else False,
        "parent_user_id": profile_data.get("parent_user_id") if profile_data else None,
        "current_dependent_id": profile_data.get("current_dependent_id") if profile_data else None,
        "full_name": profile_data.get("full_name") if profile_data else None,
        "registered_city_name": profile_data.get("city") if profile_data else None,
        "age": profile_data.get("age") if profile_data else None,
        "education": profile_data.get("education") if profile_data else None,
        "zip_code": profile_data.get("zip_code") if profile_data else None,
        "state": profile_data.get("state") if profile_data else None,
        "street": profile_data.get("street") if profile_data else None,
        "street_number": profile_data.get("street_number") if profile_data else None,
        "complement": profile_data.get("complement") if profile_data else None,
        "enem_score": preferences_data.get("enem_score") if preferences_data else None,
        "per_capita_income": preferences_data.get("family_income_per_capita") if preferences_data else None,
        "quota_types": preferences_data.get("quota_types", []) if preferences_data else [],
        "eligibility_results": profile_data.get("eligibility_results", []) if profile_data else []
    }

    # Save to cache (Disabled)
    # set_cached_profile(user_id, result)
    
    return result
