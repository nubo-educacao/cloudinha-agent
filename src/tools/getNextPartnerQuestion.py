from typing import Dict, Any, Optional
import json
from src.lib.error_handler import safe_execution
from src.lib.supabase import supabase

@safe_execution(error_type="get_next_partner_question_error", default_return={"status": "error", "message": "Failed to get next question"})
def getNextPartnerQuestionTool(user_id: str, partner_id: str) -> Dict[str, Any]:
    """
    Finds the next unanswered partner form question for the student_applications.
    
    Args:
        user_id (str): The logged-in user ID
        partner_id (str): The partner ID they are applying for
        
    Returns:
        dict: The next question to ask, or a completion status.
    """
    
    # 1. Fetch application answers
    app_res = supabase.table("student_applications").select("answers").eq("user_id", user_id).eq("partner_id", partner_id).execute()
    
    answers = {}
    if app_res.data:
        answers = app_res.data[0].get("answers", {})
        
    # 2. Fetch partner forms ordered by sort_order
    # We ideally order by partner_steps and partner_forms sort_order, but for simplicity:
    forms_res = supabase.table("partner_forms").select("*").eq("partner_id", partner_id).order("sort_order").execute()
    
    if not forms_res.data:
        return {"status": "error", "message": "No forms found for partner"}
        
    # 3. Find the first unanswered question
    for form in forms_res.data:
        field_name = form["field_name"]
        
        # Check if already answered in student_applications
        if field_name in answers:
            continue
            
        # Check mapping_source (e.g., if mapping_source == 'user_profiles.city')
        mapping = form.get("mapping_source")
        if mapping:
            parts = mapping.split(".")
            if len(parts) == 2 and parts[0] == "user_profiles":
                prof_field = parts[1]
                prof_res = supabase.table("user_profiles").select(prof_field).eq("id", user_id).execute()
                if prof_res.data and prof_res.data[0].get(prof_field):
                     # Auto-fill condition met! We should inject this to answers, but for the tool reading it:
                     continue # Skip asking, it's known. (In reality we'd save it to answers here)
                     
        # Found an unanswered question!
        return {
            "status": "success",
            "question": {
                "id": form["id"],
                "field_name": form["field_name"],
                "question_text": form["question_text"],
                "options": form.get("options")
            }
        }
        
    return {
        "status": "completed",
        "message": "All questions have been answered."
    }
