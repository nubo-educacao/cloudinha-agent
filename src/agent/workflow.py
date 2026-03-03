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
import datetime
import traceback
from src.lib.supabase import supabase

def _log_tool_error(user_id: str, session_id: str, tool_name: str, error_msg: str, tb: str, args=None, raw_output=None):
    try:
        error_data = {
            "user_id": user_id,
            "session_id": session_id,
            "error_type": "tool_error",
            "error_message": error_msg,
            "stack_trace": tb,
            "metadata": {
                "tool_name": tool_name,
                "args": args,
                "raw_output": raw_output
            }
        }
        supabase.table("agent_errors").insert(error_data).execute()
    except Exception as e:
        print(f"[Workflow] Error logging tool error to DB: {e}")

# Legacy Workflows (Removed from primary registry to enforce Passei Workflow)
from src.agent.base_workflow import SingleAgentWorkflow
from src.agent.passport_workflow import PassportWorkflow

# Initialize Registry with only the new enforced flow
workflow_registry = {
    "passport_workflow": PassportWorkflow()
}

# Wrapper for Root (Fallback only)
root_workflow = SingleAgentWorkflow(root_agent, "root_workflow")

# --- Knowledge Base Paths (injected into reasoning/concluded agents) ---
import os
_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "documents")
_PASSPORT_DOC_PATH = os.path.join(_DOCS_DIR, "passei_workflow_doc.md")
_GENERAL_KNOWLEDGE_PATH = os.path.join(_DOCS_DIR, "partners", "Base de conhecimento geral.md")

# Cache to avoid re-reading files on every turn
_knowledge_cache = {}

def _load_knowledge_context() -> str:
    """Pre-loads knowledge base content and returns formatted context string."""
    if "content" in _knowledge_cache:
        return _knowledge_cache["content"]
    
    print(f"[Workflow] Loading knowledge base files...")
    
    sections = []
    
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


def _build_default_context(user_id: str, profile_state: Dict, chat_history: str, ui_form_state: Optional[Dict]) -> str:
    """Builds the default context string injected into both Reasoning and Response agents."""
    
    # 1. Profile context
    profile_context = "\nPERFIL ATUAL DO ESTUDANTE:\n"
    for k, v in profile_state.items():
        if v is not None and str(v).strip() != "":
            profile_context += f"- {k}: {v}\n"
    profile_context += "\n"
    
    # 2. Form state context (from frontend, always injected — not a tool)
    form_context = ""
    if ui_form_state is not None:
        focused_field = ui_form_state.get("_focused_field", "Nenhum")
        form_data = {k: v for k, v in ui_form_state.items() if not k.startswith("_")}
        form_json = json.dumps(form_data, ensure_ascii=False)
        form_context = f"\nESTADO ATUAL DO FORMULÁRIO DO USUÁRIO: {form_json}\nCAMPO EM FOCO: {focused_field}\n"
    
    return profile_context + form_context + chat_history


async def _run_reasoning_agent(
    reasoning_agent: LlmAgent,
    user_id: str,
    session_id: str,
    message: Content,
    default_context: str,
    knowledge_context: str,
) -> str:
    """Runs the Reasoning Agent and returns its raw text output."""
    
    enriched_instruction = (
        f"USER_ID_CONTEXT: {user_id}\n\n"
        + reasoning_agent.instruction
        + "\n\n" + default_context
        + "\n" + knowledge_context
    )
    
    runnable = LlmAgent(
        model=reasoning_agent.model,
        name=reasoning_agent.name,
        description=reasoning_agent.description,
        instruction=enriched_instruction,
        tools=reasoning_agent.tools,
        output_key=reasoning_agent.output_key,
    )
    
    transient_session = InMemorySessionService()
    await transient_session.create_session(
        app_name="reasoning_pipeline",
        session_id=session_id,
        user_id=user_id,
    )
    
    runner = Runner(agent=runnable, app_name="reasoning_pipeline", session_service=transient_session)
    
    captured = ""
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        if hasattr(event, 'text') and event.text:
            captured += event.text
        elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for p in event.content.parts:
                if hasattr(p, 'text') and p.text:
                    captured += p.text
                elif hasattr(p, 'function_call') and p.function_call is not None:
                    tool_name = p.function_call.name
                    args = dict(p.function_call.args) if hasattr(p.function_call, 'args') else {}
                    yield {"type": "tool_start", "tool": tool_name, "args": args}
                elif hasattr(p, 'function_response') and p.function_response is not None:
                    tool_name = p.function_response.name
                    
                    # Convert response to dict if it's not already (ADK typically returns dicts for function_response.response)
                    resp = p.function_response.response
                    resp_dict = resp if isinstance(resp, dict) else {"result": str(resp)}
                    
                    # Yield tool end
                    yield {"type": "tool_end", "tool": tool_name, "output": json.dumps(resp_dict, ensure_ascii=False)}
                    
                    # Check for errors in tool response
                    if resp_dict.get("success") is False:
                        _log_tool_error(
                            user_id=user_id,
                            session_id=session_id,
                            tool_name=tool_name,
                            error_msg=str(resp_dict.get("error", "Unknown tool error")),
                            tb=None,
                            args=None,
                            raw_output=str(resp_dict)
                        )
                        
    # Yield the final accumulated reasoning text
    yield {"type": "final_text", "text": captured}


async def _run_response_agent(
    response_agent: LlmAgent,
    user_id: str,
    session_id: str,
    reasoning_report: str,
    user_message: str,
    default_context: str,
) -> AsyncGenerator[Any, None]:
    """Runs the Response Agent with the reasoning report and streams output."""
    
    response_input_text = f"""MENSAGEM ORIGINAL DO USUÁRIO:
{user_message}

RELATÓRIO TÉCNICO DO MÓDULO DE RACIOCÍNIO:
{reasoning_report}

{default_context}
"""
    
    enriched_instruction = (
        f"USER_ID_CONTEXT: {user_id}\n\n"
        + response_agent.instruction
    )
    
    runnable = LlmAgent(
        model=response_agent.model,
        name=response_agent.name,
        description=response_agent.description,
        instruction=enriched_instruction,
        tools=[],  # No tools — grounded by design
        output_key=response_agent.output_key,
    )
    
    runner = Runner(agent=runnable, app_name="cloudinha-agent", session_service=session_service)
    
    response_message = Content(role="user", parts=[Part(text=response_input_text)])
    
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=response_message):
        yield event


async def run_workflow(
    user_id: str,
    session_id: str,
    new_message: Content,
    ui_form_state: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Any, None]:
    """
    Orchestrates the generic agent workflow.
    
    Supports three step types:
    - "scripted": Deterministic messages (no LLM)
    - "action": Deterministic state updates (no LLM)
    - "reasoning_response": 2-agent pipeline (Reasoning → Response)
    - LlmAgent: Single agent execution (legacy/concluded)
    """
    if not check_authentication(user_id):
        yield SimpleTextEvent("Desculpe, não posso falar com você se não estiver logado.")
        return

    # 0. Fetch Initial State
    profile_state = getStudentProfileTool(user_id)
    
    msg_text = new_message.parts[0].text if new_message.parts else ""
    
    # Fetch Recent History from Session
    recent_history_str = ""
    chat_history_for_agent = ""
    active_wf = profile_state.get("active_workflow")
    try:
        session = await session_service.get_session("cloudinha-agent", session_id, user_id)
        
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

    # Force passport_workflow
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

        # 2. Get step from Workflow
        step = workflow_obj.get_agent_for_user(user_id, profile_state)
        
        if not step:
             print(f"[RunWorkflow] Workflow {workflow_obj.name} returned NO agent. Ending turn.")
             break

        # --- ACTION STEP (deterministic state update, no LLM) ---
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
             
             steps_run += 1
             continue

        # --- SCRIPTED MESSAGE (deterministic output, no LLM) ---
        if isinstance(step, dict) and step.get("type") == "scripted":
            scripted_message = step.get("message", "")
            scripted_name = step.get("name", "scripted_step")
            print(f"[RunWorkflow] Scripted step: {scripted_name} (Workflow: {workflow_obj.name})")
            
            yield SimpleTextEvent(scripted_message)
            captured_output = scripted_message
            
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

        # --- REASONING → RESPONSE PIPELINE (2-agent chain) ---
        if isinstance(step, dict) and step.get("type") == "reasoning_response":
            r_agent = step["reasoning_agent"]
            resp_agent = step["response_agent"]
            pipeline_name = step.get("name", "reasoning_response_pipeline")
            print(f"[RunWorkflow] ▶ Reasoning→Response pipeline: {pipeline_name} (Workflow: {workflow_obj.name})")
            
            # Build default context (shared by both agents)
            default_context = _build_default_context(user_id, profile_state, chat_history_for_agent, ui_form_state)
            knowledge_context = _load_knowledge_context()
            
            yield {"type": "tool_start", "tool": "reasoning_agent", "args": {"workflow": workflow_obj.name}}
            
            # === STEP 1: Reasoning Agent ===
            print(f"[RunWorkflow] 🧠 Running Reasoning Agent...")
            reasoning_raw = ""
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    async for r_event in _run_reasoning_agent(
                        reasoning_agent=r_agent,
                        user_id=user_id,
                        session_id=session_id,
                        message=current_message,
                        default_context=default_context,
                        knowledge_context=knowledge_context,
                    ):
                        if isinstance(r_event, dict):
                            if r_event.get("type") in ["tool_start", "tool_end"]:
                                yield r_event
                            elif r_event.get("type") == "final_text":
                                reasoning_raw = r_event.get("text", "")
                    break
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, ConnectionError, TimeoutError, OSError) as e:
                    print(f"[RunWorkflow] Reasoning attempt {attempt+1}/{max_retries} failed: {e}")
                    if attempt == max_retries - 1:
                        yield {"type": "error", "message": "Estou com dificuldades de conexão. Tente novamente."}
                        yield {"type": "tool_end", "tool": "reasoning_agent", "output": "Failed"}
                        return
                    await asyncio.sleep(2 ** attempt)
            
            # Log reasoning output
            user_msg_text = current_message.parts[0].text if current_message.parts else ""
            
            print(f"[RunWorkflow] 🧠 Reasoning complete. Report length: {len(reasoning_raw)} chars")
            print(f"[RunWorkflow] 🧠 Report preview: {reasoning_raw[:300]}...")
            
            yield {"type": "tool_end", "tool": "reasoning_agent", "output": "Reasoning Complete"}
            
            # === STEP 2: Response Agent ===
            print(f"[RunWorkflow] 💬 Running Response Agent...")
            yield {"type": "tool_start", "tool": "response_agent", "args": {"workflow": workflow_obj.name}}
            
            captured_output = ""
            
            for attempt in range(max_retries):
                try:
                    async for event in _run_response_agent(
                        response_agent=resp_agent,
                        user_id=user_id,
                        session_id=session_id,
                        reasoning_report=reasoning_raw,
                        user_message=user_msg_text,
                        default_context=default_context,
                    ):
                        final_event = workflow_obj.transform_event(event, resp_agent.name)
                        
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
                                    if hasattr(p, 'text') and p.text:
                                        captured_output += p.text
                    break
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, ConnectionError, TimeoutError, OSError) as e:
                    print(f"[RunWorkflow] Response attempt {attempt+1}/{max_retries} failed: {e}")
                    if attempt == max_retries - 1:
                        yield {"type": "error", "message": "Estou com dificuldades de conexão. Tente novamente."}
                        break
                    await asyncio.sleep(2 ** attempt)
                    captured_output = ""
            
            yield {"type": "tool_end", "tool": "response_agent", "output": "Response Complete"}
            
            # Handle Completion / Transitions
            updates = workflow_obj.handle_step_completion(user_id, profile_state, captured_output)
            
            state_changed = False
            if updates:
                db_updates = {k: v for k, v in updates.items() if not k.startswith("_")}
                if db_updates:
                    updateStudentProfileTool(user_id=user_id, updates=db_updates)
                profile_state.update(updates)
                state_changed = True
                
                new_workflow = updates.get("active_workflow")
                is_turn_complete = updates.get("_is_turn_complete")

                if "active_workflow" in updates and new_workflow is None:
                     print("[RunWorkflow] Workflow exited explicitly (None). Ending turn.")
                     break
                
                if is_turn_complete:
                     print("[RunWorkflow] Turn marked as complete by workflow. Ending turn.")
                     break

                if "active_workflow" in updates:
                     print(f"[RunWorkflow] State update triggered workflow change: {new_workflow}")
            
            steps_run += 1
            
            if not state_changed and not updates:
                 break
            
            if steps_run >= MAX_STEPS:
                print("[RunWorkflow] Max steps reached.")
            
            continue

        # --- SINGLE LLM AGENT (legacy/concluded) ---
        agent = step
        print(f"[RunWorkflow] Executing agent: {agent.name} (Workflow: {workflow_obj.name})")

        # Dynamic RAG / Instruction Injection
        intent_cat = "general_qa"
        if "sisu" in agent.name: intent_cat = "sisu"
        elif "prouni" in agent.name: intent_cat = "prouni"
        elif "match" in agent.name: intent_cat = "match_search"
        
        user_query_text = current_message.parts[0].text if current_message.parts else ""
        examples = retrieve_similar_examples(user_query_text, intent_cat)
        
        # Build context for single agent
        profile_context_str = "\nPERFIL ATUAL DO ESTUDANTE:\n"
        for k, v in profile_state.items():
            if v is not None and str(v).strip() != "":
                profile_context_str += f"- {k}: {v}\n"
        profile_context_str += "\n"

        if ui_form_state is not None:
            focused_field = ui_form_state.get("_focused_field", "Nenhum")
            form_data = {k: v for k, v in ui_form_state.items() if not k.startswith("_")}
            form_json = json.dumps(form_data, ensure_ascii=False)
            profile_context_str += f"\nESTADO ATUAL DO FORMULÁRIO DO USUÁRIO: {form_json}\nCAMPO EM FOCO: {focused_field}\n"
        
        knowledge_context_str = ""
        if agent.name in ("concluded_agent",):
            knowledge_context_str = _load_knowledge_context()
        
        runnable_agent = LlmAgent(
            model=agent.model,
            name=agent.name,
            description=agent.description,
            instruction=f"USER_ID_CONTEXT: {user_id}\n\n" + agent.instruction + "\n\n" + profile_context_str + chat_history_for_agent + knowledge_context_str + "\n" + examples,
            tools=agent.tools,
            output_key=agent.output_key
        )

        runner = Runner(agent=runnable_agent, app_name="cloudinha-agent", session_service=session_service)

        async for start_event in workflow_obj.on_runner_start(agent):
             yield start_event

        yield {"type": "tool_start", "tool": agent.name, "args": {"workflow": workflow_obj.name}}
        
        captured_output = ""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=current_message):
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
                
                break
            
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, ConnectionError, TimeoutError, OSError) as e:
                print(f"[RunWorkflow] Attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    yield {"type": "error", "message": "Estou com dificuldades de conexão. Tente novamente."}
                    break
                
                await asyncio.sleep(2 ** attempt)
                captured_output = "" 

        yield {"type": "tool_end", "tool": agent.name, "output": "Step Completed"}
        
        # Handle Completion / Transitions
        updates = workflow_obj.handle_step_completion(user_id, profile_state, captured_output)
        
        state_changed = False
        if updates:
            db_updates = {k: v for k, v in updates.items() if not k.startswith("_")}
            if db_updates:
                updateStudentProfileTool(user_id=user_id, updates=db_updates)
            profile_state.update(updates)
            state_changed = True
            
            new_workflow = updates.get("active_workflow")
            is_turn_complete = updates.get("_is_turn_complete")

            if "active_workflow" in updates and new_workflow is None:
                 print("[RunWorkflow] Workflow exited explicitly (None). Ending turn.")
                 break
            
            if is_turn_complete:
                 print("[RunWorkflow] Turn marked as complete by workflow. Ending turn.")
                 break

            if "active_workflow" in updates:
                 print(f"[RunWorkflow] State update triggered workflow change: {new_workflow}")

        steps_run += 1
        
        if not state_changed and not updates:
             break

        if steps_run >= MAX_STEPS:
            print("[RunWorkflow] Max steps reached.")
