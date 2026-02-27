from typing import Dict, Any, Optional
from src.lib.error_handler import safe_execution
from src.lib.supabase import supabase

@safe_execution(error_type="evaluate_passport_eligibility_error", default_return={"status": "error", "message": "Failed to evaluate eligibility"})
def evaluatePassportEligibilityTool(user_id: str) -> Dict[str, Any]:
    """
    Evaluates the user's eligibility for available programs based on partner_forms.is_criterion = True.
    It checks mapping_source variables if available in user_profiles.
    
    Args:
        user_id (str): Logging in user ID
        
    Returns:
        dict: Eligible programs and their details, or questions to ask if criteria are missing.
    """
    # 1. Fetch user profile
    profile_res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
    if not profile_res.data:
         return {"status": "error", "message": "User not found"}
         
    profile = profile_res.data[0]
    
    # 2. Fetch all criteria forms
    criteria_res = supabase.table("partner_forms").select("partner_id, field_name, mapping_source, criterion_rule").eq("is_criterion", True).execute()
    
    if not criteria_res.data:
         return {"status": "success", "eligible_partners": [], "missing_information": []}
         
    # Logic to evaluate criteria
    # This is a simplified version. Real version would apply `criterion_rule` JSON Logic.
    # For now, let's just return a placeholder indicating we found criteria to ask about or match.
    
    return {
        "status": "success",
        "message": "Criteria fetched.",
        "criteria": criteria_res.data
    }
