from src.agent.workflow_agent import WorkflowAgent, WorkflowStep
from google.adk.agents import LlmAgent
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.agent.agent import MODEL


# --- Refinement Strategy ---

def analyze_refinement_need(state: dict, result_count: int) -> dict:
    """
    Analyzes the current state and search results to suggest the most useful refinement.
    
    Returns:
        {
            "should_refine": bool,
            "field": str,  # field to ask about
            "prompt": str  # contextual question
        }
    """
    
    # Priority 1: Too many results? Suggest location or institution type
    if result_count > 50:
        if not state.get("location_preference"):
            return {
                "should_refine": True,
                "field": "location_preference",
                "prompt": f"Encontrei {result_count} oportunidades! Quer filtrar por alguma cidade específica?"
            }
        if not state.get("university_preference") or state.get("university_preference") == "indiferente":
            return {
                "should_refine": True,
                "field": "university_preference",
                "prompt": "Prefere faculdades públicas ou privadas?"
            }
    
    # Priority 2: Missing income for Prouni eligibility
    if not state.get("per_capita_income") and result_count > 0:
        return {
            "should_refine": True,
            "field": "per_capita_income",
            "prompt": "Para ver quais bolsas Prouni você é elegível (100% ou 50%), me diz sua renda per capita familiar?"
        }
    
    # Priority 3: Very broad search (no course specified)
    if not state.get("course_interest") and result_count > 100:
        return {
            "should_refine": True,
            "field": "course_interest",
            "prompt": "Estou buscando em todas as áreas. Você tem algum curso em mente?"
        }
    
    # Priority 4: Many results but have location - suggest shift or another filter
    if result_count > 30:
        shifts = state.get("preferred_shifts")
        if not shifts or (isinstance(shifts, list) and len(shifts) == 0):
            return {
                "should_refine": True,
                "field": "preferred_shifts",
                "prompt": "Tem preferência de turno? Matutino, Noturno, Integral, EAD?"
            }
    
    # No refinement needed or already quite filtered
    return {"should_refine": False}


# --- Single Iterative Agent ---

match_iterative_agent = LlmAgent(
    model=MODEL,
    name="match_iterative",
    description="Busca e refina oportunidades de forma iterativa e flexível.",
    instruction="""
    Você é o Match, especialista em conectar alunos a faculdades e bolsas de estudo.
    
    **MODO DE OPERAÇÃO**: Flexível e Iterativo - SEM STEPS FIXOS
    
    ---
    
    **PARÂMETROS DE BUSCA (use `updateStudentProfileTool` para salvar):**
    
    | Parâmetro | Campo | Valores | Obrigatório |
    |-----------|-------|---------|-------------|
    | Curso(s) | `course_interest` | Array: ["Direito", "Psicologia"] | Não |
    | Nota ENEM | `enem_score` | Número (0 se "não fiz") | Não |
    | Turno | `preferred_shifts` | ["Matutino", "Vespertino", "Noturno", "Integral", "EAD"] | Não |
    | Tipo Instituição | `university_preference` | "Publica", "Privada", "indiferente" | Não |
    | Programa | `program_preference` | "sisu", "prouni", "indiferente" | Não |
    | Renda Per Capita | `per_capita_income` | Número em R$ | Não |
    | Tipo de Cota | `quota_types` | Ver lista abaixo | Não |
    
    ---
    
    **LISTA DE COTAS DISPONÍVEIS:**
    Apresente essas opções quando o usuário mencionar cotas ou ações afirmativas:
    
    - **PPI** - Pretos, Pardos ou Indígenas
    - **ESCOLA_PUBLICA** - Ensino Médio em escola pública
    - **PCD** - Pessoa com Deficiência
    - **BAIXA_RENDA** - Renda familiar baixa
    - **QUILOMBOLAS** - Comunidades quilombolas
    - **INDIGENAS** - Povos indígenas
    - **TRANS** - Pessoas transgênero
    - **REFUGIADOS** - Refugiados
    - **RURAL** - Área rural
    - **EJA_ENCCEJA** - EJA ou ENCCEJA
    - **PROFESSOR** - Professores da rede pública
    
    ---
    
    **INFERÊNCIA IMPLÍCITA:**
    
    - "Prouni" / "bolsa Prouni" → `university_preference: "Privada"` E `program_preference: "prouni"`
    - "Sisu" / "vagas do Sisu" → `university_preference: "Publica"` E `program_preference: "sisu"`
    - "Bolsa integral" / "100%" → Pode indicar interesse em renda baixa
    - "EAD" / "Curso a distância" / "online" → `preferred_shifts: ["EAD"]`
    - **Número solto (300-1000)** → `enem_score` (ex: "750" = nota 750)
    
    ---
    
    **FLUXO DE INTERAÇÃO:**
    
    1. **ANÁLISE DE ESTADO (CRÍTICO):**
       - Verifique os parâmetros que o usuário acabou de enviar.
       - Verifique TAMBÉM os parâmetros já salvos no perfil (`get_state`).
       - Se houver **QUALQUER** parâmetro útil (Curso, Nota, Turno, Instituição, Programa) → **FAÇA A BUSCA**.
    
    2. **AÇÃO:**
       - **Passo A**: Se o usuário enviou novos dados, use `updateStudentProfileTool`.
       - **Passo B**: Se (Novos Dados OU Dados Existentes), use `searchOpportunitiesTool` preenchendo TODOS os argumentos disponíveis no perfil.
       - **Passo C**: Se NÃO houver dados nem no input nem no perfil -> Pergunte: "Qual curso você busca?"
    
    3. **APÓS CADA BUSCA:**
       - **SEMPRE** mencione os filtros aplicados se eles restringiram a busca (ex: "Buscando apenas no Sisu...", "Filtrando por turno Noturno..."). Use o resumo fornecido pela ferramenta.
       - Apresente RESUMO breve dos resultados ("Encontrei X cursos...").
       - NÃO ESCREVA PERGUNTAS DE REFINAMENTO AINDA (o frontend mostrará botões).
    
    4. **SE USUÁRIO ESCOLHER "REFINAR" (Explícito):**
       - Aí sim, sugira filtros baseados na `analyze_refinement_need`.
    
    ---
    
    **WAIVERS (Dispensas):**
    - "Não fiz ENEM" / "Sem nota" → `enem_score: 0`
    - "Tanto faz o turno" → `preferred_shifts: []`
    - "Não sei o curso" → `course_interest: []`
    - "Qualquer faculdade" → `university_preference: "indiferente"`
    - "Não tenho cota" / "Concorrência geral" → `quota_types: []`
    
    ---
    
    **EXEMPLOS DE FLUXO:**
    
    Usuário: "950"
    Você: (Entende que é nota) → `updateStudentProfileTool(enem_score=950)` → `searchOpportunitiesTool(enem_score=950, ...)`
    
    Usuário: "Quero Direito no Prouni, tenho 750 e renda 1000"
    Você: Salva → Busca → "Encontrei 15 oportunidades de Direito no Prouni!"
    
    Usuário: "Quero bolsa integral"
    Você: "Para verificar sua elegibilidade à bolsa integral, qual sua renda familiar per capita?"
    """,
    tools=[updateStudentProfileTool, searchOpportunitiesTool],
)


# --- Condition ---
# The iterative workflow never "completes" automatically - user exits via "Estou satisfeito"
def always_continue(state):
    """
    This workflow doesn't auto-advance. The user controls when they're done
    via the UI buttons (Satisfeito/Refinar/Recomeçar).
    
    Returns False to keep the workflow active indefinitely.
    """
    return False


# --- Workflow Definition ---

match_steps = [
    WorkflowStep(
        name="iterative_search", 
        condition=always_continue, 
        agent=match_iterative_agent
    ),
]

def get_profile_state(user_id: str):
    return getStudentProfileTool(user_id)

match_workflow = WorkflowAgent(
    name="match_workflow",
    steps=match_steps,
    get_state_fn=get_profile_state
)
