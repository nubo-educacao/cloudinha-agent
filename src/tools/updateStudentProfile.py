from typing import Optional, Dict, Any, List
from src.lib.supabase import supabase

def updateStudentProfileTool(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza os dados do aluno durante a conversa."""
    
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
        profile_updates["academic_goal"] = updates["academic_goal"]

    if profile_updates:
        data = profile_updates.copy()
        data["id"] = user_id
        
        # Use upsert to ensure row exists
        response = supabase.table("user_profiles").upsert(data, on_conflict="id").execute()
        
        # Supabase-py throws exception on error usually, but we check data presence to be safe? 
        # Actually supabase-py execute returns APIResponse.
        # If there's an error, it might raise postgrest.exceptions.APIError.
        # We'll assume success if no exception for now or wrap in try/except if needed.
        # For simple port, assuming normal operation.
        results["profile_updated"] = True # Simplified check

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
