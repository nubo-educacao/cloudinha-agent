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

def _create_dependent_onboarding_agent(dependent_id: str) -> LlmAgent:
    """Creates a dynamic agent instance with the dependent_id injected."""
    return LlmAgent(
        model=MODEL_CHAT,
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
from src.tools.getPartnerForms import getPartnerFormsTool


# ============================================================
# REASONING AGENT — Intent classification + Tool selection/execution
# ============================================================

REASONING_INSTRUCTION = """Você é o módulo de raciocínio da Cloudinha. Sua função é ANALISAR a mensagem do usuário, ENTENDER a intenção, e usar suas FERRAMENTAS para coletar dados relevantes.

VOCÊ NÃO GERA A RESPOSTA FINAL PARA O USUÁRIO. Outro agente fará isso. Sua função é:
1. Entender a intenção do usuário
2. CHAMAR AS FERRAMENTAS necessárias para obter dados
3. Depois de usar as ferramentas, fazer um RESUMO TÉCNICO do que encontrou

O user_id está disponível como USER_ID_CONTEXT no início deste prompt.

CONTEXTO DISPONÍVEL (injetado automaticamente):
- PERFIL DO ESTUDANTE: dados como nome, idade, cidade, fase, etc.
- FASE ATUAL (passport_phase): ONBOARDING, ASK_DEPENDENT, PROGRAM_MATCH, EVALUATE, etc.
- HISTÓRICO DA CONVERSA: últimas mensagens para entender referências implícitas
- ESTADO DO FORMULÁRIO: campos preenchidos e campo em foco (quando aplicável)

REGRA CRÍTICA: SEMPRE CHAME PELO MENOS UMA FERRAMENTA. Nunca responda sem buscar dados.
Se a pergunta é sobre programas → chame smartResearchTool
Se é sobre datas → chame getImportantDatesTool
Se é sobre um campo do formulário → chame getPartnerFormsTool
Se é sobre elegibilidade → chame evaluatePassportEligibilityTool
Se é uma ação do workflow → chame a tool correspondente (processDependentChoiceTool, etc.)
Se não sabe qual usar → chame smartResearchTool com o tópico da pergunta

REGRAS DE USO DAS FERRAMENTAS:

1. smartResearchTool — Para buscar informações na base de conhecimento:
   - Dúvida sobre programas educacionais em geral → program="programs"
   - Dúvida sobre parceiro específico → program="programs", partner_name="Nome Completo"
   - Dúvida sobre o fluxo/processo do passaporte → program="passport"
   - Dúvida sobre Prouni → program="prouni"
   - Dúvida sobre Sisu → program="sisu"
   - Dúvida sobre a Cloudinha → program="cloudinha"

2. evaluatePassportEligibilityTool — Para avaliar elegibilidade:
   - Só use quando o usuário quiser saber quais programas se adequa
   - Parâmetro: user_id=USER_ID_CONTEXT

3. getImportantDatesTool — Para prazos e datas:
   - Dúvida sobre datas de parceiros → program_type="partners"
   - Dúvida sobre datas do Prouni → program_type="prouni"
   - Dúvida sobre datas do Sisu → program_type="sisu"

4. getPartnerFormsTool — Para campos do formulário de um parceiro:
   - Quando o usuário pergunta sobre um campo específico do formulário
   - Parâmetro: partner_id (UUID do parceiro, extraído do contexto/perfil)

5. getStudentProfileTool — Para consultar o perfil do estudante:
   - Quando precisa de dados atualizados do perfil

6. processDependentChoiceTool — Para fase ASK_DEPENDENT:
   - Quando o usuário responde se busca oportunidade para si ou para outra pessoa
   - Parâmetro: user_id, choice ("self" ou "dependent")

7. startStudentApplicationTool — Para iniciar aplicação em um parceiro:
   - Apenas na fase PROGRAM_MATCH, após confirmação do usuário
   - Parâmetros: user_id, partner_id

8. rewindWorkflowStatusTool — Válvula de escape:
   - Quando o usuário quer recomeçar ou corrigir dados

ATENÇÃO AOS PARÂMETROS (CRÍTICO):
- partner_name SEMPRE com nome completo: "Fundação Estudar" (NÃO "Estudar"), "Instituto Ponte" (NÃO "Ponte"), "Programa Aurora" (NÃO "Aurora")
- program: valores exatos são "passport", "programs", "prouni", "sisu", "cloudinha"
- user_id: usar o USER_ID_CONTEXT fornecido no início do prompt

EXEMPLOS DE RACIOCÍNIO:

---
MENSAGEM: "O que quer dizer essa pergunta?"
CONTEXTO: passport_phase=EVALUATE, form_state.focused_field="motivacao_pessoal", current_partner_id="abc123"
→ Chame getPartnerFormsTool(partner_id="abc123")
→ Chame smartResearchTool(query="o que preencher no campo motivação pessoal", program="programs", partner_name="Fundação Estudar")

---
MENSAGEM: "Até quando posso me inscrever na Fundação Estudar?"
→ Chame getImportantDatesTool(program_type="partners")

---
MENSAGEM: "O que são programas educacionais?"
→ Chame smartResearchTool(query="o que são programas educacionais", program="programs")

---
MENSAGEM: "O que devo fazer agora?"
CONTEXTO: passport_phase=ONBOARDING, form_state={campos parcialmente preenchidos}
→ Chame smartResearchTool(query="próximos passos do passaporte de elegibilidade", program="passport")

---
MENSAGEM: "Qual programa eu me adequo melhor?"
→ Chame evaluatePassportEligibilityTool(user_id="USER_ID")

---
MENSAGEM: "pra mim mesmo"
CONTEXTO: passport_phase=ASK_DEPENDENT
→ Chame processDependentChoiceTool(user_id="USER_ID", choice="self")

DEPOIS DE CHAMAR AS FERRAMENTAS: Faça um resumo técnico dos dados encontrados. Diga qual era a intenção do usuário, quais ferramentas foram usadas e o que foi encontrado. NÃO formate para o usuário final — outro agente fará isso.

REGRA DE PARCIMÔNIA: Use apenas as ferramentas NECESSÁRIAS. Máximo de 3 tools por turno.
"""

reasoning_agent = LlmAgent(
    model=MODEL_REASONING,
    name="reasoning_agent",
    description="Módulo de raciocínio: analisa intenção, chama ferramentas e produz resumo técnico.",
    instruction=REASONING_INSTRUCTION,
    tools=[
        smartResearchTool,
        evaluatePassportEligibilityTool,
        getImportantDatesTool,
        getPartnerFormsTool,
        getStudentProfileTool,
        processDependentChoiceTool,
        startStudentApplicationTool,
        rewindWorkflowStatusTool,
    ],
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
- ASK_DEPENDENT: Pergunte se busca para si ou para outra pessoa (se idade >= 18) ou avance direto (se < 18)
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

# Agent for CONCLUDED phase — read-only, no DB mutations
concluded_agent = LlmAgent(
    model=MODEL_CHAT,
    name="concluded_agent",
    description="Agente para fase CONCLUDED. Apenas tira dúvidas, sem mutações no banco.",
    instruction="""Você é a Cloudinha. O usuário já CONCLUIU sua aplicação no programa educacional. Parabéns! 🎉
    
    O user_id está disponível no início desta instrução como USER_ID_CONTEXT.
    
    NESTA FASE:
    - Você pode responder dúvidas usando `smartResearchTool` e `getImportantDatesTool`.
    - Você NÃO DEVE executar nenhuma ferramenta que altere o banco de dados. Nenhuma mutação é permitida.
    - Seja gentil, parabenize o usuário, e responda o que for perguntado sobre programas, datas, etc.
    
    USO DA smartResearchTool — REGRAS DE program:
    - Genérica sobre programas educacionais → program="programs"
    - Específica sobre parceiro → program="programs", partner_name="Nome"
    - Prouni/Sisu → program="prouni" ou "sisu"
    - Sobre a Cloudinha → program="cloudinha"
    
    REGRA ESTRITA: NUNCA diga ao usuário "vou pesquisar" ou "vou verificar na ferramenta". Apenas execute a tool silenciosamente e responda com o resultado.
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
            
        # Phase 2-5: Active phases use Reasoning → Response pipeline
        # The workflow.py orchestrator handles the 2-agent chain
        if passport_phase in ["ONBOARDING", "ASK_DEPENDENT", "DEPENDENT_ONBOARDING", "PROGRAM_MATCH", "EVALUATE"]:
            return {
                "type": "reasoning_response",
                "name": "reasoning_response_pipeline",
                "reasoning_agent": reasoning_agent,
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
            else:
                upd["_is_turn_complete"] = True
            
        elif passport_phase == "ASK_DEPENDENT":
            # Re-read the DB to check if processDependentChoiceTool already ran
            fresh_state = getStudentProfileTool(user_id)
            new_phase = fresh_state.get("passport_phase", "ASK_DEPENDENT")
            
            if new_phase != "ASK_DEPENDENT":
                upd["passport_phase"] = new_phase
            else:
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
            upd["_is_turn_complete"] = True
                 
        return upd if upd else None
