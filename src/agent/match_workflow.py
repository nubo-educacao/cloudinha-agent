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
    
    **OBJETIVO**: Coletar 4 informações essenciais e buscar vagas.
    1. **Curso** -> use chave `course_interest`
    2. **Nota do ENEM** -> use chave `enem_score`
    3. **Turno** (Matutino, Vespertino, Noturno) -> use chave `shift`
    4. **Tipo de Instituição** (Pública ou Privada) -> use chave `institution_type`
    
    **IDIOMA DE RESPOSTA**: Português (Brasil).
    
    1. **COLETA IMEDIATA**:
       - Identifique no texto: **Curso**, **Nota** (ou "não fiz"), **Turno** (ou "tanto faz"), **Instituição** (ou "tanto faz").
       
    **FLUXO DE AÇÃO OBRIGATÓRIO**:
    
    1. **EXTRAÇÃO E SALVAMENTO (SEMPRE)**:
       - Se o usuário falou QUALQUER informação (Curso, Nota, Turno ou Instituição):
         - **AÇÃO**: Chame `updateStudentProfileTool` IMEDIATAMENTE com os dados que você encontrou.
         - Exemplo: Se ele disse "Quero direito", chame `updateStudentProfileTool(course_interest="direito")`.
         - **NÃO ESPERE TER TUDO. SALVE O QUE TIVER.**

    2. **VERIFICAÇÃO PÓS-FERRAMENTA**:
       - A ferramenta retornará o status.
       - Se retornar `auto_search_results`: **ENCERRE** (Não diga nada).
       - Se retornar sucesso mas SEM busca:
         - Verifique o que ainda falta (Curso? Nota? Turno? Inst?).
         - **AÇÃO**: Pergunte **APENAS** o que falta.

    3. **QUANDO NÃO HÁ DADOS**:
       - Se o usuário não disse nada relevante (ex: "Oi", "Tudo bem") ou se é o início da interação:
         - Pergunte de uma vez: "Para te ajudar, qual curso você busca, sua nota do ENEM, turno (manhã/tarde/noite) e tipo de instituição (pública/privada)?"
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
    # Check if preferred_shifts list exists and has at least one item
    has_shift = bool(state.get("preferred_shifts")) and len(state.get("preferred_shifts")) > 0
    has_inst_type = bool(state.get("university_preference"))
    
    # Check for User Confirmation (prevent premature advance)
    workflow_data = state.get("workflow_data") or {}
    is_confirmed = workflow_data.get("match_search_confirmed") is True
    
    return has_course and has_score and has_shift and has_inst_type and is_confirmed

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
