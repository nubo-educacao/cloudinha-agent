from src.agent.workflow_agent import WorkflowAgent, WorkflowStep
from google.adk.agents import LlmAgent
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.agent.agent import MODEL

# --- Step Agents ---

# 1. Basic Preferences Step (Course & Score)
basic_prefs_agent = LlmAgent(
    model=MODEL,
    name="match_basic_prefs",
    description="Coleta Curso e Nota do ENEM.",
    instruction="""
    Você é o Match, especialista em conectar alunos a faculdades.
    Seu objetivo agora é descobrir o **Curso de interesse** e a **Nota do ENEM** (ou estimativa) do aluno.
    
    1. Pergunte qual curso o aluno quer (ex: Direito, Medicina, Engenharia).
    2. Pergunte a nota do ENEM (ex: 600, 700).
    
    Assim que o usuário fornecer essas informações:
    1. Salve-as no perfil usando `updateStudentProfileTool` (busque campos compatíveis ou use 'course_interest' e 'enem_score' se existirem, senão adapte).
       *Nota: O esquema atual do banco pode não ter 'course_interest' explícito nas colunas comuns, mas `updateStudentProfileTool` aceita dicionário. Vamos assumir que o agente tenta salvar.*
    2. EXECUTE `searchOpportunitiesTool` com o nome do curso e a nota para mostrar opções iniciais.
    
    Mostre os resultados de forma resumida e empolgante.
    """,
    tools=[updateStudentProfileTool, searchOpportunitiesTool],
)

# 2. Socioeconomic Step (Income)
socioeconomic_agent = LlmAgent(
    model=MODEL,
    name="match_socioeconomic",
    description="Coleta Renda Per Capita para refinar bolsas.",
    instruction="""
    Você é o Match. Agora vamos ver as melhores bolsas (Prouni/Sisu) para o bolso do aluno.
    
    1. Pergunte a **Renda Per Capita** mensal da família (ou ajude a calcular perguntando renda total e pessoas na casa).
    
    Assim que o usuário responder:
    1. Salve a renda usando `updateStudentProfileTool` (campo `per_capita_income` ou similar).
    2. EXECUTE `searchOpportunitiesTool` novamente, agora INCLUINDO a renda per capita para filtrar bolsas elegíveis (Prouni 100%, 50%, etc).
    
    Explique brevemente se ele é elegível a Prouni (Até 1.5 salários = 100%, até 3 = 50%).
    """,
    tools=[updateStudentProfileTool, searchOpportunitiesTool],
)

# 3. Refinement Step (Location)
refinement_agent = LlmAgent(
    model=MODEL,
    name="match_refinement",
    description="Refina por Localização (Cidade).",
    instruction="""
    Você é o Match. Para finalizar, vamos encontrar opções perto de casa.
    
    1. Pergunte se o aluno tem preferência por alguma **Cidade** específica ou se quer ver as de sua cidade atual.
    
    Assim que o usuário responder:
    1. Salve a cidade de interesse usando `updateStudentProfileTool`.
    2. EXECUTE `searchOpportunitiesTool` passando a cidade para priorizar/ordenar os resultados.
    
    Apresente a lista final de melhores oportunidades.
    """,
    tools=[updateStudentProfileTool, searchOpportunitiesTool],
)


# --- Conditions ---
# We need to define what constitutes "complete" for each step based on the profile state.
# Ideally, we check if the relevant fields are present in the user profile.

def check_basic_prefs(state):
    # Check if we have course and score
    # course_interest is now returned by getStudentProfileTool correctly
    has_course = bool(state.get("course_interest")) 
    has_score = state.get("enem_score") is not None
    return has_course and has_score

def check_socioeconomic(state):
    # Check for income
    return state.get("per_capita_income") is not None

def check_location(state):
    # Check for target city (location_preference)
    return bool(state.get("location_preference"))


# --- Workflow Definition ---

match_steps = [
    WorkflowStep(name="basic_prefs", condition=check_basic_prefs, agent=basic_prefs_agent),
    WorkflowStep(name="socioeconomic", condition=check_socioeconomic, agent=socioeconomic_agent),
    WorkflowStep(name="refinement", condition=check_location, agent=refinement_agent),
]

def get_profile_state(user_id: str):
    return getStudentProfileTool(user_id)

match_workflow = WorkflowAgent(
    name="match_workflow",
    steps=match_steps,
    get_state_fn=get_profile_state
)
