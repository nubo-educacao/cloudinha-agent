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

# Initialize Registry
workflow_registry = {
    "match_workflow": MatchWorkflow(),
    "sisu_workflow": SingleAgentWorkflow(sisu_agent, "sisu_workflow"),
    "prouni_workflow": SingleAgentWorkflow(prouni_agent, "prouni_workflow"),
    "onboarding_workflow": onboarding_workflow
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
    
    # Pre-loop Router check (Steps == 0 logic)
    # Only run Router if onboarding is complete
    if profile_state.get("onboarding_completed"):
        msg_text = new_message.parts[0].text if new_message.parts else ""
        decision = await execute_router_agent(user_id, session_id, msg_text, profile_state)
        
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

    # Main Loop
    MAX_STEPS = 10
    steps_run = 0
    current_message = new_message

    while steps_run < MAX_STEPS:
        
        # 1. Determine Active Workflow
        active_workflow_name = profile_state.get("active_workflow")
        workflow_obj = None

        if not profile_state.get("onboarding_completed"):
            workflow_obj = workflow_registry["onboarding_workflow"]
            # Enforce state consistency
            if active_workflow_name != "onboarding_workflow":
                updateStudentProfileTool(user_id=user_id, updates={"active_workflow": "onboarding_workflow"})
                active_workflow_name = "onboarding_workflow" 
        
        elif active_workflow_name in workflow_registry:
            workflow_obj = workflow_registry[active_workflow_name]
        
        else:
            workflow_obj = root_workflow # Default

        # 2. Get Agent from Workflow
        # Pass copy of state to be safe? getStudentProfileTool returns dict.
        agent = workflow_obj.get_agent_for_user(user_id, profile_state)
        
        if not agent:
             # Workflow returned None, meaning it's done or yielded without agent
             # For Onboarding, this means complete. for Match, handled internally.
             # If we are here, essentially we break or fallback to Root?
             # If Onboarding finished, we break loop to let user reply?
             print(f"[RunWorkflow] Workflow {workflow_obj.name} returned NO agent. Ending turn.")
             break

        print(f"[RunWorkflow] Executing agent: {agent.name} (Workflow: {workflow_obj.name})")

        # 3. Dynamic RAG / Instruction Injection
        # We need to inject examples. Identify category.
        intent_cat = "general_qa"
        if "sisu" in agent.name: intent_cat = "sisu"
        elif "prouni" in agent.name: intent_cat = "prouni"
        elif "match" in agent.name: intent_cat = "match_search"
        
        user_query_text = current_message.parts[0].text if current_message.parts else ""
        examples = retrieve_similar_examples(user_query_text, intent_cat)
        
        # Create Runner Instance (Clone agent with new instruction)
        # Note: We append examples to existing instruction.
        # This handles the "context injection" done by MatchWorkflow too (it appended to instruction).
        runnable_agent = LlmAgent(
            model=agent.model,
            name=agent.name,
            description=agent.description,
            instruction=f"USER_ID_CONTEXT: {user_id}\n" + agent.instruction + "\n" + examples,
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
                    # We might want to break or continue? If we break, we exit the step.
                    # If we don't re-raise, we proceed to 'handle_step_completion' with whatever captured_output we have.
                    break
                
                # Backoff
                await asyncio.sleep(2 ** attempt)
                # Continue to next attempt (restart runner.run_async)
                # Note: captured_output might have partial data. 
                # Ideally we reset it? 
                captured_output = "" 
                # Also, we might have yielded partial events.


        yield {"type": "tool_end", "tool": agent.name, "output": "Step Completed"}
        
        # 5. Handle Completion / Transitions
        updates = workflow_obj.handle_step_completion(user_id, profile_state, captured_output)
        
        state_changed = False
        if updates:
            updateStudentProfileTool(user_id=user_id, updates=updates)
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
