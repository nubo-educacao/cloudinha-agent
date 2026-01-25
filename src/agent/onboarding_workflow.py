from typing import Any, Dict, Optional
from google.adk.agents import LlmAgent, Agent
from src.agent.base_workflow import BaseWorkflow
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.logModeration import logModerationTool
from src.agent.config import MODEL_ONBOARDING
from src.agent.utils import load_instruction_from_file

# --- Single Onboarding Agent Definition ---
onboarding_agent = LlmAgent(
    model=MODEL_ONBOARDING,
    name="onboarding_agent",
    description="Coleta os dados do perfil do usuário em uma conversa fluida.",
    instruction=load_instruction_from_file("onboarding_agent_instruction.txt") + "\n\n" + load_instruction_from_file("persona.txt"),
    tools=[updateStudentProfileTool, logModerationTool],
)

def check_profile_complete(state: Dict[str, Any]) -> bool:
    """
    Retorna True apenas se TODOS os 4 campos essenciais estiverem preenchidos.
    """
    has_name = bool(state.get("full_name"))
    has_age = state.get("age") is not None
    has_city = bool(state.get("city_name"))
    has_education = bool(state.get("education"))

    # Debug logs
    if not (has_name and has_age and has_city and has_education):
        print(f"[ONBOARDING CHECK] Incomplete: Name={has_name}, Age={has_age}, City={has_city}, Educ={has_education}")
        
    return has_name and has_age and has_city and has_education

class OnboardingWorkflow(BaseWorkflow):
    @property
    def name(self) -> str:
        return "onboarding_workflow"

    def get_agent_for_user(self, user_id: str, current_state: Dict[str, Any]) -> Optional[Agent]:
        # If profile is NOT complete, return the agent to complete it.
        # Note: current_state should be the profile
        if not check_profile_complete(current_state):
            return onboarding_agent
        
        # If complete, we return None, indicating this workflow is done.
        return None

    def handle_step_completion(self, user_id: str, current_state: Dict[str, Any], step_output: str) -> Optional[Dict[str, Any]]:
        # Check if we just finished
        if check_profile_complete(current_state):
            print(f"[Workflow] Onboarding Complete. Marking flag.")
            return {"onboarding_completed": True, "active_workflow": None}
        return None

# Singleton instance
onboarding_workflow = OnboardingWorkflow()
