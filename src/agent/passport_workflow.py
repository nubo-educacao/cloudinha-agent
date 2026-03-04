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
# REASONING AGENTS — Intent classification + Tool selection/execution by Phase
# ============================================================

ONBOARDING_REASONING_INSTRUCTION = """Você está na fase ONBOARDING. O usuário está preenchendo seus dados pessoais em um formulário na tela.

O user_id está disponível como USER_ID_CONTEXT no início deste prompt.

Sua função tática é dupla:
1. **RESPONDER DÚVIDAS E PESQUISAR (PRIORIDADE ALTA)**: O usuário PODE E VAI fazer perguntas sobre prazos, como funcionam os programas parceiros, o que ele ganha com eles, etc. Você DEVE SEMPRE usar as ferramentas `smartResearchTool` e `getImportantDatesTool` para responder a essas dúvidas com precisão. NUNCA se recuse a responder uma dúvida sob o pretexto de que ele precisa terminar o cadastro primeiro.
2. **AUXILIAR NO CADASTRO**: Use `getStudentProfileTool` para ver o que ele já preencheu. Compare com o 'ESTADO ATUAL DO FORMULÁRIO DO USUÁRIO' injetado no contexto. Se ele relatar um erro ("não consigo salvar", "o que falta?"), aponte qual campo precisa ser corrigido com base no contexto injetado. Lembre-o gentilmente de que o preenchimento é feito na tela.

Instruções finais: A resposta exata para dúvidas gerais do passaporte já consta no seu contexto injetado, mas para parceiros/prazos específicos, faça a chamada de tool obrigatória. Não tente realizar avaliações de eligibility ou achar matches definitivos ainda, mas sempre responda as dúvidas dele sobre as oportunidades da plataforma."""

DEPENDENT_ONBOARDING_REASONING_INSTRUCTION = """Você está na fase DEPENDENT_ONBOARDING. O usuário está preenchendo os dados do seu dependente (ex: um filho) em um formulário na tela ao lado.

O user_id do titular está como USER_ID_CONTEXT. O dependent_id do dependente está no contexto (verifique em current_dependent_id no perfil).

Sua função tática é dupla:
1. **RESPONDER DÚVIDAS E PESQUISAR (PRIORIDADE ALTA)**: O pai/responsável PODE E VAI fazer perguntas sobre prazos, como funcionam os programas parceiros e o que eles oferecem para o filho dele. Você DEVE SEMPRE usar as ferramentas `smartResearchTool` e `getImportantDatesTool` para responder a essas dúvidas clara e precisamente. NUNCA se recuse a responder uma dúvida sob o pretexto de que ele precisa terminar o cadastro do dependente primeiro.
2. **AUXILIAR NO CADASTRO DO DEPENDENTE**: Use `getStudentProfileTool(user_id=ID_DO_DEPENDENTE)` para ver o que já foi salvo no banco. Compare com o 'ESTADO ATUAL DO FORMULÁRIO DO USUÁRIO' injetado no contexto. Se houver dúvidas ou erros relatados na hora de preencher/salvar, oriente-o usando esses dados. O preenchimento deve ser feito na UI visual.

Instruções finais: Não tente realizar avaliações de eligibility ou achar matches definitivos para o dependente ainda. Foco total em tirar as dúvidas abertamente e ajudar a preencher os dados corretamente."""

ASK_DEPENDENT_REASONING_INSTRUCTION = """Você está na fase ASK_DEPENDENT. O sistema quer saber se essas oportunidades de estudo são para o próprio usuário ou para um dependente (filho, irmão, etc).

O user_id está disponível como USER_ID_CONTEXT no início deste prompt.

1. O usuário pode tirar dúvidas sobre programas a qualquer momento. Se ele perguntar algo, use `smartResearchTool` ou `getImportantDatesTool` para responder com clareza.
2. Se o usuário afirmar para quem é a vaga de forma clara (ex: "é para mim" ou "para minha filha"), chame OBRIGATORIAMENTE a ferramenta `processDependentChoiceTool(choice='self')` ou `processDependentChoiceTool(choice='dependent')` para registrar a escolha e avançar o fluxo.
3. Se ele não escolheu ainda, chame a `getStudentProfileTool` para ver a idade dele e, no seu resumo técnico, explique as opções com base na idade para que o Response Agent formule a mensagem.
4. NÃO tente empurrar a decisão. Deixe os botões da UI ou a resposta do usuário guiarem."""

PROGRAM_MATCH_REASONING_INSTRUCTION = """Esta é a fase PROGRAM_MATCH, a hora da verdade! Os programas parceiros já estão sendo exibidos na tela do usuário em cards visuais. Siga esta ordem rigidamente:

O user_id está disponível como USER_ID_CONTEXT no início deste prompt. O respectivo dependent_id está no perfil do usuário, caso ele tenha um.

1. **Leitura dos Dados:** Use `getEligibilityResultsTool` para buscar os resultados de elegibilidade do estudante. Se a ferramenta retornar resultados, anote os `partner_id` (UUID) e `partner_name` de cada programa. Se retornar vazio, não se preocupe — os cards dos parceiros estão sendo exibidos na tela do estudante pelo frontend.
2. **Dúvidas:** Se o usuário perguntar algo específico sobre os programas, use a `smartResearchTool` passando o 'partner_name'. Se perguntar prazos, use `getImportantDatesTool`.
3. **Decisão do Estudante:** Quando o estudante disser no chat qual programa ele quer (ex: "Quero a Fundação Estudar", "Instituto Ponte por favor", "quero me aplicar na Aurora"), chame IMEDIATAMENTE a ferramenta `startStudentApplicationTool`.
4. **Como passar o partner_id:** Você pode passar tanto o UUID (se disponível nos resultados de `getEligibilityResultsTool`) quanto o NOME do parceiro. A ferramenta aceita ambos e resolve internamente. Exemplo: `startStudentApplicationTool(user_id=USER_ID, partner_id="Fundação Estudar")` é válido.
5. **Não peça confirmação adicional.** Se o estudante já disse qual programa quer, inicie a aplicação imediatamente. Não diga "vou iniciar", apenas CHAME a ferramenta.
6. **Se o estudante ainda não escolheu:** Faça um resumo simpático dos programas disponíveis (baseado nos resultados de elegibilidade ou no que o frontend exibe) e pergunte qual ele prefere."""




EVALUATE_REASONING_INSTRUCTION = """Você está na fase EVALUATE. O estudante escolheu um programa parceiro e agora o edital ou formulário oficial desse programa está aberto na tela dele para ser preenchido (student_application).

O user_id e o current_partner_id (da aplicação ativa) estão disponíveis no contexto.

1. Use `getPartnerFormsTool` passando o ID do parceiro atual para entender todas as regras e campos obrigatórios do edital.
2. Use `getStudentApplicationTool` para ler o que o estudante já conseguiu preencher e salvar no banco até o momento.
3. ANALISE O PREENCHIMENTO: Compare o que o estudante já salvou (via tool), o que o edital pede (via partner forms) e o 'ESTADO ATUAL DO FORMULÁRIO DO USUÁRIO' injetado no contexto. 
4. Se o usuário relatar erros ao salvar ou perguntar sobre um campo, use o contexto de UI (campo em foco e dados atuais) para dar uma explicação técnica e empática do erro.
5. Atue como o monitor particular dele: Traduza termos complexos, cruze o que ele escreveu com o que o edital pede usando a `smartResearchTool` junto com as regras do `getPartnerFormsTool`.
6. Você NÃO envia o formulário no final. Apenas o guie, responda às dificuldades de preenchimento e traduza a burocracia até que ele mesmo clique no botão de 'Concluir Inscrição' na UI. O ProfileTool pode ser usado se precisar validar um dado fixo dele."""


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

concluded_agent = LlmAgent(
    model=MODEL_CHAT,
    name="concluded_agent",
    description="Agente para fase CONCLUDED. Apenas tira dúvidas e pode iniciar novas aplicações.",
    instruction="""Você está na fase CONCLUDED. A aplicação atual do estudante foi finalizada e enviada!
    
    O user_id está disponível no início desta instrução como USER_ID_CONTEXT.
    
    NESTA FASE:
    1. Imediatamente celebre a conquista com o estudante!
    2. Leia o campo `eligibility_results` no `getStudentProfileTool` para analisar para quais OUTROS parceiros o usuário tem um bom match.
    3. Seja proativo: diga a ele que com as respostas já dadas, ele também tem chances noutros programas (cite-os com base no resultado lido). Pergunte: 'Gostaria de aproveitar seus dados já salvos e tentar aplicar para esse programa também?'
    4. Se ele aceitar e disser sim explicitamente para um parceiro, use a ferramenta `startStudentApplicationTool` para iniciar esse novo parceiro. O fluxo voltará dinamicamente para a fase EVALUATE.
    5. Você também deve responder dúvidas usando `smartResearchTool` e `getImportantDatesTool`.
    
    USO DA smartResearchTool — REGRAS DE program:
    - Genérica sobre programas educacionais → program="programs"
    - Específica sobre parceiro → program="programs", partner_name="Nome"
    - Prouni/Sisu → program="prouni" ou "sisu"
    - Sobre a Cloudinha → program="cloudinha"
    
    REGRA ESTRITA: NUNCA diga ao usuário "vou pesquisar" ou "vou verificar na ferramenta". Apenas execute a tool silenciosamente e responda com o resultado.
    """,
    tools=[
        getStudentProfileTool,
        startStudentApplicationTool,
        smartResearchTool,
        getImportantDatesTool
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
