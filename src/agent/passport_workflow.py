import json
from typing import Any, Dict, Optional, AsyncGenerator
from google.adk.agents import LlmAgent, Agent
from src.agent.base_workflow import BaseWorkflow
from src.agent.config import MODEL_ONBOARDING, MODEL_ROUTER
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool

# Phase 1: Greeting is a scripted message to prevent LLM hallucination
PASSPORT_INTRO_MESSAGE = "Oi! Eu sou a Cloudinha 👋\n\nEstou aqui para te ajudar a encontrar oportunidades educacionais que combinem com o seu momento e seus objetivos.\n\nVocê pode conhecer e se candidatar a programas de apoio educacional. Esses programas ajudam estudantes a desenvolver seu potencial ao longo da trajetória escolar. Eles podem oferecer aulas complementares, mentoria, orientação de estudos, desenvolvimento pessoal e, em alguns casos, apoio financeiro. Estou aqui para responder qualquer dúvida que você tiver sobre programas educacionais e sobre o processo de aplicar na plataforma.\n\nPara começar, preciso entender um pouco sobre você. Comece preenchendo o Onboarding ao lado. Com esses dados vamos te indicar em quais programas parceiros que você pode se aplicar"

from src.tools.processDependentChoice import processDependentChoiceTool

# (Removed passport_ask_dependent in favor of unified passei_agent)

# Agent 2.5: Dependent Onboarding — collect dependent's info
DEPENDENT_ONBOARDING_INSTRUCTION = """Você é a Cloudinha coletando dados de um DEPENDENTE.

IMPORTANTE: O ID do dependente é fornecido como DEPENDENT_ID_CONTEXT no início desta instrução.
Use ESSE ID (não o USER_ID_CONTEXT) como user_id ao chamar updateStudentProfileTool.

CAMPOS NECESSÁRIOS (5 no total):
1. Nome completo → updates: {{"full_name": "valor"}}
2. Idade → updates: {{"age": valor_numerico}}
3. Grau de parentesco → updates: {{"relationship": "valor"}}
4. Cidade → updates: {{"city_name": "valor"}}
5. Escolaridade → updates: {{"education": "valor"}}

SEU FLUXO OBRIGATÓRIO A CADA TURNO:
1. Chame getStudentProfileTool(user_id=DEPENDENT_ID_CONTEXT) para ver quais campos JÁ estão preenchidos.
2. LEIA O HISTÓRICO DA CONVERSA. Se o usuário já forneceu alguma informação na MENSAGEM ATUAL ou em mensagens anteriores que ainda NÃO foi salva, SALVE IMEDIATAMENTE com updateStudentProfileTool.
3. Pergunte APENAS o PRÓXIMO campo que ainda está vazio.
4. Se todos os 5 campos estiverem preenchidos, diga: "Perfeito! Dados do dependente cadastrados com sucesso! ✅"

EXEMPLOS:
- Se o histórico mostra que o bot perguntou "Qual o nome?" e o usuário respondeu "Maria Silva" → SALVE {{"full_name": "Maria Silva"}} e pergunte a idade.
- Se o perfil já tem full_name e age preenchidos → pergunte o grau de parentesco.
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

from src.tools.smartResearch import smartResearchTool
from src.tools.getImportantDates import getImportantDatesTool
from src.tools.startStudentApplication import startStudentApplicationTool
from src.tools.rewindWorkflowStatus import rewindWorkflowStatusTool

# Agent 3: Unified Passei Agent (active phases: ONBOARDING, ASK_DEPENDENT, PROGRAM_MATCH, EVALUATE, DEPENDENT_ONBOARDING)
passei_agent = LlmAgent(
    model=MODEL_ROUTER,
    name="passei_agent",
    description="Agente principal do Passei Workflow. Guia o candidato pelas fases da aplicação.",
    instruction="""Você é a Cloudinha, auxiliando o candidato nos programas educacionais por meio do fluxo 'Passei Workflow'.
    
    O user_id está disponível no início desta instrução como USER_ID_CONTEXT. Use esse valor ao chamar TODAS as ferramentas.
    O estado atual do formulário na tela do usuário ESTÁ INJETADO NO PROMPT (como ESTADO ATUAL DO FORMULÁRIO DO USUÁRIO PENDENTE DE SALVAMENTO).
    
    REGRA CRÍTICA — RESPONDA USANDO A BASE DE CONHECIMENTO:
    Acima desta instrução foi injetada uma BASE DE CONHECIMENTO com documentação sobre o fluxo do passaporte e sobre programas educacionais.
    Quando o estudante fizer QUALQUER pergunta (sobre o processo, formulários, programas, etapas, o que é onboarding, como funciona, etc.):
    → PRIMEIRO: Consulte a BASE DE CONHECIMENTO acima para formular uma resposta precisa e informativa.
    → SEGUNDO: Se precisar de informações ESPECÍFICAS de um parceiro (Fundação Estudar, Instituto Ponte, Programa Aurora), chame smartResearchTool(target_program="programs", partner_name="...").
    → TERCEIRO: Após responder a dúvida, incentive gentilmente o estudante a continuar o fluxo atual.
    NUNCA responda "de cabeça" ignorando a BASE DE CONHECIMENTO. NUNCA dê respostas vagas como "preencha o formulário ao lado" sem antes responder a pergunta de fato.
    
    SEU OBJETIVO DE ACORDO COM A FASE ('passport_phase' no perfil do estudante):
    
    1. Fase ONBOARDING: O usuário está preenchendo os dados básicos no painel ao lado. Se ele fizer uma pergunta, RESPONDA usando a BASE DE CONHECIMENTO. Depois, incentive-o a continuar o preenchimento. Não apenas redirecione — explique o que ele precisa saber.
    
    2. Fase ASK_DEPENDENT: Verifique a 'age' (idade) do estudante no PROFILE dele usando a getStudentProfileTool.
       - Se a idade for MAIOR ou IGUAL a 18 anos, pergunte: "Você está buscando aplicar para si próprio ou para outra pessoa?". Aguarde a resposta. Avalie a intenção e ative a ferramenta `processDependentChoiceTool` com a escolha.
       - Se a idade for MENOR que 18 anos, você já sabe que é para o próprio estudante (não pode aplicar para dependente). Avise gentilmente: "Como você tem menos de 18 anos, vamos seguir com a sua própria aplicação, tudo bem?". Em seguida, e SEM aguardar a resposta do usuário, chame IMEDIATAMENTE a ferramenta `processDependentChoiceTool` com a opção "self" para avançar o fluxo para PROGRAM_MATCH. Nunca trave nesta fase.
    
    3. Fase PROGRAM_MATCH: Você é o HOST nesta fase!
       - PRIMEIRO: Chame `evaluatePassportEligibilityTool(user_id=USER_ID_CONTEXT)` para obter os programas elegíveis.
       - SEGUNDO: Apresente os resultados ao usuário de forma entusiasmada: "Analisei seu perfil! Encontrei X programas parceiros em que você atende aos requisitos. Dá uma olhada neles e me diz qual chamou mais sua atenção."
       - TERCEIRO: Quando o usuário indicar verbalmente qual programa quer, CONFIRME com ele antes de prosseguir: "Você quer se inscrever no programa [nome]? Posso iniciar sua aplicação agora."
       - QUARTO: Após confirmação, chame `startStudentApplicationTool(user_id=USER_ID_CONTEXT, partner_id=ID_DO_PARCEIRO)`.
       - NÃO pule etapas. Sempre confirme antes de chamar startStudentApplicationTool.
    
    4. Fase EVALUATE: O usuário está preenchendo um formulário do parceiro no painel ao lado. Responda dúvidas específicas sobre os campos da tela. Use `smartResearchTool` para buscar informações do edital do parceiro específico. Use `getImportantDatesTool` se precisar de datas. Motive o usuário a finalizar o formulário.
    
    5. Fase DEPENDENT_ONBOARDING: O usuário está cadastrando dados de outra pessoa no painel ao lado. Ajude tirando dúvidas sobre os campos.
    
    6. CORREÇÃO/REINÍCIO (VÁLVULA DE ESCAPE): Se o usuário disser peremptoriamente "errei algo antes", "quero mudar minha resposta anterior", "quero recomeçar", etc, chame `rewindWorkflowStatusTool`.
    
    USO DA smartResearchTool — REGRAS DE target_program:
    Atenção: NÃO use para dúvidas gerais de passaporte (essas já estão na BASE DE CONHECIMENTO acima). Use APENAS se a BASE não for suficiente:
    - Se a dúvida é ESPECÍFICA sobre um parceiro (Fundação Estudar, Instituto Ponte, Programa Aurora / Instituto Sol):
      → Chame smartResearchTool(query="...", target_program="programs", partner_name="Nome do Parceiro")
      Exemplos de partner_name: "Fundação Estudar", "Instituto Ponte", "Programa Aurora"
    - Se a dúvida é sobre Prouni ou Sisu:
      → Chame smartResearchTool(query="...", target_program="prouni") ou target_program="sisu"
    - Se a dúvida é sobre a Cloudinha (quem é, como funciona):
      → Chame smartResearchTool(query="...", target_program="cloudinha")
    
    MUITO IMPORTANTE: 
    - Seja sempre breve, empático e claro.
    - NUNCA repita a mensagem de saudação/intro ("Oi! Eu sou a Cloudinha..."). Ela já foi enviada antes. Responda DIRETO a pergunta.
    - Quando o estudante perguntar algo, RESPONDA com detalhes da BASE DE CONHECIMENTO. Cite etapas específicas, parceiros por nome, etc. Respostas genéricas são PROIBIDAS.
    - Se a BASE DE CONHECIMENTO não cobrir o assunto, chame smartResearchTool para buscar informações adicionais.
    - Se o assunto for sobre um parceiro específico, chame smartResearchTool(target_program="programs", partner_name="...") para obter detalhes do edital.
    - Após responder a dúvida, incentive gentilmente o estudante a continuar o fluxo.
    - Não gere falsas esperanças nem crie exigências que não existem nos documentos consultados.
    """,
    tools=[
        getStudentProfileTool,
        processDependentChoiceTool,
        evaluatePassportEligibilityTool, 
        getNextPartnerQuestionTool, 
        savePartnerAnswerTool,
        startStudentApplicationTool,
        rewindWorkflowStatusTool,
        smartResearchTool,
        getImportantDatesTool
    ]
)

# Agent 4: Concluded Agent — read-only, no DB mutations (doc item 22)
concluded_agent = LlmAgent(
    model=MODEL_ROUTER,
    name="concluded_agent",
    description="Agente para fase CONCLUDED. Apenas tira dúvidas, sem mutações no banco.",
    instruction="""Você é a Cloudinha. O usuário já CONCLUIU sua aplicação no programa educacional. Parabéns! 🎉
    
    O user_id está disponível no início desta instrução como USER_ID_CONTEXT.
    
    NESTA FASE:
    - Você pode responder dúvidas usando `smartResearchTool` e `getImportantDatesTool`.
    - Você NÃO DEVE executar nenhuma ferramenta que altere o banco de dados. Nenhuma mutação é permitida.
    - Seja gentil, parabenize o usuário, e responda o que for perguntado sobre programas, datas, etc.
    
    USO DA smartResearchTool — REGRAS DE target_program:
    - Genérica sobre programas educacionais → target_program="passport"
    - Específica sobre parceiro → target_program="programs", partner_name="Nome"
    - Prouni/Sisu → target_program="prouni" ou "sisu"
    - Sobre a Cloudinha → target_program="cloudinha"
    """,
    tools=[
        smartResearchTool,
        getImportantDatesTool,
        getStudentProfileTool
    ]
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
             return passei_agent

        # Phase 3: Ask Dependent
        if passport_phase == "ASK_DEPENDENT":
            return passei_agent

        # Phase 3.5: Dependent Onboarding — collect dependent's info
        if passport_phase == "DEPENDENT_ONBOARDING":
            dependent_id = current_state.get("current_dependent_id")
            if dependent_id:
                return _create_dependent_onboarding_agent(dependent_id)
            return None  # Should not happen

        # Phase 4: Program Match & Evaluate — active agent
        if passport_phase in ["PROGRAM_MATCH", "EVALUATE"]:
            return passei_agent
        
        # Phase 5: Concluded — read-only agent (no DB mutations per doc item 22)
        if passport_phase == "CONCLUDED":
            return concluded_agent
            
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
            upd["_is_turn_complete"] = True
            
        elif passport_phase == "ONBOARDING":
            fresh_state = getStudentProfileTool(user_id)
            if fresh_state.get("onboarding_completed"):
                upd["passport_phase"] = "ASK_DEPENDENT"
                # Not setting _is_turn_complete allows ASK_DEPENDENT agent to be executed in the same turn if the user chatted.
            else:
                upd["_is_turn_complete"] = True
            
        elif passport_phase == "ASK_DEPENDENT":
            # Re-read the DB to check if processDependentChoiceTool already ran
            # (it sets passport_phase to DEPENDENT_ONBOARDING or PROGRAM_MATCH)
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "ASK_DEPENDENT")
            
            if new_phase != "ASK_DEPENDENT":
                # Tool was called! Update local state and let the loop continue
                # to immediately run the next agent (DEPENDENT_ONBOARDING or PROGRAM_MATCH)
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
                    # Doc item 14: after dependent onboarding → PROGRAM_MATCH (not EVALUATE)
                    upd["passport_phase"] = "PROGRAM_MATCH"
            # Always end turn — wait for user input
            upd["_is_turn_complete"] = True
        
        elif passport_phase == "PROGRAM_MATCH":
            # Re-read DB to check if startStudentApplicationTool already ran
            # (it would have advanced the phase to EVALUATE via the tool itself or via agent)
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "PROGRAM_MATCH")
            
            if new_phase != "PROGRAM_MATCH":
                # Tool was called and phase was advanced — sync local state
                upd["passport_phase"] = new_phase
            # Always end turn — wait for next user interaction
            upd["_is_turn_complete"] = True
            
        elif passport_phase == "EVALUATE":
            # Re-read DB to check if phase was advanced to CONCLUDED by the frontend
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "EVALUATE")
            
            if new_phase != "EVALUATE":
                upd["passport_phase"] = new_phase
            upd["_is_turn_complete"] = True
        
        elif passport_phase == "CONCLUDED":
            upd["_is_turn_complete"] = True
                 
        return upd if upd else None
