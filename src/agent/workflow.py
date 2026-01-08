from typing import AsyncGenerator, Any
from google.adk.runners import Runner
from google.genai.types import Content, Part
from src.agent.agent import root_agent, session_service
from src.agent.guardrails import guardrails_agent
from google.adk.sessions import InMemorySessionService
from src.agent.onboarding_workflow import onboarding_workflow
from src.agent.match_workflow import match_workflow
import functools
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.getStudentProfile import getStudentProfileTool

# Simple mock event for text responses (like Auth block)
class SimpleTextEvent:
    def __init__(self, text: str):
        self.text = text

def check_authentication(user_id: str) -> bool:
    """
    Verifies if the user is authenticated.
    Returns True if valid, False if anonymous or missing.
    """
    if not user_id or user_id.strip() == "" or user_id == "anon-user":
        return False
    return True

async def run_workflow(
    user_id: str,
    session_id: str,
    new_message: Content
) -> AsyncGenerator[Any, None]:
    """
    Orchestrates the agent workflow:
    1. Auth Check
    2. Guardrails Check
    3. Workflow Routing (Onboarding -> Match -> Root)
    """

    # 1. Auth Check
    if not check_authentication(user_id):
        yield SimpleTextEvent("Desculpe, não posso falar com você se não estiver logado.")
        return

    # 2. Guardrails Check
    transient_session_service = InMemorySessionService()

    await transient_session_service.create_session(
        app_name="guardrails-check",
        session_id=session_id,
        user_id=user_id
    )
    
    guardrails_runner = Runner(
        agent=guardrails_agent,
        app_name="guardrails-check", 
        session_service=transient_session_service
    )

    guardrails_text_buffer = ""
    guardrails_events_buffer = []

    async for event in guardrails_runner.run_async(
        user_id=user_id,
        session_id=session_id, 
        new_message=new_message
    ):
        guardrails_events_buffer.append(event)
        if hasattr(event, 'text') and event.text:
            guardrails_text_buffer += event.text
        elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
             for part in event.content.parts:
                 if hasattr(part, 'text') and part.text:
                     guardrails_text_buffer += part.text

    print(f"[Guardrails] Output: {guardrails_text_buffer}")
    decision_text = guardrails_text_buffer.strip().upper()

    if "SAFE" in decision_text:
        # 3. Safe -> Router Loop
        
        MAX_STEPS = 10 
        steps_run = 0
        current_message = new_message
        
        while steps_run < MAX_STEPS:
            # Determine Active Workflow
            profile_state = getStudentProfileTool(user_id)
            active_workflow_obj = None
            
            # Logic:
            # 1. Onboarding not completed -> Onboarding Workflow
            # 2. Onboarding completed AND active_workflow == "match" -> Match Workflow
            # 3. Else -> Root Agent (break loop)
            
            if not profile_state.get("onboarding_completed"):
                 active_workflow_obj = onboarding_workflow
            elif profile_state.get("active_workflow") == "match_workflow":
                 active_workflow_obj = match_workflow
            
            if active_workflow_obj:
                 # Check Step
                 active_step_agent = active_workflow_obj.get_agent_for_user(user_id)
                 
                 if active_step_agent:
                      print(f"[Workflow] User {user_id} in workflow '{active_workflow_obj.name}' step: {active_step_agent.name}")
                      
                      # --- DYNAMIC TOOL WRAPPER ---
                      # We create a fresh instance to ensure clean state if needed, though mostly stateless.
                      from google.adk.agents import LlmAgent
                      
                      # For Onboarding, we used a wrapper to help with args.
                      # For Match, we use tools directly.
                      # We can keep it simple here and just use the step agent's tools.
                      
                      step_agent_instance = LlmAgent(
                          model=active_step_agent.model,
                          name=active_step_agent.name,
                          description=active_step_agent.description,
                          instruction=active_step_agent.instruction,
                          tools=active_step_agent.tools,
                          output_key=active_step_agent.output_key
                      )
                      
                      step_runner = Runner(
                        agent=step_agent_instance,
                        app_name="cloudinha-agent",
                        session_service=session_service
                      )
                      
                      async for event in step_runner.run_async(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=current_message
                      ):
                          yield event
                      
                      # Check Transition
                      next_step_agent = active_workflow_obj.get_agent_for_user(user_id)
                      
                      if next_step_agent and next_step_agent.name != active_step_agent.name:
                          # Step Advanced
                          print(f"[DEBUG] State Advanced in {active_workflow_obj.name}! Triggering {next_step_agent.name}")
                          # Force next agent to speak
                          current_message = Content(role="user", parts=[Part(text="(System: Previous step completed. Proceed to next step immediately.)")])
                          
                      elif next_step_agent is None:
                          # Workflow Finished
                          print(f"[DEBUG] Workflow {active_workflow_obj.name} Complete!")
                          
                          updates = {}
                          if active_workflow_obj.name == "onboarding_workflow":
                              updates["onboarding_completed"] = True
                              current_message = Content(role="user", parts=[Part(text="(System: Onboarding complete. Answer user original request.)")])
                              
                          elif active_workflow_obj.name == "match_workflow":
                              updates["active_workflow"] = None 
                              # Let Root Agent handle "What's next?"
                              current_message = Content(role="user", parts=[Part(text="(System: Match flow complete. Ask if user needs anything else.)")])
                          
                          if updates:
                              updateStudentProfileTool(user_id=user_id, updates=updates)
                              
                      else:
                          # Same Step (Validation failed or question asked)
                          print(f"[DEBUG] Stalled in {active_step_agent.name}. Waiting for user.")
                          break
                 else:
                      # Workflow Object Active but no agent returned?
                      # Cleanup to avoid infinite loop
                      updateStudentProfileTool(user_id=user_id, updates={"active_workflow": None})
                      break

            else:
                 # Root Agent
                 root_runner = Runner(
                    agent=root_agent,
                    app_name="cloudinha-agent",
                    session_service=session_service
                 )
                 
                 async for event in root_runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=current_message 
                 ):
                    yield event
                 
                 break
            
            steps_run += 1

    else:
        # Unsafe
        print("[Guardrails] Blocked message.")
        for event in guardrails_events_buffer:
             yield event
