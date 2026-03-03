import uuid
from typing import Dict, Any
from src.lib.error_handler import safe_execution
from src.lib.supabase import supabase
from src.tools.updateStudentProfile import updateStudentProfileTool

@safe_execution(error_type="process_dependent_error", default_return={"status": "error", "message": "Failed to process dependent choice"})
def processDependentChoiceTool(user_id: str, choice: str) -> Dict[str, Any]:
    """
    Processes the user's choice about whether they are applying for themselves or a dependent.
    If dependent: creates a NEW user_profiles row for the dependent with isdependent=TRUE.
    If self: just transitions to EVALUATE.
    
    Args:
        user_id (str): The ID of the currently logged-in user (the responsible/parent).
        choice (str): "self" or "dependent".
    
    Returns:
        dict: Result with status and the next phase.
    """
    choice = choice.lower().strip()
    is_dependent = choice == "dependent"
    
    if is_dependent:
        # Create a NEW user_profiles row for the dependent
        dependent_id = str(uuid.uuid4())
        
        dependent_data = {
            "id": dependent_id,
            "isdependent": True,
            "parent_user_id": user_id,
            # These will be filled during DEPENDENT_ONBOARDING:
            "full_name": None,
            "age": None,
            "relationship": None,
            "city": None,
            "education": None,
            "onboarding_completed": False,
            "active_workflow": "passport_workflow",
            "passport_phase": "DEPENDENT_ONBOARDING",
        }
        
        supabase.table("user_profiles").insert(dependent_data).execute()
        print(f"!!! [DEPENDENT CREATED] id={dependent_id}, parent={user_id}")
        
        # Save the dependent_id on the parent's profile so the flow knows which dependent to use
        updateStudentProfileTool(user_id=user_id, updates={
            "current_dependent_id": dependent_id,
            "passport_phase": "DEPENDENT_ONBOARDING",
        })
        
        return {
            "status": "success",
            "isdependent": True,
            "dependent_id": dependent_id,
            "next_phase": "DEPENDENT_ONBOARDING",
            "message": f"Perfil do dependente criado. ID: {dependent_id}"
        }
    else:
        # Self application — transition to EVALUATE instead of PROGRAM_MATCH and process eligibility
        from src.tools.evaluatePassportEligibility import evaluatePassportEligibilityTool
        
        updateStudentProfileTool(user_id=user_id, updates={
            "passport_phase": "EVALUATE",
        })
        
        # We can trigger evaluate right here, or let the agent handle it. The instruction says agent will do it if we are in PROGRAM_MATCH, but we are skipping it. Let's call it just in case, although the phase is EVALUATE now.
        eval_result = evaluatePassportEligibilityTool(user_id=user_id)
        
        return {
            "status": "success",
            "isdependent": False,
            "next_phase": "EVALUATE",
            "message": "Aplicação será para si próprio. Avançando para análise de elegibilidade (EVALUATE).",
            "eligibility_result": eval_result
        }
