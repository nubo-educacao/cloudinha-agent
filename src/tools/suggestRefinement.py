from typing import Dict, Any
from src.tools.getStudentProfile import getStudentProfileTool
from src.lib.error_handler import safe_execution

@safe_execution(error_type="tool_error", default_return="Erro ao sugerir refinamento.")
def suggestRefinementTool(user_id: str, result_count: int) -> str:
    """
    Analyzes the user's profile and the search result count to suggest the most useful refinement question.
    Use this when the search returns too many results (>30) to help the user narrow down their choices.
    
    Args:
        user_id (str): The user's ID to fetch their current profile/preferences.
        result_count (int): The number of results found in the last search.
        
    Returns:
        str: A suggestion instruction for the agent (e.g., "Ask about location preference"), or "No refinement needed".
    """
    
    # Fetch current search state from profile
    # getStudentProfileTool is safe, returns {} on error
    state = getStudentProfileTool(user_id)

    if not state:
        return "Profile not found."

    # Logic: Suggest refinement until we have <= 12 results
    
    # Priority 1: COURSE (Most impactful filter - prevents timeout!)
    if not state.get("course_interest") and result_count > 12:
        return "SUGGESTION: Ask for course interest. Content: 'Para qual curso você gostaria de buscar? Me diz um ou mais cursos!'"
    
    # Priority 2: Location - STATE before City (more common refinement)
    if result_count > 12:
        if not state.get("state_preference"):
            return "SUGGESTION: Ask for state preference. Content: 'Quer filtrar por algum estado específico? (ex: São Paulo, Minas Gerais)'"
        
        if not state.get("location_preference"):
            return "SUGGESTION: Ask the user if they want to filter by a specific city. Content: 'Quer filtrar por alguma cidade específica?'"
            
        if not state.get("university_preference") or state.get("university_preference") == "indiferente":
             return "SUGGESTION: Ask preference for Public vs Private. Content: 'Prefere faculdades públicas ou privadas?'"
    
    # Priority 3: Missing income for Prouni eligibility (only if still > 12)
    if not state.get("per_capita_income") and result_count > 12:
        return "SUGGESTION: Ask for income to check Prouni eligibility. Content: 'Para ver quais bolsas Prouni você é elegível (100% ou 50%), me diz sua renda per capita familiar?'"
    
    # Priority 4: Still > 12 results - suggest shift or another filter
    if result_count > 12:
        shifts = state.get("preferred_shifts")
        if not shifts or (isinstance(shifts, list) and len(shifts) == 0):
             return "SUGGESTION: Ask for shift preference. Content: 'Tem preferência de turno? Matutino, Noturno, Integral, EAD?'"
    
    return "No specific refinement needed. Ask the user if the results are good or if they want to refine manually."
