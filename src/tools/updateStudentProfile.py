from typing import Optional, Dict, Any, List
from src.lib.supabase import supabase

def updateStudentProfileTool(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza os dados do aluno durante a conversa."""
    print(f"!!! [DEBUG TOOL] updateStudentProfileTool CALLED with user_id={user_id}, updates={updates}")
    
    results = {
        "profile_updated": False,
        "preferences_updated": False,
        "errors": []
    }

    # Update user_profiles if applicable
    profile_updates = {}
    if "city_name" in updates:
        profile_updates["city"] = updates["city_name"]
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

    # Update user_preferences if applicable
    preferences_updates = {}
    if "enem_score" in updates:
        preferences_updates["enem_score"] = updates["enem_score"]
    if "per_capita_income" in updates:
        preferences_updates["family_income_per_capita"] = updates["per_capita_income"]
    
    if preferences_updates:
        # Check existence manually first
        existing_prefs_response = supabase.table("user_preferences") \
            .select("id") \
            .eq("user_id", user_id) \
            .maybe_single() \
            .execute()
        
        existing_prefs = existing_prefs_response.data

        if existing_prefs:
            # Update
            supabase.table("user_preferences") \
                .update(preferences_updates) \
                .eq("id", existing_prefs["id"]) \
                .execute()
        else:
            # Insert
            data = preferences_updates.copy()
            data["user_id"] = user_id
            supabase.table("user_preferences").insert(data).execute()
        
        results["preferences_updated"] = True

    return {"success": True, **results}
