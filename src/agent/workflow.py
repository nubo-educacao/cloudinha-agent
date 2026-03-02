from typing import AsyncGenerator, Any, Dict, Optional
import asyncio
import httpx
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

# Workflows
from src.agent.base_workflow import SingleAgentWorkflow
from src.agent.onboarding_workflow import onboarding_workflow
from src.agent.match_workflow import MatchWorkflow
from src.agent.passport_workflow import PassportWorkflow

# Initialize Registry
workflow_registry = {
    "match_workflow": MatchWorkflow(),
    "sisu_workflow": SingleAgentWorkflow(sisu_agent, "sisu_workflow"),
    "prouni_workflow": SingleAgentWorkflow(prouni_agent, "prouni_workflow"),
    "onboarding_workflow": onboarding_workflow,
    "passport_workflow": PassportWorkflow()
}

# Wrapper for Root (Default)
root_workflow = SingleAgentWorkflow(root_agent, "root_workflow")

class SimpleTextEvent:
    def __init__(self, text: str):
        self.text = text

def check_authentication(user_id: str) -> bool:
    return bool(user_id and user_id.strip() != "" and user_id != "anon-user")

async def run_workflow(
    user_id: str,
    session_id: str,
    new_message: Content
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

    # Migrate legacy workflows to passport_workflow
    # Users who had match_workflow/sisu_workflow/prouni_workflow as active should go through passport_workflow now
    LEGACY_WORKFLOWS = {"match_workflow", "sisu_workflow", "prouni_workflow", "onboarding_workflow"}
    active_wf = profile_state.get("active_workflow")
    if active_wf in LEGACY_WORKFLOWS:
        print(f"[RunWorkflow] Migrating legacy workflow '{active_wf}' -> 'passport_workflow'")
        updateStudentProfileTool(user_id=user_id, updates={"active_workflow": "passport_workflow"})
        profile_state = getStudentProfileTool(user_id)
        active_wf = "passport_workflow"

    # Only run router if user already has an active workflow (to decide CONTINUE vs CHANGE)
    # For brand new users, we default to passport_workflow below
    if active_wf:
        decision = await execute_router_agent(user_id, session_id, msg_text, profile_state, recent_history=recent_history_str)
        
        if decision:
             intent = decision.get("intent")
             target = decision.get("target_workflow")
             
             if intent == "CHANGE_WORKFLOW" and target:
                 yield {"type": "tool_start", "tool": "RouterAgent", "args": {"action": "switch", "target": target}}
                 updateStudentProfileTool(user_id=user_id, updates={"active_workflow": target})
                 profile_state = getStudentProfileTool(user_id) # Refresh
                 yield {"type": "tool_end", "tool": "RouterAgent", "output": f"Sent to {target}"}
                 
             elif intent == "EXIT_WORKFLOW":
                 yield {"type": "tool_start", "tool": "RouterAgent", "args": {"action": "exit"}}
                 updateStudentProfileTool(user_id=user_id, updates={"active_workflow": None})
                 profile_state = getStudentProfileTool(user_id) # Refresh
                 yield {"type": "tool_end", "tool": "RouterAgent", "output": "Exited workflow"}
    else:
        # No active workflow — default to passport_workflow
        updateStudentProfileTool(user_id=user_id, updates={"active_workflow": "passport_workflow"})
        profile_state = getStudentProfileTool(user_id)
        # Ensure it's set in the local dict just in case cache delayed the read
        profile_state["active_workflow"] = "passport_workflow"

    # Main Loop
    MAX_STEPS = 10
    steps_run = 0
    current_message = new_message

    while steps_run < MAX_STEPS:
        
        # 1. Determine Active Workflow
        active_workflow_name = profile_state.get("active_workflow")
        workflow_obj = None

        # passport_workflow is the default entry point for everything
        # It handles onboarding internally
        if active_workflow_name in workflow_registry:
            workflow_obj = workflow_registry[active_workflow_name]
        else:
            workflow_obj = root_workflow # Fallback

        # 2. Get Agent or Scripted Message from Workflow
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
        
        # Create Runner Instance (Clone agent with new instruction)
        # Inject: USER_ID_CONTEXT + profile_state + chat history + original instruction + RAG examples
        runnable_agent = LlmAgent(
            model=agent.model,
            name=agent.name,
            description=agent.description,
            instruction=f"USER_ID_CONTEXT: {user_id}\n" + profile_context_str + chat_history_for_agent + agent.instruction + "\n" + examples,
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
