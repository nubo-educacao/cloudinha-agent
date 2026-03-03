from typing import AsyncGenerator, Any, Dict, Optional
import asyncio
import httpx
import json
from google.adk.runners import Runner
from google.adk.agents import LlmAgent, Agent
from google.genai.types import Content, Part
from google.adk.sessions import InMemorySessionService
from src.lib.resilience import retry_with_backoff
from tenacity import RetryError
from src.agent.agent import session_service, root_agent, sisu_agent, prouni_agent
from src.agent.router_agent import execute_router_agent
from src.agent.retrieval import retrieve_similar_examples
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.updateStudentProfile import updateStudentProfileTool
import logging

# Legacy Workflows (Removed from primary registry to enforce Passei Workflow)
# "match_workflow": ...
# "sisu_workflow": ...
# "prouni_workflow": ...
from src.agent.base_workflow import SingleAgentWorkflow
from src.agent.passport_workflow import PassportWorkflow

# Initialize Registry with only the new enforced flow
workflow_registry = {
    "passport_workflow": PassportWorkflow()
}

# Wrapper for Root (Fallback only)
root_workflow = SingleAgentWorkflow(root_agent, "root_workflow")

# --- Knowledge Base Paths (injected into passei/concluded agents) ---
import os
_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "documents")
_PASSPORT_DOC_PATH = os.path.join(_DOCS_DIR, "passei_workflow_doc.md")
_GENERAL_KNOWLEDGE_PATH = os.path.join(_DOCS_DIR, "partners", "Base de conhecimento geral.md")

# Cache to avoid re-reading files on every turn
_knowledge_cache = {}

def _load_knowledge_context() -> str:
    """Pre-loads knowledge base content and returns formatted context string.
    
    Note: passei_workflow_doc.md is a technical PRD not suitable for direct context injection
    (it contains code references and the INTRO script which the LLM would repeat).
    Instead, we inject a student-facing summary of the process + the general knowledge base.
    """
    if "content" in _knowledge_cache:
        return _knowledge_cache["content"]
    
    print(f"[Workflow] Loading knowledge base files...")
    
    sections = []
    
    # 1. Student-facing process summary (replaces raw passei_workflow_doc.md injection)
    process_summary = """=== COMO FUNCIONA O PASSAPORTE DA ELIGIBILIDADE ===

O Passaporte da Eligibilidade é um processo guiado pela Cloudinha que ajuda estudantes a encontrar e se candidatar a programas educacionais parceiros. Funciona assim:

ETAPA 1 - ONBOARDING (Cadastro de dados):
O estudante preenche um formulário com seus dados básicos: nome, idade, cidade, escolaridade, CEP e endereço. Esses dados são essenciais para avaliar a elegibilidade nos programas parceiros.

ETAPA 2 - ESCOLHA DO CANDIDATO:
Após o cadastro, perguntamos se o estudante busca uma oportunidade para si próprio ou para outra pessoa (um dependente, como filho ou familiar).

ETAPA 3 - ANÁLISE DE ELEGIBILIDADE (Program Match):
Com base nos dados informados, o sistema analisa automaticamente quais programas parceiros o estudante atende aos critérios (como idade, renda, escolaridade). A Cloudinha apresenta os resultados.

ETAPA 4 - APLICAÇÃO (Evaluate):
O estudante escolhe um programa e preenche o formulário específico do parceiro. A Cloudinha tira dúvidas sobre o edital e os campos do formulário.

ETAPA 5 - CONCLUSÃO:
Após enviar a aplicação, o processo está completo. O estudante pode continuar tirando dúvidas.

PARCEIROS DISPONÍVEIS:
- Fundação Estudar: Programas de desenvolvimento e bolsas para estudantes de alto potencial.
- Instituto Ponte: Apoio educacional focado em acesso a escolas de excelência.
- Programa Aurora | Instituto Sol: Programa de formação complementar e mentoria.

O QUE SÃO PROGRAMAS DE APOIO EDUCACIONAL:
São iniciativas de organizações da sociedade civil que ampliam oportunidades de formação acadêmica. NÃO se limitam a bolsas financeiras — podem incluir aulas complementares, mentoria, orientação de carreira, desenvolvimento socioemocional, preparação para processos seletivos e mais.
"""
    sections.append(process_summary)
    print("[Workflow] ✅ Process summary loaded")
    
    # 2. General partner knowledge base (detailed content)
    if os.path.exists(_GENERAL_KNOWLEDGE_PATH):
        try:
            with open(_GENERAL_KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                sections.append(f"=== BASE DE CONHECIMENTO DETALHADA SOBRE PROGRAMAS EDUCACIONAIS ===\n{content}")
                print(f"[Workflow] ✅ Loaded Base de conhecimento geral.md ({len(content)} chars)")
        except Exception as e:
            print(f"[Workflow] ❌ Erro ao ler {_GENERAL_KNOWLEDGE_PATH}: {e}")
    else:
        print(f"[Workflow] ❌ Base de conhecimento geral.md NOT FOUND at {_GENERAL_KNOWLEDGE_PATH}")
    
    result = "\nBASE DE CONHECIMENTO — USE ESTAS INFORMAÇÕES PARA RESPONDER PERGUNTAS DO ESTUDANTE:\n" + "\n\n".join(sections) + "\n--- FIM DA BASE DE CONHECIMENTO ---\n"
    print(f"[Workflow] ✅ Knowledge context ready ({len(result)} chars total)")
    
    _knowledge_cache["content"] = result
    return result

class SimpleTextEvent:
    def __init__(self, text: str):
        self.text = text

def check_authentication(user_id: str) -> bool:
    return bool(user_id and user_id.strip() != "" and user_id != "anon-user")

async def run_workflow(
    user_id: str,
    session_id: str,
    new_message: Content,
    ui_form_state: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Any, None]:
    """
    Orchestrates the generic agent workflow.
    """
    if not check_authentication(user_id):
        yield SimpleTextEvent("Desculpe, não posso falar com você se não estiver logado.")
        return

    # 0. Fetch Initial State
    profile_state = getStudentProfileTool(user_id)
    
    # Pre-loop Router check
    # Run Router for ALL users (passport_workflow handles onboarding internally)
    msg_text = new_message.parts[0].text if new_message.parts else ""
    
    # [Fix] Fetch Recent History from DB (chat_messages) for full context
    recent_history_str = ""
    chat_history_for_agent = ""
    active_wf = profile_state.get("active_workflow")
    try:
        session = await session_service.get_session("cloudinha-agent", session_id, user_id)
        
        # Agent gets last 20 messages filtered by current workflow
        if active_wf and hasattr(session, 'load_for_workflow'):
            workflow_history = session.load_for_workflow(active_wf, limit=20)
        else:
            workflow_history = session.load()[-20:] if session.load() else []
        
        agent_history_lines = []
        for m in workflow_history:
            role_label = "Usuário" if m.role == "user" else "Cloudinha"
            txt = ""
            if m.parts:
                for p in m.parts:
                    if p.text: txt += p.text
            if txt:
                agent_history_lines.append(f"{role_label}: {txt}")
        
        if agent_history_lines:
            chat_history_for_agent = "\nHISTÓRICO DA CONVERSA (últimas mensagens):\n" + "\n".join(agent_history_lines) + "\n---\n"
        
        # Router gets last 10 globally for decision making (needs cross-workflow context)
        all_history = session.load()
        last_messages_for_router = all_history[-10:] if all_history else []
        router_history_lines = []
        for m in last_messages_for_router:
            role_label = "Usuário" if m.role == "user" else "Cloudinha (Bot)"
            txt = ""
            if m.parts:
                for p in m.parts:
                    if p.text: txt += p.text
            if txt:
                router_history_lines.append(f"{role_label}: {txt}")
        
        recent_history_str = "\n".join(router_history_lines)

    except Exception as e:
        print(f"[RunWorkflow] Context Fetch Error: {e}")

    # O "Passei Workflow" é o fluxo definitivo e único da Cloudinha agora.
    # Independentemente do que estava no active_wf, vamos forçar para passport_workflow
    if active_wf != "passport_workflow":
        print(f"[RunWorkflow] Forcing workflow -> 'passport_workflow'")
        updateStudentProfileTool(user_id=user_id, updates={"active_workflow": "passport_workflow"})
        profile_state = getStudentProfileTool(user_id)
        active_wf = "passport_workflow"
    
    profile_state["active_workflow"] = "passport_workflow"

    # Main Loop
    MAX_STEPS = 10
    steps_run = 0
    current_message = new_message

    while steps_run < MAX_STEPS:
        
        # 1. Determine Active Workflow (Always passport_workflow now)
        workflow_obj = workflow_registry["passport_workflow"]

        # 2. Get Agent or Scripted Message from Workflow
        # By passing profile_state, passport_workflow looks at 'passport_phase'
        step = workflow_obj.get_agent_for_user(user_id, profile_state)
        
        # Handle None — workflow is done
        if not step:
             print(f"[RunWorkflow] Workflow {workflow_obj.name} returned NO agent. Ending turn.")
             break

        # --- ACTION STEP (deterministic state update, no LLM, processes user input) ---
        if isinstance(step, dict) and step.get("type") == "action":
             action_func = step.get("func")
             action_name = step.get("name", "action_step")
             print(f"[RunWorkflow] Action step: {action_name} (Workflow: {workflow_obj.name})")
             
             user_text = current_message.parts[0].text if current_message.parts else ""
             
             if action_func:
                 action_updates = action_func(user_id, profile_state, user_text)
                 if action_updates:
                     db_updates = {k: v for k, v in action_updates.items() if not k.startswith("_")}
                     if db_updates:
                         updateStudentProfileTool(user_id=user_id, updates=db_updates)
                     profile_state.update(action_updates)
                     
                     if action_updates.get("_is_turn_complete"):
                         print("[RunWorkflow] Turn marked as complete by action step.")
                         break
             
             # Loop continues immediately to next step
             steps_run += 1
             continue

        # --- SCRIPTED MESSAGE (deterministic output, no LLM) ---
        if isinstance(step, dict) and step.get("type") == "scripted":
            scripted_message = step.get("message", "")
            scripted_name = step.get("name", "scripted_step")
            print(f"[RunWorkflow] Scripted step: {scripted_name} (Workflow: {workflow_obj.name})")
            
            yield SimpleTextEvent(scripted_message)
            captured_output = scripted_message
            
            # Still handle transitions
            updates = workflow_obj.handle_step_completion(user_id, profile_state, captured_output)
            if updates:
                db_updates = {k: v for k, v in updates.items() if not k.startswith("_")}
                if db_updates:
                    updateStudentProfileTool(user_id=user_id, updates=db_updates)
                profile_state.update(updates)
                
                if updates.get("_is_turn_complete"):
                    print("[RunWorkflow] Turn marked as complete by scripted step. Ending turn.")
                    break
            
            steps_run += 1
            continue

        # --- LLM AGENT ---
        agent = step
        print(f"[RunWorkflow] Executing agent: {agent.name} (Workflow: {workflow_obj.name})")

        # 3. Dynamic RAG / Instruction Injection
        # We need to inject examples. Identify category.
        intent_cat = "general_qa"
        if "sisu" in agent.name: intent_cat = "sisu"
        elif "prouni" in agent.name: intent_cat = "prouni"
        elif "match" in agent.name: intent_cat = "match_search"
        
        user_query_text = current_message.parts[0].text if current_message.parts else ""
        examples = retrieve_similar_examples(user_query_text, intent_cat)
        
        # Inject Profile State context to the selected agent BEFORE it runs
        profile_context_str = "\nPERFIL ATUAL DO ESTUDANTE:\n"
        for k, v in profile_state.items():
            if v is not None and str(v).strip() != "":
                profile_context_str += f"- {k}: {v}\n"
        profile_context_str += "\n"

        if ui_form_state is not None:
            focused_field = ui_form_state.get("_focused_field", "Nenhum")
            form_data = {k: v for k, v in ui_form_state.items() if not k.startswith("_")}
            form_json = json.dumps(form_data, ensure_ascii=False)
            profile_context_str += f"\nESTADO ATUAL DO FORMULÁRIO DO USUÁRIO PENDENTE DE SALVAMENTO: {form_json}. CAMPO EM FOCO: {focused_field}\n"
        
        # Pre-load knowledge base content for passei/concluded agents
        knowledge_context_str = ""
        if agent.name in ("passei_agent", "concluded_agent"):
            knowledge_context_str = _load_knowledge_context()
        
        # Create Runner Instance (Clone agent with new instruction)
        # Inject: USER_ID_CONTEXT + original instruction + profile_state + chat history + knowledge base + RAG examples
        runnable_agent = LlmAgent(
            model=agent.model,
            name=agent.name,
            description=agent.description,
            instruction=f"USER_ID_CONTEXT: {user_id}\n\n" + agent.instruction + "\n\n" + profile_context_str + chat_history_for_agent + knowledge_context_str + "\n" + examples,
            tools=agent.tools,
            output_key=agent.output_key
        )

        runner = Runner(agent=runnable_agent, app_name="cloudinha-agent", session_service=session_service)

        # 4. Run Agent & Emit/Capture Events
        
        # Emit "On Start" events
        async for start_event in workflow_obj.on_runner_start(agent):
             yield start_event

        yield {"type": "tool_start", "tool": agent.name, "args": {"workflow": workflow_obj.name}}
        
        captured_output = ""
        
        # Retry logic for agent execution
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=current_message):
                    # Transform/Filter
                    final_event = workflow_obj.transform_event(event, agent.name)
                    
                    if final_event:
                        if hasattr(final_event, 'text') and final_event.text:
                            captured_output += final_event.text
                        elif isinstance(final_event, dict) and final_event.get("output"):
                            captured_output += final_event.get("output", "")
                        
                        yield final_event
                    else:
                         if hasattr(event, 'text') and event.text:
                             captured_output += event.text
                         elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                             for p in event.content.parts:
                                 if hasattr(p, 'text') and p.text: captured_output += p.text
                
                # If we finish the loop without error, break the retry loop
                break
            
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, ConnectionError, TimeoutError, OSError) as e:
                print(f"[RunWorkflow] Attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    yield {"type": "error", "message": "Estou com dificuldades de conexão. Tente novamente."}
                    break
                
                # Backoff
                await asyncio.sleep(2 ** attempt)
                captured_output = "" 


        yield {"type": "tool_end", "tool": agent.name, "output": "Step Completed"}
        
        # 5. Handle Completion / Transitions
        updates = workflow_obj.handle_step_completion(user_id, profile_state, captured_output)
        
        state_changed = False
        if updates:
            # Filter out internal flags (prefixed with _) before saving to DB
            db_updates = {k: v for k, v in updates.items() if not k.startswith("_")}
            if db_updates:
                updateStudentProfileTool(user_id=user_id, updates=db_updates)
            profile_state.update(updates) # Local Update
            state_changed = True
            
            # Check for Workflow Switch/Termination/Turn End
            new_workflow = updates.get("active_workflow")
            is_turn_complete = updates.get("_is_turn_complete")

            # 1. Check if workflow exited
            if "active_workflow" in updates and new_workflow is None:
                 print("[RunWorkflow] Workflow exited explicitly (None). Ending turn.")
                 break
            
            # 2. Check if turn is marked as complete
            if is_turn_complete:
                 print("[RunWorkflow] Turn marked as complete by workflow. Ending turn.")
                 break

            if "active_workflow" in updates:
                 print(f"[RunWorkflow] State update triggered workflow change: {new_workflow}")
                 # Loop will continue and pick up new workflow
                 pass

        steps_run += 1
        
        # Termination conditions to avoid infinite loops if no state change?
        # If agent ran and no state change, usually we break (waiting for user input).
        # EXCEPT if the agent *internally* decided to continue?
        # Standard ADK Agent usually implies turn end unless we chain.
        # MatchWorkflow: Reasoning -> Response chain was handled by "state change" (_match_phase).
        # So we continue loop.
        
        # But if Standard Agent (Root/Sisu) ran, we should break.
        if not state_changed and not updates:
             break

        # If we looped MAX times
        if steps_run >= MAX_STEPS:
            print("[RunWorkflow] Max steps reached.")
