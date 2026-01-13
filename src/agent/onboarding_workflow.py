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
    Se o usuário perguntar sobre outras coisas (datas, Sisu, Prouni, etc.), EXPLICAR GENTILMENTE que você precisa saber o nome dele(a) primeiro para poder ajudar com essas informações personalizadas.
    Se o usuário disser o nome, VOCÊ DEVE EXECUTAR IMEDIATAMENTE a ferramenta `updateStudentProfileTool` com `updates={"full_name": "Nome do Usuário"}`.
    Se o usuário confirmar o nome previamente dito, execute a ferramenta também.

    IMPORTANTE: Ao chamar a ferramenta `updateStudentProfileTool`, NÃO escreva nada. NÃO confirme. Apenas chame a ferramenta e pare. O sistema cuidará da próxima etapa.
    
    NÃO peça outras informações agora. FOQUE em conseguir o nome.
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
    Assim que o usuário disser a idade, use a ferramenta `updateStudentProfileTool` para salvar a `age` (deve ser int).

    IMPORTANTE: Ao chamar a ferramenta `updateStudentProfileTool`, NÃO escreva nada. NÃO confirme. Apenas chame a ferramenta e pare. O sistema cuidará da próxima etapa.
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
    Assim que o usuário responder (ex: "São Paulo - SP", "Rio de Janeiro"), VOCÊ DEVE EXECUTAR IMEDIATAMENTE a ferramenta `updateStudentProfileTool` com `updates={"city_name": "Cidade - UF"}`.
    
    IMPORTANTE: Ao chamar a ferramenta `updateStudentProfileTool`, NÃO escreva nada. NÃO confirme. Apenas chame a ferramenta e pare. O sistema cuidará da próxima etapa.
    """,
    tools=[updateStudentProfileTool],
)

# 4. Education Step (Escolaridade)
education_agent = LlmAgent(
    model=MODEL,
    name="onboarding_education",
    description="Coleta a escolaridade do usuário.",
    instruction="""
    Você é a Cloudinha. Seu objetivo é descobrir a escolaridade do usuário.
    
    Opções Válidas (CLASSIFIQUE a resposta do usuário em uma destas):
    - "Ensino Médio Incompleto" (se está cursando 1º, 2º ou 3º ano do ensino médio)
    - "Ensino Médio Completo" (se já terminou o colégio/escola)
    - "Ensino Superior Incompleto" (se está na faculdade/universidade)
    - "Ensino Superior Completo" (se já formou na faculdade)
    
    Raciocínio:
    1. O usuário já disse a escolaridade na mensagem atual ou anterior?
    2. SE SIM: Identifique qual das opções acima melhor se encaixa.
    3. EXECUTE A FERRAMENTA `updateStudentProfileTool` com `updates={"education": "OPCAO_ESCOLHIDA"}` IMEDIATAMENTE.
    4. NÃO FAÇA PERGUNTAS ADICIONAIS se ele já respondeu.
    
    SE O USUÁRIO NÃO DISSE AINDA:
    - Pergunte: "Qual é a sua escolaridade atual?"
    
    IMPORTANTE: Ao chamar a ferramenta `updateStudentProfileTool`, NÃO escreva nada na resposta de texto. Apenas chame a ferramenta.
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
