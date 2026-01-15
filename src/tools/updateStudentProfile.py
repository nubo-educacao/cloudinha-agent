from typing import Optional, Dict, Any, List, Union
import json
from src.lib.supabase import supabase

def updateStudentProfileTool(user_id: str, updates: Dict[str, Any]) -> str:
    """Atualiza os dados do aluno durante a conversa."""
    
    # --- DEBUG ALIAS ---
    if user_id == "user":
        user_id = "dac47479-079f-4878-bb43-009e4879fa8b"
        print(f"!!! [DEBUG] Aliased 'user' to {user_id}")

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
