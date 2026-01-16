from src.agent.workflow_agent import WorkflowAgent, WorkflowStep
from google.adk.agents import LlmAgent
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.logModeration import logModerationTool
from src.agent.agent import MODEL
from src.agent.utils import load_instruction_from_file

# --- Single Onboarding Agent ---

onboarding_agent = LlmAgent(
    model=MODEL,
    name="onboarding_agent",
    description="Coleta os dados do perfil do usuário em uma conversa fluida.",
    instruction=load_instruction_from_file("onboarding_agent_instruction.txt") + "\n\n" + load_instruction_from_file("persona.txt"),
    tools=[updateStudentProfileTool, logModerationTool],
)

# --- Condition ---

def check_profile_complete(state):
    """
    Retorna True apenas se TODOS os 4 campos essenciais estiverem preenchidos.
    """
    profile = state  # Assumindo que 'state' já é o dicionário do perfil ou contém as chaves
    
    has_name = bool(profile.get("full_name"))
    has_age = profile.get("age") is not None
    has_city = bool(profile.get("city_name"))
    has_education = bool(profile.get("education"))

    # Debug logs para facilitar rastreio
    print(f"[ONBOARDING CHECK] Name={has_name}, Age={has_age}, City={has_city}, Educ={has_education}")

    return has_name and has_age and has_city and has_education

# --- Workflow Definition ---

onboarding_steps = [
    WorkflowStep(
        name="profile_collection",
        condition=check_profile_complete,
        agent=onboarding_agent
    ),
]

def get_profile_state(user_id: str):
    return getStudentProfileTool(user_id)

onboarding_workflow = WorkflowAgent(
    name="onboarding_workflow",
    steps=onboarding_steps,
    get_state_fn=get_profile_state
)
