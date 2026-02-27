from google.adk.agents import LlmAgent
from src.agent.config import MODEL_ROUTER
from src.lib.error_handler import safe_execution
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import re
import json

# Define the Prompt
# Define the Prompt
ROUTER_INSTRUCTION = """
Você é o Roteador Central da Cloudinha (Assistente Educacional).
Sua função é APENAS CLASSIFICAR a intenção do usuário para decidir qual fluxo deve estar ativo.

**Contexto Atual:**
(O estado atual e o **HISTÓRICO RECENTE DE MENSAGENS** serão fornecidos).

**Workflows Disponíveis:**
1. `passport_workflow`: O usuário quer **A QUALQUER MOMENTO** buscar cursos, bolsas, vagas, tirar dúvidas sobre SISU/PROUNI, iniciar uma aplicação ou falar sobre assuntos educacionais. (QUALQUER AÇÃO OU DÚVIDA EDUCACIONAL).
2. `None` (Root Agent): Conversa casual, "Oi", "Obrigado", ou **PERGUNTAS TÉCNICAS** sobre o próprio bot ("Como funciona?", "Arquitetura").

**DIFERENCIAÇÃO CRÍTICA - Educacional vs Técnico/Meta:**

🎯 **EDUCACIONAL** → `passport_workflow` (verbos de busca, informação e interação):
   - "Quero VER vagas"
   - "Me MOSTRE oportunidades"
   - "Estou procurando curso de X"
   - "O que É o SISU?"
   - "Como faço para me INSCREVER?"
   - "O que são cotas?"

🛠️ **TÉCNICO / META** → `None` (Root Agent):
   - "Como você funciona?"
   - "Qual sua arquitetura?"
   - "Explique seu fluxo técnico"
   - "Quem te criou?"

**Regras de Decisão:**
- **MUDANÇA IMPLÍCITA**: Se a instrução do usuário é nova e sobre buscar, inscrever-se ou tirar dúvida, vá para `passport_workflow`.
    - De Técnico/Meta para Edu → `passport_workflow`
    - De qualquer um para Técnico/Meta → `None` (EXIT_WORKFLOW se já estiver em um, ou apenas target null)
    
- **REGRA CRÍTICA - passport_workflow ATIVO**:
    - Se o `active_workflow` atual é `passport_workflow`, SEMPRE retorne `CONTINUE_WORKFLOW`.
    - O passport_workflow tem agentes internos que lidam com QUALQUER tipo de resposta do usuário.
    - Respostas curtas, nomes, idades, cidades, "minha filha", "pra mim", "outra pessoa", etc. são RESPOSTAS a perguntas do workflow. NÃO reclassifique.
    - A ÚNICA exceção é se o usuário disser explicitamente "sair", "cancelar", "parar" → EXIT_WORKFLOW.

- **CONTINUIDADE (CRÍTICO - ANALISE O HISTÓRICO)**:
    - **LEIA O HISTÓRICO DE MENSAGENS FORNECIDO**.
    - Se a **ÚLTIMA MENSAGEM DO BOT** foi uma pergunta, e a mensagem ATUAL do usuário é a RESPOSTA, mantenha o workflow (`CONTINUE_WORKFLOW`).
    - Respostas podem ser indiretas: "minha filhinha", "17 anos", "São Paulo", "Direito", "pra mim mesmo", etc.
    - Ex: 
      Bot: "Para quem você está buscando a oportunidade?" 
      Usuário: "minha filhinha" 
      -> `CONTINUE_WORKFLOW` (NÃO é uma nova intenção, é resposta à pergunta!)

- **SAÍDA**: "Sair", "Cancelar", "Voltar", "Parar" → `EXIT_WORKFLOW`.

**Exemplos Práticos:**

📌 **EDUCACIONAL → passport_workflow:**
- "Quero ver faculdades de direito" → CHANGE_WORKFLOW, passport_workflow
- "Buscar bolsas na minha cidade" → CHANGE_WORKFLOW, passport_workflow
- "O que é nota de corte?" → CHANGE_WORKFLOW, passport_workflow

📌 **CONTINUIDADE (passport_workflow ativo):**
- Bot: "Para quem você está buscando?" | User: "minha filhinha" → CONTINUE_WORKFLOW
- Bot: "Para quem você está buscando?" | User: "pra mim" → CONTINUE_WORKFLOW
- Bot: "Qual o nome completo?" | User: "Maria da Silva" → CONTINUE_WORKFLOW
- Bot: "Qual a idade?" | User: "17" → CONTINUE_WORKFLOW
- Bot: "Qual programa?" | User: "SISU" → CONTINUE_WORKFLOW
- Qualquer resposta curta quando passport_workflow ativo → CONTINUE_WORKFLOW

**Saída Obrigatória (JSON):**
Você NÃO deve conversar. Apenas retorne um JSON estrito:
{
  "intent": "CHANGE_WORKFLOW" | "CONTINUE_WORKFLOW" | "EXIT_WORKFLOW",
  "target_workflow": "passport_workflow" | null,
  "confidence": "high" | "medium" | "low",
  "reasoning": "Explique com base no HISTÓRICO se é uma continuação/resposta ou mudança."
}
"""

router_agent = LlmAgent(
    model=MODEL_ROUTER,  # Lightweight model for fast intent classification
    name="router_agent",
    description="Classifies user intent to route to the correct workflow.",
    instruction=ROUTER_INSTRUCTION,
    tools=[], # Router does not need tools, it just outputs decision. The System (workflow.py) executes the switch.
    output_key="router_decision"
)

@safe_execution(error_type="router_error", default_return={})
async def execute_router_agent(user_id: str, session_id: str, message_text: str, profile_state: dict, recent_history: str = None) -> dict:
    """
    Executes the router agent logic and returns the decision dictionary.
    """
    # Prepare Context for Router
    router_input_text = f"MENSAGEM ATUAL DO USUÁRIO: {message_text}\n\nESTADO ATUAL:\nactive_workflow: {profile_state.get('active_workflow')}\nonboarding_completed: {profile_state.get('onboarding_completed')}"
    
    if recent_history:
        router_input_text += f"\n\n=== HISTÓRICO RECENTE (Contexto) ===\n{recent_history}\n====================================="

    router_msg = Content(role="user", parts=[Part(text=router_input_text)])
    
    transient_session_service = InMemorySessionService()
    
    # Run Router (Transient)
    await transient_session_service.create_session(
        app_name="router_check",
        session_id=session_id,
        user_id=user_id
    )
    router_runner = Runner(agent=router_agent, app_name="router_check", session_service=transient_session_service)
    router_response = ""
    
    # print(f"!!! [DEBUG ROUTER] Input:\n{router_input_text}")

    async for r_event in router_runner.run_async(user_id=user_id, session_id=session_id, new_message=router_msg):
        if hasattr(r_event, 'text') and r_event.text:
            router_response += r_event.text
        elif hasattr(r_event, 'content') and r_event.content.parts:
            for p in r_event.content.parts:
                if p.text: router_response += p.text
    
    # print(f"!!! [DEBUG ROUTER] Raw Response:\n{router_response}")
    
    # Parse JSON
    return parse_router_json(router_response)

def parse_router_json(text: str) -> dict:
    """Extracts and parses JSON object from text using regex."""
    try:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception as e:
        print(f"[ROUTER PARSE ERROR] {e}")
    return {}
