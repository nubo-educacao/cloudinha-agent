from src.agent.workflow_agent import WorkflowAgent, WorkflowStep
from google.adk.agents import LlmAgent
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.agent.agent import MODEL

# --- Step Agents ---

# 1. Name Step
name_agent = LlmAgent(
    model=MODEL,
    name="onboarding_name",
    description="Coleta o nome do usuário.",
    instruction="""
    Você é a Cloudinha. Seu objetivo é descobrir o nome do usuário.
    Se o usuário disser o nome, VOCÊ DEVE EXECUTAR IMEDIATAMENTE a ferramenta `updateStudentProfileTool` com `updates={"full_name": "Nome do Usuário"}`.
    Se o usuário confirmar o nome previamente dito, execute a ferramenta também.
    NÃO peça outras informações agora. APENAS execute a ferramenta se tiver o nome.
    """,
    tools=[updateStudentProfileTool],
)

# 2. Age Step
age_agent = LlmAgent(
    model=MODEL,
    name="onboarding_age",
    description="Coleta a idade do usuário.",
    instruction="""
    Você é a Cloudinha. Agora que você sabe o nome, pergunte a idade do usuário.
    Seja breve.
    Assim que o usuário disser a idade, use a ferramenta `updateStudentProfileTool` para salvar a `age` (deve ser int).
    """,
    tools=[updateStudentProfileTool],
)

# 3. City Step
city_agent = LlmAgent(
    model=MODEL,
    name="onboarding_city",
    description="Coleta a cidade do usuário.",
    instruction="""
    Você é a Cloudinha. Pergunte em qual cidade e estado o usuário mora.
    Assim que o usuário responder, use a ferramenta `updateStudentProfileTool` para salvar `city_name`.
    """,
    tools=[updateStudentProfileTool],
)

# 4. Education Step (Escolaridade)
education_agent = LlmAgent(
    model=MODEL,
    name="onboarding_education",
    description="Coleta a escolaridade do usuário.",
    instruction="""
    Você é a Cloudinha. Pergunte a escolaridade atual do usuário.
    Assim que o usuário responder (ex: "terminei o ensino médio", "estou no 3º ano"), VOCÊ DEVE EXECUTAR IMEDIATAMENTE a ferramenta `updateStudentProfileTool` com `updates={"education": "Ensino Médio Completo"}` (ou o valor correspondente).
    NÃO peça confirmação. APENAS SALVE.
    """,
    tools=[updateStudentProfileTool],
)


# --- Conditions ---

def check_name(state):
    print(f"[DEBUG CHECK] Name: {state.get('full_name')}")
    return bool(state.get("full_name"))

def check_age(state):
    print(f"[DEBUG CHECK] Age: {state.get('age')}")
    return state.get("age") is not None

def check_city(state):
    print(f"[DEBUG CHECK] City: {state.get('city_name')}")
    return bool(state.get("city_name"))

def check_education(state):
    print(f"[DEBUG CHECK] Education: {state.get('education')}")
    return bool(state.get("education"))


# --- Workflow Definition ---

onboarding_steps = [
    WorkflowStep(name="name_step", condition=check_name, agent=name_agent),
    WorkflowStep(name="age_step", condition=check_age, agent=age_agent),
    WorkflowStep(name="city_step", condition=check_city, agent=city_agent),
    WorkflowStep(name="education_step", condition=check_education, agent=education_agent),
]

def get_profile_state(user_id: str):
    return getStudentProfileTool(user_id)

onboarding_workflow = WorkflowAgent(
    name="onboarding_workflow",
    steps=onboarding_steps,
    get_state_fn=get_profile_state
)
