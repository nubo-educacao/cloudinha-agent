import json
from typing import Any, Dict, Optional, AsyncGenerator
from google.adk.agents import LlmAgent, Agent
from google.genai import types as genai_types
from src.agent.base_workflow import BaseWorkflow
from src.agent.config import MODEL_CHAT, MODEL_REASONING, MODEL_ROUTER
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool

# Phase 1: Greeting is a scripted message to prevent LLM hallucination
PASSPORT_INTRO_MESSAGE = "Oi! Eu sou a Cloudinha 👋\n\nEstou aqui para te ajudar a encontrar oportunidades educacionais que combinem com o seu momento e seus objetivos.\n\nVocê pode conhecer e se candidatar a programas de apoio educacional. Esses programas ajudam estudantes a desenvolver seu potencial ao longo da trajetória escolar. Eles podem oferecer aulas complementares, mentoria, orientação de estudos, desenvolvimento pessoal e, em alguns casos, apoio financeiro. Estou aqui para responder qualquer dúvida que você tiver sobre programas educacionais e sobre o processo de aplicar na plataforma.\n\nPara começar, preciso entender um pouco sobre você. Clique em \"Vamos começar!\" e preencha o formulário ao lado. Com esses dados vamos te indicar em quais programas parceiros que você pode se aplicar"

from src.tools.processDependentChoice import processDependentChoiceTool
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
2. **RENDA PER CAPITA**: Se o usuário tiver dúvidas ou problemas ao salvar a renda, explique que "Renda Per Capita Mensal" é a soma de todos os ganhos da casa dividida pelo número de moradores. Oriente a clicar no botão "Calcular Renda" para preencher facilmente.
3. **NÃO AVALIE ELEGIBILIDADE AINDA**: Foco em completar o cadastro. Responda dúvidas sobre a plataforma abertamente.
"""

DEPENDENT_ONBOARDING_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Você está na FASE DEPENDENT_ONBOARDING. O usuário está preenchendo os dados do seu dependente (ex: um filho) no formulário ao lado.

FUNÇÃO TÁTICA:
1. **AUXILIAR NO CADASTRO DO DEPENDENTE**: Use `getStudentProfileTool(user_id=ID_DO_DEPENDENTE)` (verifique `current_dependent_id` no perfil) para ver o que já foi salvo. Oriente o preenchimento na UI lateral.
2. **RENDA PER CAPITA**: Se houver problemas com renda, explique gentilmente que "Renda Per Capita Mensal" é a soma de todos os rendimentos dividida pelo número de moradores na casa do dependente, e recomende usar o "Calcular Renda".
3. **FOCO NO DEPENDENTE**: Responda dúvidas sobre oportunidades para o filho/dependente do usuário com clareza.
"""

ASK_DEPENDENT_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Você está na FASE ASK_DEPENDENT. Queremos saber se a vaga é para o usuário ou para um dependente.

FUNÇÃO TÁTICA:
1. **COORDENAR ESCOLHA**: SEMPRE que o usuário responder indicando para quem é a aplicação (ex: "É para mim", "Para mim", "Preencher pra mim", "É para outra pessoa", "Para outra pessoa", "É para minha filha", "Para meu filho", etc.), use OBRIGATORIAMENTE a ferramenta `processDependentChoiceTool`.
   - Você pode passar 'self' (se for para o próprio usuário) ou 'dependent' (se for para outra pessoa).
   - Opcionalmente, você pode passar a própria resposta do usuário no parâmetro `choice` (ex: choice="É para minha filha"), pois a ferramenta entenderá a intenção.
2. **IDADE**: Use `getStudentProfileTool` para ver a idade. Use isso para sugerir as opções de forma contextual.
"""

PROGRAM_MATCH_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Esta é a FASE PROGRAM_MATCH. Os cards de programas parceiros estão na tela.

FUNÇÃO TÁTICA:
1. **LER RESULTADOS**: Use `getEligibilityResultsTool` para buscar os matches calculados. Verifique no retorno da ferramenta se o match foi feito para o ESTUDANTE (respondente principal) ou para o seu DEPENDENTE (ex: filho/filha).
2. **CLAREZA NA COMUNICAÇÃO**: Ao apresentar as opções, deixe muito claro para quem são os programas. Se for para o dependente, use frases como "Encontrei essas opções excelentes para o seu filho/sua filha!" ou "Esses programas combinam muito bem com o perfil do seu dependente.".
3. **INICIAR APLICAÇÃO**: Se o usuário escolher um programa (ex: "Quero a Fundação Estudar"), chame IMEDIATAMENTE `startStudentApplicationTool` com o UUID ou Nome do parceiro.
   - **Leia atentamente a intenção do usuário:** se a mensagem contiver a identificação do dependente (ex: `target_user_id=...` ou expressar "inscrever meu dependente"), você DEVE passar esse ID no parâmetro `target_user_id`. Caso contrário, omita o parâmetro. Não peça confirmação extra.
7. **RESUMO COM CRITÉRIOS**: Se o usuário não escolheu e você for apresentar as opções:
   - Apresente um resumo entusiasta das opções elegíveis.
   - Para **CADA PROGRAMA**, liste brevemente 1 ou 2 critérios principais que o estudante/dependente **atendeu** (ex: "Você atendeu ao critério de renda e idade!"). Isso ajuda a justificar o match.
8. **TIRAR DÚVIDAS SOBRE PROGRAMAS**: Se o estudante fizer perguntas sobre os programas listados (ex: prazos, regras do edital, o que o programa oferece), use OBRIGATORIAMENTE a ferramenta `smartResearchTool` para buscar a resposta na base de conhecimento antes de responder. Nunca diga "não consigo ver o edital" ou pergunte o que ele quer saber sem antes pesquisar.
9. **PARCEIROS COM REDIRECIONAMENTO EXTERNO**: Se o usuário demonstrar interesse em um programa que possua o campo `external_redirect_config` nos resultados da ferramenta `getEligibilityResultsTool`, **NÃO chame startStudentApplicationTool**. Em vez disso, responda informando que a inscrição é externa. Utilize os campos `message`, `url` e `buttonText` do config para orientar o usuário.
   - Exemplo de resposta: "A inscrição para este programa é feita externamente. [message do config]. Clique no link para continuar: [url do config]"
"""




EVALUATE_REASONING_INSTRUCTION = BASE_REASONING_INSTRUCTION + """
Você está no MÓDULO DE RACIOCÍNIO da FASE EVALUATE (Preenchimento de formulário de parceiro).
Sua função é fornecer um RELATÓRIO TÉCNICO estruturado para o agente de resposta.

PROTOCOLO DE PENSAMENTO OBRIGATÓRIO (NÃO PULE ESTAS ETAPAS):
1. **TOOL CALL WITH USER_ID**: Você DEVE chamar `getPartnerFormsTool(user_id="...")` passando o `user_id` do contexto. Se o usuário estiver perguntando sobre o formulário na tela, omita o `partner_id`.
2. **FILTRAGEM DE ETAPA (CONDIÇÃO CRÍTICA)**: A ferramenta retorna TODOS os campos do formulário. Você deve identificar em qual etapa (`step_name`) o usuário afirma estar (ex: "Dados acadêmicos") e FILTRAR os resultados para processar APENAS os campos dessa etapa. Se não houver etapa mencionada, use a etapa com o primeiro erro detectado.
3. **RELATÓRIO ESTRUTURADO**: Ignore o tom de voz. Emita APENAS os dados filtrados:

--- INÍCIO DO RELATÓRIO TÉCNICO ---
ETAPA DETECTADA: [Nome da etapa filtrada]
REJEIÇÃO DE DADOS IRRELEVANTES: [Cite brevemente que descartou X campos de outras etapas para focar nesta]
CAMPOS DA ETAPA: [Lista de question_text e data_type dos campos filtrados]
ERROS E VALIDAÇÕES: [Analise o 'maskking' e o erro apenas dos campos desta etapa]
DICA TÉCNICA: [Instrução clara para o response_agent sobre como ajudar o usuário nesta etapa específica]
--- FIM DO RELATÓRIO TÉCNICO ---

REGRAS DE CHAMADA DE FERRAMENTA:
- Sempre use o `user_id` do contexto (USER_ID_CONTEXT).
- Jamais emita texto conversacional. Seu output é um documento técnico para a Cloudinha (agente de resposta).
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
1. **CELEBRAR E CONFIRMAR**: Comemore a vitória! Use `getStudentApplicationTool` para confirmar os detalhes e o status ("SUBMITTED") da aplicação que o usuário acabou de enviar. Isso confirma para o estudante que tudo deu certo.
2. **ANALISAR OPORTUNIDADES TOTAIS**: Use `getEligibilityResultsTool` para checar a elegibilidade do estudante em TODOS os outros programas parceiros do Nubo Hub. Esta ferramenta mostra quais critérios foram atendidos ou não para cada parceiro disponível.
3. **SUGERIR NOVAS APLICAÇÕES**: Com base nos resultados de `getEligibilityResultsTool`, identifique outros programas onde o estudante é altamente elegível. Incentive-o a se candidatar a esses novos programas para aumentar suas chances de sucesso.
4. **INICIAR APLICAÇÃO**: Se o estudante aceitar uma sugestão, chame `startStudentApplicationTool` com o NOME do parceiro imediatamente.
5. **NUNCA PEÇA ID OU CONFIRMAÇÃO**: Identifique o nome do programa pela ferramenta e inicie o processo silenciosamente se o usuário demonstrar interesse.
6. **PARCEIROS COM REDIRECIONAMENTO EXTERNO**: Se o usuário demonstrar interesse em um programa que possua o campo `external_redirect_config` nos resultados da ferramenta `getEligibilityResultsTool`, **NÃO chame startStudentApplicationTool**. Em vez disso, responda informando que a inscrição é externa. Utilize os campos `message`, `url` e `buttonText` do config para orientar o usuário.
   - Exemplo de resposta: "A inscrição para este programa é feita externamente. [message do config]. Clique no link para continuar: [url do config]"
""",
    tools=[
        getStudentProfileTool,
        getEligibilityResultsTool,
        getStudentApplicationTool,
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
0. **IDIOMA EXCLUSIVO**: Você DEVE SEMPRE responder EXCLUSIVAMENTE em Português do Brasil (PT-BR), independentemente do idioma dos dados no relatório técnico ou do input do usuário.
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

INÍCIO DE APLICAÇÃO MODO SILENCIOSO:
- Se o relatório técnico indicar que a ferramenta `startStudentApplicationTool` foi executada e a aplicação foi INICIADA com sucesso (fase avançada para EVALUATE), sua ÚNICA FUNÇÃO é confirmar o início e pedir para o usuário olhar o formulário no painel ao lado.
- NUNCA liste os programas ou opções de match se uma aplicação acabou de ser iniciada com sucesso. Foque APENAS no formulário que se abriu.

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
  - PROCESSAMENTO DE DEPENDENTE DEFINIDO: Se o relatório indicar que `processDependentChoiceTool` foi usada e o usuário escolheu "para outra pessoa/dependente" (faseDEPENDENT_ONBOARDING), apenas avise alegremente que o perfil foi criado e oriente o usuário a preencher os dados do dependente no formulário que acabou de abrir ao lado. NUNCA pergunte novamente para quem é a vaga.
  - PROCESSAMENTO PARA SI MESMO: Se o usuário escolheu "para mim mesmo" (fase PROGRAM_MATCH), diga que está analisando as opções e apresente os programas.
- PROGRAM_MATCH: Apresente resultados de elegibilidade com entusiasmo. **MUITO IMPORTANTE**: Sempre inclua os critérios que a pessoa (eu ou dependente) atendeu para aquele programa, justificando por que é um bom match (conforme os dados do relatório).
- EVALUATE: Ajude com dúvidas sobre campos do formulário do parceiro. Se o relatório técnico mostrar que você analisou campos com erro (via getPartnerFormsTool), seja específica sobre o que corrigir (ex: "O CPF deve ter 11 números" ou "A data parece inválida").
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
        print(f"[TRACE] [PassportWorkflow] DECISION POINT: user_id={user_id}, phase_received='{passport_phase}'")
        print(f"[PassportWorkflow] get_agent_for_user: phase='{passport_phase}' for user={user_id}")
        
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
        passport_phase = current_state.get("passport_phase") or "INTRO"
        # Debug: Log reasoning report (safe for Pyre)
        print(f"[REASONING REPORT] user_id={user_id}, phase={passport_phase}")
        if step_output:
             print(f"[REASONING REPORT CONTENT]: {step_output[:200]}...")
        
        upd = {}
        
        if passport_phase == "INTRO":
            print(f"[REASONING OUTPUT] Phase INTRO: {step_output}")
            # [FIX] Do NOT auto-transition to ONBOARDING after intro.
            # We wait for the user to click "Vamos começar!" which sends a specific message.
            # This ensures the user SEES the scripted greeting.
            upd["_is_turn_complete"] = True
            return upd
            
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
