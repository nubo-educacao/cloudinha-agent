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
    
    IMPORTANT: This tool should ONLY be called when the user explicitly expresses their choice 
    (e.g., "it's for me", "it's for my son"). Do NOT call this tool automatically based on 
    profile completion or age if a choice hasn't been clearly communicated by the user.
    
    Args:
        user_id (str): The ID of the currently logged-in user (the responsible/parent).
        choice (str): "self" or "dependent".
    
    Returns:
        dict: Result with status and the next phase.
    """
    choice = choice.lower().strip()
    # Handle natural language phrases from UI
    is_dependent_kw = any(word in choice for word in [
        "dependent", "pessoa", "outra", "filho", "filha", "parente", 
        "irmão", "irmã", "neto", "neta", "sobrinho", "sobrinha"
    ])
    is_self_kw = any(word in choice for word in [
        "self", "mim", "meu", "minha", "próprio", "própria", "eu mesmo", "eu mesma"
    ])
    
    # Priority check: if it looks like dependent, it's dependent. 
    # Otherwise, if it looks like self, it's self.
    if is_dependent_kw:
        is_dependent = True
    elif is_self_kw:
        is_dependent = False
    else:
        # Default fallback or let LLM decide? If called by Reasoning Agent, it should be clear.
        is_dependent = "dependent" in choice # Fallback to original logic
    
    if is_dependent:
        # Check if parent already has a dependent assigned
        parent_res = supabase.table("user_profiles").select("current_dependent_id").eq("id", user_id).single().execute()
        existing_dependent_id = parent_res.data.get("current_dependent_id") if parent_res.data else None
        
        if existing_dependent_id:
            dependent_id = existing_dependent_id
            print(f"!!! [DEPENDENT REUSED] id={dependent_id}, parent={user_id}")
            # Ensure phase is updated even if reusing
            updateStudentProfileTool(user_id=dependent_id, updates={"passport_phase": "DEPENDENT_ONBOARDING"})
        else:
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
            # Also create user_preferences for the dependent to avoid errors in later phases
            supabase.table("user_preferences").insert({"user_id": dependent_id}).execute()
            print(f"!!! [DEPENDENT CREATED] id={dependent_id}, parent={user_id}")
        
        # Save the dependent_id on the parent's profile and set it as active target
        updateStudentProfileTool(user_id=user_id, updates={
            "current_dependent_id": dependent_id,
            "active_application_target_id": dependent_id,
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
        # Self application — transition to PROGRAM_MATCH and set target
        updateStudentProfileTool(user_id=user_id, updates={
            "active_application_target_id": user_id,
            "passport_phase": "PROGRAM_MATCH",
            "eligibility_results": None
        })
        
        return {
            "status": "success",
            "isdependent": False,
            "next_phase": "PROGRAM_MATCH",
            "message": "Aplicação será para si próprio. Avançando para análise de elegibilidade (PROGRAM_MATCH)."
        }
