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
1. `match_workflow`: O usuário quer **BUSCAR/VER/FILTRAR** faculdades ou bolsas (AÇÃO).
2. `sisu_workflow`: O usuário tem **DÚVIDAS** sobre regras, datas, funcionamento do SISU (INFORMAÇÃO).
3. `prouni_workflow`: O usuário tem **DÚVIDAS** sobre regras, datas, funcionamento do PROUNI (INFORMAÇÃO).
4. `None` (Root Agent): Conversa casual, "Oi", "Obrigado", ou **PERGUNTAS TÉCNICAS** sobre o próprio bot ("Como funciona?", "Arquitetura").

**DIFERENCIAÇÃO CRÍTICA - Intenção ACIONAL vs INFORMACIONAL vs META:**

🎯 **ACIONAL** → `match_workflow` (verbos de busca/seleção):
   - "Quero VER vagas"
   - "Me MOSTRE oportunidades"
   - "BUSCAR faculdades"
   - "ENCONTRAR bolsas"
   - "Quais são as MELHORES OPORTUNIDADES"
   - "CALCULAR minhas chances"
   - "Estou procurando curso de X"
   
   ⚠️ **IMPORTANTE**: Mesmo que a mensagem contenha "SISU" ou "PROUNI", se a intenção é BUSCAR/VER vagas, vá para `match_workflow`:
   - ✅ "Quero as melhores oportunidades do SISU" → `match_workflow` (buscar vagas públicas)
   - ✅ "Me mostre bolsas do PROUNI" → `match_workflow` (buscar bolsas privadas)
   - ✅ "Vagas de medicina no SISU" → `match_workflow` (buscar curso específico)

❓ **INFORMACIONAL** → `sisu_workflow` ou `prouni_workflow` (perguntas conceituais):
   - "O que É o SISU?"
   - "COMO FUNCIONA a nota de corte?"
   - "QUANDO abrem as inscrições?"
   - "Quais são as REGRAS de renda do PROUNI?"
   - "Como faço para me INSCREVER?"
   - "O que são cotas?"
   - "Qual a DIFERENÇA entre integral e parcial?"

🛠️ **TÉCNICO / META** → `None` (Root Agent):
   - "Como você funciona?"
   - "Qual sua arquitetura?"
   - "Explique seu fluxo técnico"
   - "Quem te criou?"
   - "Leia sua documentação técnica"

**Regras de Decisão:**
- **MUDANÇA IMPLÍCITA**: Se o usuário está em um workflow mas muda o tipo de intenção:
    - De ação (match) para dúvida → `sisu_workflow` ou `prouni_workflow`
    - De dúvida para ação → `match_workflow`
    - De qualquer um para Técnico/Meta → `None` (EXIT_WORKFLOW se já estiver em um, ou apenas target null)
    
- **CONTINUIDADE (CRÍTICO - ANALISE O HISTÓRICO)**:
    - **LEIA O HISTÓRICO DE MENSAGENS FORNECIDO**.
    - Se a **ÚLTIMA MENSAGEM DO BOT** foi uma pergunta, e a mensagem ATUAL do usuário é a RESPOSTA, mantenha o workflow (`CONTINUE_WORKFLOW`).
    - Ex: 
      Bot: "Que curso você quer?" 
      Usuário: "Arquitetura" 
      -> `CONTINUE_WORKFLOW`.
    - Ex:
      Bot: "Qual sua nota?"
      Usuário: "600"
      -> `CONTINUE_WORKFLOW`.

- **SAÍDA**: "Sair", "Cancelar", "Voltar" → `EXIT_WORKFLOW`.

**Exemplos Práticos:**

📌 **ACIONAL → match_workflow:**
- "Quero ver faculdades de direito" → CHANGE_WORKFLOW, match_workflow
- "Buscar bolsas na minha cidade" → CHANGE_WORKFLOW, match_workflow

📌 **INFORMACIONAL → sisu/prouni_workflow:**
- "O que é nota de corte?" → CHANGE_WORKFLOW, sisu_workflow
- "Como funciona a lista de espera do PROUNI?" → CHANGE_WORKFLOW, prouni_workflow

📌 **CONTINUIDADE (OLHANDO HISTÓRICO):**
- Histórico Bot: "Qual seu curso?" | Atual User: "Direito" → CONTINUE_WORKFLOW
- Histórico Bot: "Qual sua renda?" | Atual User: "1500" → CONTINUE_WORKFLOW

**Saída Obrigatória (JSON):**
Você NÃO deve conversar. Apenas retorne um JSON estrito:
{
  "intent": "CHANGE_WORKFLOW" | "CONTINUE_WORKFLOW" | "EXIT_WORKFLOW",
  "target_workflow": "match_workflow" | "sisu_workflow" | "prouni_workflow" | null,
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
