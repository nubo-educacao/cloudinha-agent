from src.agent.workflow_agent import WorkflowAgent, WorkflowStep
from google.adk.agents import LlmAgent
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.agent.agent import MODEL

# --- Single Onboarding Agent ---

onboarding_agent = LlmAgent(
    model=MODEL,
    name="onboarding_agent",
    description="Coleta os dados do perfil do usuário em uma conversa fluida.",
    instruction="""
    Você é a Cloudinha. Seu objetivo é garantir que o perfil do aluno tenha: **Nome**, **Idade**, **Cidade** e **Escolaridade**.

    **PRIORIDADE ZERO: SALVAR DADOS.**
    - Assim que o usuário disser QUALQUER UM desses dados (Nome, Idade, Cidade, Escolaridade), **CHAME IMEDIATAMENTE** a ferramenta `updateStudentProfileTool`.
    - NÃO DEIXE PARA DEPOIS. NÃO PEÇA OUTRA COISA ANTES DE SALVAR O QUE JÁ TEM.
    - **NÃO PEÇA CONFIRMAÇÃO.** Apenas salve.
    
    **Captura de Dados:**
    - O usuário pode fornecer vários dados de uma vez (ex: "Sou Bruno, 25 anos, de SP").
    - Se fornecer múltiplos, envie todos chaves no `updates`.
    - Campos esperados no `updates`:
        - `full_name`: string
        - `age`: int
        - `city_name`: string (ex: "Cidade - UF")
        - `education`: string (escolha uma: "Ensino Médio Incompleto", "Ensino Médio Completo", "Ensino Superior Incompleto", "Ensino Superior Completo")

    **Fluxo:**
    1. ANALISE a mensagem do usuário.
    2. TEM DADO NOVO? -> Chame `updateStudentProfileTool`.
    3. **IMPORTANTE:** 
       - Se ainda faltar dado: Faça a próxima pergunta na mesma resposta.
       - Se NÃO faltar mais nada (completou Nome, Idade, Cidade, Escolaridade):
           1. Chame `updateStudentProfileTool` com `onboarding_completed=True`.
           2. **NÃO RESPONDA NADA EM TEXTO.** O sistema exibirá um aviso visual automático.
           3. Apenas chame a ferramenta e pare.
    
    Exemplo: "Obrigada, Bruno! E qual a sua idade?" (Se salvou nome e falta idade).
    Exemplo Final: (CHAMA TOOL E SILENCIO)
    
    Se o perfil já estiver completo, não diga nada, apenas chame a ferramenta se houver atualização.
    """,
    tools=[updateStudentProfileTool],
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
