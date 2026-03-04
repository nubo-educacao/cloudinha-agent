from typing import Dict, Any, Optional
from src.lib.error_handler import safe_execution
from src.agent.agent import supabase_client

@safe_execution(error_type="get_student_application_error", default_return={"status": "error", "message": "Failed to fetch student application"})
def getStudentApplicationTool(user_id: str, partner_id: str) -> Dict[str, Any]:
    """
    Fetches the current progress of a student's application for a specific partner program.
    This is used during the EVALUATE phase to see what the student has already filled out,
    allowing the agent to help with missing fields or questions about the application form.
    
    Args:
        user_id (str): The ID of the student. (usually available as USER_ID_CONTEXT)
        partner_id (str): The ID of the partner program the student is applying to.
        
    Returns:
        dict: The application details, including the 'answers' JSON object containing the saved form data.
    """
    try:
        res = supabase_client.table("student_applications") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("partner_id", partner_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if not res.data:
            return {"status": "error", "message": "No application found for this partner."}
            
        return res.data[0]
    except Exception as e:
        return {"status": "error", "message": str(e)}
