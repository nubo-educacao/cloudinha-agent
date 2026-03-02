import json
from typing import Any, Dict, Optional, AsyncGenerator
from google.adk.agents import LlmAgent, Agent
from src.agent.base_workflow import BaseWorkflow
from src.agent.onboarding_workflow import onboarding_workflow, check_profile_complete
from src.agent.config import MODEL_ONBOARDING, MODEL_ROUTER
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool

# Phase 1: Greeting is a scripted message to prevent LLM hallucination
PASSPORT_INTRO_MESSAGE = "Programas educacionais são muito importantes e eu vou te ajudar a encontrar a melhor opção! 🌟"

from src.tools.processDependentChoice import processDependentChoiceTool

# Agent 2: Ask for dependent
passport_ask_dependent = LlmAgent(
    model=MODEL_ROUTER,
    name="passport_ask_dependent",
    description="Asks if the application is for the user or someone else.",
    instruction="""Você é a Cloudinha. O usuário já completou o cadastro básico.
    Agora, pergunte a ele: "Você está buscando aplicar para si próprio ou para outra pessoa (filho, cônjuge, etc)?"
    
    Aguarde a resposta. Assim que ele responder, use a ferramenta processDependentChoiceTool.
    O user_id está disponível no início desta instrução como USER_ID_CONTEXT. Use esse valor.
    
    INTERPRETAÇÃO DA RESPOSTA (use seu julgamento):
    → choice="self" se a resposta indicar que é PARA ELE MESMO:
      "pra mim", "eu mesmo", "para mim", "sim, pra mim", "próprio", "eu"
    
    → choice="dependent" se a resposta indicar que é PARA OUTRA PESSOA:
      "minha filha", "meu filho", "filhinha", "pro meu filho", "outra pessoa",
      "minha esposa", "meu marido", "meu irmão", "minha mãe", "dependente",
      "é pra outra pessoa", "não é pra mim"
    
    DEPOIS de chamar a ferramenta, confirme a escolha:
    Se dependente: "Entendi! Vou precisar dos dados da pessoa para quem você está aplicando. 📝"
    Se self: "Perfeito! Vamos verificar os programas disponíveis para você! 🚀"
    
    MUITO IMPORTANTE: Não avance a conversa sem usar a ferramenta.
    """,
    tools=[processDependentChoiceTool]
)

# Agent 2.5: Dependent Onboarding — collect dependent's info
DEPENDENT_ONBOARDING_INSTRUCTION = """Você é a Cloudinha coletando dados de um DEPENDENTE.

IMPORTANTE: O ID do dependente é fornecido como DEPENDENT_ID_CONTEXT no início desta instrução.
Use ESSE ID (não o USER_ID_CONTEXT) como user_id ao chamar updateStudentProfileTool.

CAMPOS NECESSÁRIOS (4 no total):
1. Nome completo → updates: {{"full_name": "valor"}}
2. Idade → updates: {{"age": valor_numerico}}
3. Cidade → updates: {{"city_name": "valor"}}
4. Escolaridade → updates: {{"education": "valor"}}

SEU FLUXO OBRIGATÓRIO A CADA TURNO:
1. Chame getStudentProfileTool(user_id=DEPENDENT_ID_CONTEXT) para ver quais campos JÁ estão preenchidos.
2. LEIA O HISTÓRICO DA CONVERSA. Se o usuário já forneceu alguma informação na MENSAGEM ATUAL ou em mensagens anteriores que ainda NÃO foi salva, SALVE IMEDIATAMENTE com updateStudentProfileTool.
3. Pergunte APENAS o PRÓXIMO campo que ainda está vazio.
4. Se todos os 4 campos estiverem preenchidos, diga: "Perfeito! Dados do dependente cadastrados com sucesso! ✅"

EXEMPLOS:
- Se o histórico mostra que o bot perguntou "Qual o nome?" e o usuário respondeu "Maria Silva" → SALVE {{"full_name": "Maria Silva"}} e pergunte a idade.
- Se o perfil já tem full_name e age preenchidos → pergunte a cidade.
- Se tudo preenchido → confirme sucesso.

REGRA CRÍTICA: SEMPRE chame a ferramenta updateStudentProfileTool ANTES de perguntar o próximo campo.
Nunca re-pergunte algo que já foi respondido.
"""
from src.tools.lookupCEP import lookupCEPTool

def _create_dependent_onboarding_agent(dependent_id: str) -> LlmAgent:
    """Creates a dynamic agent instance with the dependent_id injected."""
    return LlmAgent(
        model=MODEL_ONBOARDING,
        name="passport_dependent_onboarding_agent",
        description="Collects the dependent's profile information.",
        instruction=f"DEPENDENT_ID_CONTEXT: {dependent_id}\n" + DEPENDENT_ONBOARDING_INSTRUCTION,
        tools=[updateStudentProfileTool, getStudentProfileTool, lookupCEPTool]
    )

from src.tools.evaluatePassportEligibility import evaluatePassportEligibilityTool
from src.tools.getNextPartnerQuestion import getNextPartnerQuestionTool
from src.tools.savePartnerAnswer import savePartnerAnswerTool

# Agent 3: Eligibility & Forms Iterator
passport_iteration_agent = LlmAgent(
    model=MODEL_ROUTER,
    name="passport_iteration_agent",
    description="Iterates over partner criteria and asks missing mapping_source information.",
    instruction="""Você é a Cloudinha e está coletando os dados do candidato para uma aplicação educacional.
    
    O user_id está disponível no início desta instrução como USER_ID_CONTEXT. Use esse valor ao chamar TODAS as ferramentas.
    
    Primeiro, use a ferramenta evaluatePassportEligibilityTool com o user_id para verificar os critérios e sugerir um programa (partner_id).
    
    Depois que o usuário escolher um programa ou se o parceiro já estiver definido, use getNextPartnerQuestionTool com o user_id e partner_id para buscar a próxima pergunta do formulário a ser feita.
    Faça a PRÓXIMA pergunta necessária ao usuário de forma clara e amigável.
    
    Quando o usuário responder, ANTES de perguntar a próxima, OBRIGATORIAMENTE salve a resposta usando savePartnerAnswerTool.
    Não deduza respostas, pergunte.
    
    Quando getNextPartnerQuestionTool retornar "completed", informe ao usuário quantos critérios ele atendeu, diga que a aplicação foi finalizada e pergunte se ele deseja avaliar outro programa.
    """,
    tools=[evaluatePassportEligibilityTool, getNextPartnerQuestionTool, savePartnerAnswerTool]
)

class PassportWorkflow(BaseWorkflow):
    @property
    def name(self) -> str:
        return "passport_workflow"

    def get_agent_for_user(self, user_id: str, current_state: Dict[str, Any]) -> Optional[Agent]:
        passport_phase = current_state.get("passport_phase", "INTRO")
        
        # Phase 1: Greeting
        if passport_phase == "INTRO":
            return {
                "type": "scripted", 
                "name": "passport_intro",
                "message": PASSPORT_INTRO_MESSAGE
            }
            
        # Phase 2: Onboarding Hook
        if passport_phase == "ONBOARDING":
             if not current_state.get("onboarding_completed"):
                  return onboarding_workflow.get_agent_for_user(user_id, current_state)
             else:
                  pass  # Fall through to next if-check

        # Phase 3: Ask Dependent
        if passport_phase == "ASK_DEPENDENT":
            return passport_ask_dependent

        # Phase 3.5: Dependent Onboarding — collect dependent's info
        if passport_phase == "DEPENDENT_ONBOARDING":
            dependent_id = current_state.get("current_dependent_id")
            if dependent_id:
                return _create_dependent_onboarding_agent(dependent_id)
            return None  # Should not happen

        # Phase 4: Iterator / Evaluate
        if passport_phase == "EVALUATE":
            return passport_iteration_agent
            
        return None

    def transform_event(self, event: Any, agent_name: str) -> Optional[Any]:
        return event

    async def on_runner_start(self, agent: Agent) -> AsyncGenerator[Any, None]:
        if False: yield
        return

    def handle_step_completion(self, user_id: str, current_state: Dict[str, Any], step_output: str) -> Optional[Dict[str, Any]]:
        passport_phase = current_state.get("passport_phase", "INTRO")
        
        upd = {}
        
        if passport_phase == "INTRO":
            if not current_state.get("onboarding_completed"):
                upd["passport_phase"] = "ONBOARDING"
            else:
                upd["passport_phase"] = "ASK_DEPENDENT"
            
        elif passport_phase == "ONBOARDING":
            onb_updates = onboarding_workflow.handle_step_completion(user_id, current_state, step_output)
            if onb_updates:
                upd.update(onb_updates)
            if current_state.get("onboarding_completed") or (onb_updates and onb_updates.get("onboarding_completed")):
                upd["passport_phase"] = "ASK_DEPENDENT"
                upd["active_workflow"] = "passport_workflow"
            else:
                upd["_is_turn_complete"] = True
            
        elif passport_phase == "ASK_DEPENDENT":
            # Re-read the DB to check if processDependentChoiceTool already ran
            # (it sets passport_phase to DEPENDENT_ONBOARDING or EVALUATE)
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "ASK_DEPENDENT")
            
            if new_phase != "ASK_DEPENDENT":
                # Tool was called! Update local state and let the loop continue
                # to immediately run the next agent (DEPENDENT_ONBOARDING or EVALUATE)
                upd["passport_phase"] = new_phase
                # DON'T set _is_turn_complete — let the loop pick up the next agent
            else:
                # Tool wasn't called yet (agent just asked the question).
                # End the turn and wait for user's answer.
                upd["_is_turn_complete"] = True

        elif passport_phase == "DEPENDENT_ONBOARDING":
            # Check if the DEPENDENT's profile is complete (not the parent's)
            dependent_id = current_state.get("current_dependent_id")
            if dependent_id:
                dep_state = getStudentProfileTool(dependent_id)
                dep_complete = bool(
                    dep_state.get("full_name") and
                    dep_state.get("age") is not None and
                    dep_state.get("registered_city_name") and
                    dep_state.get("education")
                )
                
                if dep_complete:
                    upd["passport_phase"] = "EVALUATE"
            # Always end turn — wait for user input
            upd["_is_turn_complete"] = True
            
        elif passport_phase == "EVALUATE":
            upd["_is_turn_complete"] = True
                 
        return upd if upd else None
