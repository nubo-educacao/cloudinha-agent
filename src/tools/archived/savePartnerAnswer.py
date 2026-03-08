from typing import Dict, Any, Optional
import json
from src.lib.error_handler import safe_execution
from src.lib.supabase import supabase

@safe_execution(error_type="save_partner_answer_error", default_return={"status": "error", "message": "Failed to save answer"})
def savePartnerAnswerTool(user_id: str, partner_id: str, field_name: str, answer_value: Any) -> Dict[str, Any]:
    """
    Saves an answer to the student_applications table and updates mapping source if applicable.
    
    Args:
        user_id (str): Logging in user ID.
        partner_id (str): Partner ID of the application.
        field_name (str): The partner_forms.field_name.
        answer_value (Any): The user's answer.
        
    Returns:
        dict: Success or failure.
    """
    # 1. UPSERT student application
    # First, get existing answers
    app_res = supabase.table("student_applications").select("id, answers").eq("user_id", user_id).eq("partner_id", partner_id).execute()
    
    answers = {}
    app_id = None
    if app_res.data:
        answers = app_res.data[0].get("answers", {})
        app_id = app_res.data[0].get("id")
        
    answers[field_name] = answer_value
    
    data = {
         "user_id": user_id,
         "partner_id": partner_id,
         "answers": answers
    }
    
    if app_id:
         data["id"] = app_id
         
    supabase.table("student_applications").upsert(data, on_conflict="user_id, partner_id").execute()
    
    # 2. Check mapping_source to write back
    form_res = supabase.table("partner_forms").select("mapping_source").eq("partner_id", partner_id).eq("field_name", field_name).execute()
    if form_res.data:
         mapping = form_res.data[0].get("mapping_source")
         if mapping:
             parts = mapping.split(".")
             if len(parts) == 2 and parts[0] == "user_profiles":
                 # We need to know if it's dependent?
                 # If the current user_profile for this user_id is `isdependent=True`, we just update it normally because user_id points to the dependent.
                 # Actually, handling dependent UUID vs parent UUID requires strict profiling. 
                 # For now, update the tied user_id profile:
                 prof_field = parts[1]
                 supabase.table("user_profiles").update({prof_field: answer_value}).eq("id", user_id).execute()
                 
    return {"status": "success", "message": f"Answer for {field_name} saved successfully."}
