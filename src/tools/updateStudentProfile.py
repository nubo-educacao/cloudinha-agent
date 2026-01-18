from typing import Optional, Dict, Any, List, Union
import json
from src.lib.supabase import supabase

def standardize_city(city_input: str) -> Optional[Dict[str, str]]:
    """
    Match city name against cities table using fuzzy search.
    Returns {"name": standardized_name, "state": state_code} or None.
    """
    if not city_input or not city_input.strip():
        return None
    
    try:
        # First try exact match (case-insensitive)
        response = supabase.table("cities").select("name, state").ilike("name", city_input.strip()).limit(1).execute()
        if response.data:
            return {"name": response.data[0]["name"], "state": response.data[0]["state"]}
        
        # Fallback to partial match
        response = supabase.table("cities").select("name, state").ilike("name", f"%{city_input.strip()}%").limit(1).execute()
        if response.data:
            return {"name": response.data[0]["name"], "state": response.data[0]["state"]}
    except Exception as e:
        print(f"[WARN] City standardization failed: {e}")
    
    return None

def updateStudentProfileTool(user_id: str, updates: Dict[str, Any]) -> str:
    """Atualiza os dados do aluno durante a conversa."""
    


    print(f"!!! [DEBUG TOOL] updateStudentProfileTool CALLED with user_id={user_id}, updates={updates}")
    
    results = {
        "profile_updated": False,
        "preferences_updated": False,
        "errors": []
    }

    # Update user_profiles if applicable
    profile_updates = {}
    
    # Standardize city name if provided
    if "city_name" in updates:
        raw_city = updates["city_name"]
        standardized = standardize_city(raw_city)
        if standardized:
            profile_updates["city"] = standardized["name"]
            print(f"!!! [CITY STANDARDIZED] '{raw_city}' -> '{standardized['name']}' ({standardized['state']})")
        else:
            profile_updates["city"] = raw_city  # Keep original if not found
            print(f"!!! [CITY NOT FOUND] Keeping original: '{raw_city}'")
    
    if "age" in updates:
        profile_updates["age"] = updates["age"]
    if "full_name" in updates:
        profile_updates["full_name"] = updates["full_name"]
    if "academic_goal" in updates:
        profile_updates["education"] = updates["academic_goal"] # Support legacy input key
    if "education" in updates:
        profile_updates["education"] = updates["education"]
    if "onboarding_completed" in updates:
        profile_updates["onboarding_completed"] = updates["onboarding_completed"]
    if "active_workflow" in updates:
        profile_updates["active_workflow"] = updates["active_workflow"]

    if profile_updates:
        data = profile_updates.copy()
        data["id"] = user_id
        
        # Use upsert to ensure row exists
        try:
            response = supabase.table("user_profiles").upsert(data, on_conflict="id").execute()
            print(f"!!! [DEBUG WRITE] Update response: {response}")
            results["profile_updated"] = True 
        except Exception as e:
            print(f"!!! [ERROR WRITE] Update FAILED: {e}")
            results["errors"].append(str(e))

    return json.dumps({"success": True, **results}, ensure_ascii=False)

