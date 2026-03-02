from typing import Dict, Any, Optional
import json
from src.lib.error_handler import safe_execution
from src.lib.supabase import supabase

@safe_execution(error_type="get_next_partner_question_error", default_return={"status": "error", "message": "Failed to get next question"})
def getNextPartnerQuestionTool(user_id: str, partner_id: str) -> Dict[str, Any]:
    """
    Finds the next unanswered partner form question for the student_applications.
    Auto-fills answers from mapping_source when data already exists in user_profiles.
    
    Args:
        user_id (str): The logged-in user ID
        partner_id (str): The partner ID they are applying for
        
    Returns:
        dict: The next question to ask, or a completion status.
    """
    
    # 1. Fetch or create application + existing answers
    app_res = supabase.table("student_applications").select("id, answers").eq("user_id", user_id).eq("partner_id", partner_id).execute()
    
    answers = {}
    app_id = None
    if app_res.data:
        answers = app_res.data[0].get("answers", {}) or {}
        app_id = app_res.data[0].get("id")
    
    # 2. Fetch user profile for mapping_source lookups
    profile_res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
    profile = profile_res.data[0] if profile_res.data else {}
        
    # 3. Fetch partner forms ordered by sort_order
    forms_res = supabase.table("partner_forms").select("*").eq("partner_id", partner_id).order("sort_order").execute()
    
    if not forms_res.data:
        return {"status": "error", "message": "No forms found for partner"}
    
    # 4. Auto-fill from mapping_source and find next unanswered question
    auto_filled = {}
    
    for form in forms_res.data:
        field_name = form["field_name"]
        
        # Already answered in student_applications
        if field_name in answers:
            continue
            
        # Check mapping_source for auto-fill
        mapping = form.get("mapping_source")
        if mapping:
            parts = mapping.split(".")
            if len(parts) == 2 and parts[0] == "user_profiles":
                prof_field = parts[1]
                value = profile.get(prof_field)
                if value is not None and value != "":
                    # Auto-fill! Save to answers
                    answers[field_name] = value
                    auto_filled[field_name] = value
                    print(f"[getNextPartnerQuestion] Auto-filled '{field_name}' from user_profiles.{prof_field} = {value}")
                    continue
        
        # Found an unanswered question that needs user input!
        # But first, save any auto-filled answers
        if auto_filled:
            _save_answers(user_id, partner_id, answers, app_id)
        
        return {
            "status": "question",
            "question": {
                "id": form["id"],
                "field_name": form["field_name"],
                "question_text": form["question_text"],
                "options": form.get("options"),
                "is_criterion": form.get("is_criterion", False)
            },
            "auto_filled_count": len(auto_filled)
        }
    
    # All questions answered (possibly some auto-filled just now)
    if auto_filled:
        _save_answers(user_id, partner_id, answers, app_id)
    
    return {
        "status": "completed",
        "message": "All questions have been answered.",
        "total_answers": len(answers),
        "auto_filled_count": len(auto_filled)
    }


def _save_answers(user_id: str, partner_id: str, answers: dict, app_id: str = None):
    """Helper to upsert answers to student_applications."""
    data = {
        "user_id": user_id,
        "partner_id": partner_id,
        "answers": answers
    }
    if app_id:
        data["id"] = app_id
    
    supabase.table("student_applications").upsert(data, on_conflict="user_id, partner_id").execute()
    print(f"[getNextPartnerQuestion] Saved {len(answers)} answers for partner {partner_id}")
