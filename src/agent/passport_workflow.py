import json
from typing import Any, Dict, Optional, AsyncGenerator
from google.adk.agents import LlmAgent, Agent
from google.genai import types as genai_types
from src.agent.base_workflow import BaseWorkflow
from src.agent.config import MODEL_CHAT, MODEL_REASONING, MODEL_ROUTER
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool

# Phase 1: Greeting is a scripted message to prevent LLM hallucination
PASSPORT_INTRO_MESSAGE = "Oi! Eu sou a Cloudinha 👋\n\nEstou aqui para te ajudar a encontrar oportunidades educacionais que combinem com o seu momento e seus objetivos.\n\nVocê pode conhecer e se candidatar a programas de apoio educacional. Esses programas ajudam estudantes a desenvolver seu potencial ao longo da trajetória escolar. Eles podem oferecer aulas complementares, mentoria, orientação de estudos, desenvolvimento pessoal e, em alguns casos, apoio financeiro. Estou aqui para responder qualquer dúvida que você tiver sobre programas educacionais e sobre o processo de aplicar na plataforma.\n\nPara começar, preciso entender um pouco sobre você. Comece preenchendo o Onboarding ao lado. Com esses dados vamos te indicar em quais programas parceiros que você pode se aplicar"

from src.tools.processDependentChoice import processDependentChoiceTool
from src.tools.lookupCEP import lookupCEPTool
from src.tools.getNextPartnerQuestion import getNextPartnerQuestionTool
from src.tools.savePartnerAnswer import savePartnerAnswerTool
from src.tools.smartResearch import smartResearchTool
from src.tools.getImportantDates import getImportantDatesTool
from src.tools.startStudentApplication import startStudentApplicationTool
from src.tools.rewindWorkflowStatus import rewindWorkflowStatusTool
from src.tools.getPartnerForms import getPartnerFormsTool
from src.tools.getStudentApplication import getStudentApplicationTool
from src.tools.getEligibilityResults import getEligibilityResultsTool

# ============================================================
# BASE INSTRUCTIONS — Common to all agents
# ============================================================

BASE_REASONING_INSTRUCTION = """Você é um especialista em orientação educacional no ecossistema Nubo Hub.
O USER_ID_CONTEXT está sempre disponível para identificação do perfil.

DIRETRIZES PARA TODOS OS AGENTES (SEMPRE ATIVAS):
1. **RESPONDER DÚVIDAS E PESQUISAR**: O estudante pode fazer perguntas sobre prazos, regras de programas parceiros, benefícios ou dúvidas gerais. Você DEVE usar OBRIGATORIAMENTE as ferramentas `smartResearchTool` e `getImportantDatesTool` para responder com precisão. NUNCA se negue a pesquisar.
2. **SILÊNCIO TÉCNICO**: Nunca diga "vou pesquisar", "vou verificar na ferramenta" ou "usando minhas ferramentas". Execute a tool silenciosamente e responda com o resultado.
3. **USO DA smartResearchTool — REGRAS DE program**:
   - Genérica sobre programas ou Nubo → program="programs"
   - Específica sobre um parceiro → program="programs", partner_name="Nome do Parceiro"
   - Sobre Prouni/Sisu → program="prouni" ou "sisu"
   - Sobre a Cloudinha/Assistente → program="cloudinha"
"""

# ============================================================
# REASONING AGENTS — Intent classification + Tool selection/execution by Phase
# ============================================================

ONBOARDING_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Você está na FASE ONBOARDING. O usuário está preenchendo seus dados pessoais em um formulário na tela.

FUNÇÃO TÁTICA:
1. **AUXILIAR NO CADASTRO**: Use `getStudentProfileTool` para ver o que já foi preenchido. Compare com o 'ESTADO ATUAL DO FORMULÁRIO DO USUÁRIO' injetado no contexto. Oriente o preenchimento na UI.
2. **NÃO AVALIE ELEGIBILIDADE AINDA**: Foco em completar o cadastro. Responda dúvidas sobre a plataforma abertamente.
"""

DEPENDENT_ONBOARDING_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Você está na FASE DEPENDENT_ONBOARDING. O usuário está preenchendo os dados do seu dependente (ex: um filho) no formulário ao lado.

FUNÇÃO TÁTICA:
1. **AUXILIAR NO CADASTRO DO DEPENDENTE**: Use `getStudentProfileTool(user_id=ID_DO_DEPENDENTE)` (verifique `current_dependent_id` no perfil) para ver o que já foi salvo. Oriente o preenchimento na UI lateral.
2. **FOCO NO DEPENDENTE**: Responda dúvidas sobre oportunidades para o filho/dependente do usuário com clareza.
"""

ASK_DEPENDENT_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Você está na FASE ASK_DEPENDENT. Queremos saber se a vaga é para o usuário ou para um dependente.

FUNÇÃO TÁTICA:
1. **COORDENAR ESCOLHA**: Se o usuário disser para quem é (ex: "para mim" ou "para minha filha"), use OBRIGATORIAMENTE `processDependentChoiceTool(choice='self'|'dependent')`.
2. **IDADE**: Use `getStudentProfileTool` para ver a idade. Use isso para sugerir as opções de forma contextual.
"""

PROGRAM_MATCH_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Esta é a FASE PROGRAM_MATCH. Os cards de programas parceiros estão na tela.

FUNÇÃO TÁTICA:
1. **LER RESULTADOS**: Use `getEligibilityResultsTool` para buscar os matches calculados.
2. **INICIAR APLICAÇÃO**: Se o estudante escolher um programa (ex: "Quero a Fundação Estudar"), chame IMEDIATAMENTE `startStudentApplicationTool` com o UUID ou Nome do parceiro. Não peça confirmação extra.
3. **RESUMO**: Se o estudante não escolheu, faça um resumo entusiasta das opções elegíveis.
"""




EVALUATE_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Você está na FASE EVALUATE. O edital oficial de um parceiro está aberto na tela para preenchimento.

FUNÇÃO TÁTICA:
1. **MONITORIA DO EDITAL**: Use `getPartnerFormsTool` para ler as regras e `getStudentApplicationTool` para ver o que já foi preenchido.
2. **TRADUZIR BUROCRACIA**: Use `smartResearchTool` junto com as regras do edital para explicar campos complexos ou critérios aos estudantes.
3. **ERROS DE PREENCHIMENTO**: Ajude o estudante a entender erros relatados na UI comparando com o edital.
"""


onboarding_reasoning_agent = LlmAgent(
    model=MODEL_REASONING,
    name="onboarding_reasoning_agent",
    description="Raciocínio para a fase ONBOARDING. Read-only e knowledge tools apenas.",
    instruction=ONBOARDING_REASONING_INSTRUCTION,
    tools=[
        getStudentProfileTool,
        smartResearchTool,
        getImportantDatesTool,
        rewindWorkflowStatusTool,
    ],
)

dependent_onboarding_reasoning_agent = LlmAgent(
    model=MODEL_REASONING,
    name="dependent_onboarding_reasoning_agent",
    description="Raciocínio para a fase DEPENDENT_ONBOARDING. Read-only e knowledge tools focadas no dependente.",
    instruction=DEPENDENT_ONBOARDING_REASONING_INSTRUCTION,
    tools=[
        getStudentProfileTool,
        smartResearchTool,
        getImportantDatesTool,
        rewindWorkflowStatusTool,
    ],
)

ask_dependent_reasoning_agent = LlmAgent(
    model=MODEL_REASONING,
    name="ask_dependent_reasoning_agent",
    description="Raciocínio para a fase ASK_DEPENDENT. Processa a resposta se é para self ou dependent.",
    instruction=ASK_DEPENDENT_REASONING_INSTRUCTION,
    tools=[
        getStudentProfileTool,
        processDependentChoiceTool,
        smartResearchTool,
        getImportantDatesTool,
        rewindWorkflowStatusTool,
    ],
)

program_match_reasoning_agent = LlmAgent(
    model=MODEL_REASONING,
    name="program_match_reasoning_agent",
    description="Raciocínio para a fase PROGRAM_MATCH. Avalia opções e inicia aplicação.",
    instruction=PROGRAM_MATCH_REASONING_INSTRUCTION,
    tools=[
        getStudentProfileTool,
        getEligibilityResultsTool,
        startStudentApplicationTool,
        smartResearchTool,
        getImportantDatesTool,
        rewindWorkflowStatusTool,
    ],
)

evaluate_reasoning_agent = LlmAgent(
    model=MODEL_REASONING,
    name="evaluate_reasoning_agent",
    description="Raciocínio para a fase EVALUATE. Auxilia no preenchimento lendo o edital e a aplicação existente.",
    instruction=EVALUATE_REASONING_INSTRUCTION,
    tools=[
        getPartnerFormsTool,
        getStudentApplicationTool,
        getStudentProfileTool,
        smartResearchTool,
        getImportantDatesTool,
        rewindWorkflowStatusTool,
    ],
)

concluded_agent = LlmAgent(
    model=MODEL_CHAT,
    name="concluded_agent",
    description="Agente para fase CONCLUDED. Lê resultados de elegibilidade, sugere novas aplicações e tira dúvidas.",
    instruction=BASE_REASONING_INSTRUCTION + """
Você está na FASE CONCLUDED. A aplicação atual do estudante foi finalizada e enviada!

FUNÇÃO TÁTICA:
1. **CELEBRAR**: Continue comemorando a conquista!
2. **LER NOVAS OPORTUNIDADES**: Use `getEligibilityResultsTool` para ler os matches calculados pelo sistema.
3. **SUGERIR E INICIAR**: Analise os matches e sugira outros programas. Se o estudante aceitar, use `startStudentApplicationTool` para o `partner_id` correspondente.
""",
    tools=[
        getStudentProfileTool,
        getEligibilityResultsTool,
        startStudentApplicationTool,
        smartResearchTool,
        getImportantDatesTool
    ]
)

# ============================================================
# RESPONSE AGENT — Grounded response synthesis + Proactivity
# ============================================================

RESPONSE_INSTRUCTION = """Você é a Cloudinha, uma assistente educacional empática e clara.

Você recebe um RELATÓRIO TÉCNICO do módulo de raciocínio com dados já coletados pelas ferramentas. Sua ÚNICA função é formular uma resposta natural e útil para o estudante com base nos dados do relatório.

REGRAS ABSOLUTAS:
1. Responda APENAS com base nos dados do RELATÓRIO TÉCNICO e no contexto fornecido.
2. Se o relatório não contém dados suficientes, diga honestamente que não tem essa informação no momento.
3. NUNCA invente dados, estatísticas, datas ou nomes de programas que não estejam no relatório.
4. NUNCA diga "vou pesquisar", "vou verificar", "usando minhas ferramentas" — responda diretamente.
5. NUNCA repita a saudação de boas vindas ("Oi! Eu sou a Cloudinha...").
6. Seja breve, empática e clara. Use emojis com moderação.
7. Quando citar informações, use dados EXATOS do relatório técnico.

ERROS NAS FERRAMENTAS:
- Se o relatório indica que uma ferramenta falhou, adapte a resposta: "Não consegui verificar [X] agora, mas com base no que sei..."
- Não deixe o erro visível ao usuário de forma técnica.

PROATIVIDADE — Ao final da sua resposta:
- Se faz sentido, sugira 1-2 próximos passos relevantes para a fase atual do estudante
- Ou sugira perguntas que o estudante poderia fazer para se aprofundar
- Exemplos: "Quer saber mais sobre [X]?", "O próximo passo seria [Y] — posso te ajudar com isso!"
- NÃO seja proativo se a resposta já for uma orientação de próximo passo (evite redundância)
- NÃO sugira mais de 2 opções para não sobrecarregar
- NÃO seja proativo em respostas de ação do workflow (ex: processar escolha de dependente)

CONTEXTO DA FASE:
- ONBOARDING: Incentive o preenchimento do formulário ao lado
- ASK_DEPENDENT: Use a idade do estudante para ser inteligente.
  - Se idade < 18: "Vi aqui que você tem [X] anos, acredito que está buscando para você mesmo, né? Ou seria para um irmão ou parente?"
  - Se idade >= 18: "Vi aqui que você tem [X] anos, você está buscando oportunidades para você mesmo ou para um filho ou parente?"
  - Sempre ofereça as opções de forma gentil e empática.
- PROGRAM_MATCH: Apresente resultados de elegibilidade com entusiasmo
- EVALUATE: Ajude com dúvidas sobre campos do formulário do parceiro
- CONCLUDED: Parabenize e tire dúvidas finais
- DEPENDENT_ONBOARDING: Ajude com dúvidas sobre os campos do dependente

TOM DE VOZ:
- Empática e acolhedora
- Linguagem simples e acessível
- Breve — respostas longas cansam
- Incentivadora sem ser invasiva
"""


response_agent = LlmAgent(
    model=MODEL_CHAT,
    name="response_agent",
    description="Sintetiza resposta final com base no output estruturado do Reasoning Agent.",
    instruction=RESPONSE_INSTRUCTION,
    tools=[],  # NENHUMA tool — grounded by design
)


class PassportWorkflow(BaseWorkflow):
    @property
    def name(self) -> str:
        return "passport_workflow"

    def get_agent_for_user(self, user_id: str, current_state: Dict[str, Any]) -> Optional[Agent]:
        passport_phase = current_state.get("passport_phase") or "INTRO"
        
        # Phase 1: Greeting
        if passport_phase == "INTRO":
            return {
                "type": "scripted", 
                "name": "passport_intro",
                "message": PASSPORT_INTRO_MESSAGE
            }
            
        # Phase 2-5: Active phases use Reasoning → Response pipeline
        if passport_phase in ["ONBOARDING", "ASK_DEPENDENT", "DEPENDENT_ONBOARDING", "PROGRAM_MATCH", "EVALUATE"]:
            
            # Select the specialized reasoning agent based on phase
            if passport_phase == "ONBOARDING":
                active_reasoning = onboarding_reasoning_agent
            elif passport_phase == "ASK_DEPENDENT":
                active_reasoning = ask_dependent_reasoning_agent
            elif passport_phase == "DEPENDENT_ONBOARDING":
                active_reasoning = dependent_onboarding_reasoning_agent
            elif passport_phase == "PROGRAM_MATCH":
                active_reasoning = program_match_reasoning_agent
            elif passport_phase == "EVALUATE":
                active_reasoning = evaluate_reasoning_agent
            else:
                active_reasoning = onboarding_reasoning_agent # fallback
                
            return {
                "type": "reasoning_response",
                "name": f"{passport_phase.lower()}_reasoning_response_pipeline",
                "reasoning_agent": active_reasoning,
                "response_agent": response_agent,
            }
        
        # Phase 6: Concluded — still uses single agent (read-only, simpler needs)
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
            upd["_is_turn_complete"] = True
            
        elif passport_phase == "ASK_DEPENDENT":
            # Re-read the DB to check if processDependentChoiceTool already ran
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "ASK_DEPENDENT")
            
            if new_phase != "ASK_DEPENDENT":
                upd["passport_phase"] = new_phase
            upd["_is_turn_complete"] = True

        elif passport_phase == "DEPENDENT_ONBOARDING":
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
                    upd["passport_phase"] = "PROGRAM_MATCH"
            upd["_is_turn_complete"] = True
        
        elif passport_phase == "PROGRAM_MATCH":
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "PROGRAM_MATCH")
            
            if new_phase != "PROGRAM_MATCH":
                upd["passport_phase"] = new_phase
            upd["_is_turn_complete"] = True
            
        elif passport_phase == "EVALUATE":
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "EVALUATE")
            
            if new_phase != "EVALUATE":
                upd["passport_phase"] = new_phase
            upd["_is_turn_complete"] = True
        
        elif passport_phase == "CONCLUDED":
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "CONCLUDED")
            
            if new_phase != "CONCLUDED":
                upd["passport_phase"] = new_phase
            upd["_is_turn_complete"] = True
                 
        return upd if upd else None
