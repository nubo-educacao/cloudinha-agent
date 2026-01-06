from typing import AsyncGenerator, Any
from google.adk.runners import Runner
from google.genai.types import Content, Part
from src.agent.agent import root_agent, session_service
from src.agent.guardrails import guardrails_agent
from google.adk.sessions import InMemorySessionService
from src.agent.onboarding_workflow import onboarding_workflow
import functools
from src.tools.updateStudentProfile import updateStudentProfileTool

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
    3. Root Agent (if safe)
    """
    

    # 1. Auth Check
    if not check_authentication(user_id):
        yield SimpleTextEvent("Desculpe, não posso falar com você se não estiver logado.")
        return

    # 2. Guardrails Check
    # We run the guardrails agent in a separate runner loop.
    # We use a transient InMemorySessionService to avoid polluting the main conversation history/DB.
    transient_session_service = InMemorySessionService()

    # FIX: Create the session in the transient service before usage
    await transient_session_service.create_session(
        app_name="guardrails-check",
        session_id=session_id,
        user_id=user_id
    )
    
    # We buffer the output to decide whether to proceed or block.
    guardrails_runner = Runner(
        agent=guardrails_agent,
        app_name="guardrails-check", 
        session_service=transient_session_service
    )

    guardrails_text_buffer = ""
    guardrails_events_buffer = []

    # Run guardrails
    async for event in guardrails_runner.run_async(
        user_id=user_id,
        session_id=session_id, # Reusing session might pollute history with "SAFE"? 
        # Ideally, guardrails should be stateless or use a transient session.
        # But ADK requires a session. Let's use the same session but maybe we can't avoid history pollution easily 
        # without a separate session ID.
        # Using a prefixed session ID for guardrails to avoid polluting the main chat history.
        # This prevents the user from seeing "SAFE" in their history context for the next turn.
        new_message=new_message
    ):
        guardrails_events_buffer.append(event)
        if hasattr(event, 'text') and event.text:
            guardrails_text_buffer += event.text
        elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
             for part in event.content.parts:
                 if hasattr(part, 'text') and part.text:
                     guardrails_text_buffer += part.text

    # Log/Debug
    print(f"[Guardrails] Output: {guardrails_text_buffer}")

    # Check decision
    # Normalize cleanup
    decision_text = guardrails_text_buffer.strip().upper()

    if "SAFE" in decision_text:
        # 3. Safe -> Check Onboarding -> Proceed
        
        # --- ONBOARDING & ROUTING LOOP ---
        # We use a loop to allow chaining agents (e.g., Name -> Age transition in one turn)
        # or handing off to Root Agent immediately after Onboarding finishes.
        
        MAX_STEPS = 5
        steps_run = 0
        current_message = new_message
        
        while steps_run < MAX_STEPS:
            # Check Onboarding State
            active_step_agent = onboarding_workflow.get_agent_for_user(user_id)
            
            if active_step_agent:
                 print(f"[Workflow] User {user_id} in onboarding step: {active_step_agent.name}")
                 
                 # INJECT user_id into the tool
                 # We define a wrapper function with EXPLICIT arguments for each field.
                 # This is easier for the LLM than a generic dict.
                 
                 def update_student_info(
                     full_name: str = None,
                     age: int = None,
                     city_name: str = None,
                     education: str = None
                 ):
                     """
                     Atualiza o perfil do estudante com as informações fornecidas.
                     Você deve preencher APENAS o campo relevante para a pergunta atual.
                     
                     Args:
                        full_name (str, optional): O nome completo do usuário.
                        age (int, optional): A idade do usuário.
                        city_name (str, optional): A cidade e estado do usuário.
                        education (str, optional): A escolaridade atual do usuário (Ensino Médio, etc).
                     """
                     updates = {}
                     if full_name: updates["full_name"] = full_name
                     if age: updates["age"] = age
                     if city_name: updates["city_name"] = city_name
                     if education: updates["education"] = education
                     
                     print(f"!!! [DEBUG TOOL] update_student_info CALLED for {user_id} with {updates}")
                     return updateStudentProfileTool(user_id=user_id, updates=updates)
                 
                 update_student_info.__name__ = "updateStudentProfileTool"
                 
                 # Create a COPY of the agent config
                 from google.adk.agents import LlmAgent
                 
                 # We need to make sure the tool list is correct.
                 step_agent_instance = LlmAgent(
                     model=active_step_agent.model,
                     name=active_step_agent.name,
                     description=active_step_agent.description,
                     instruction=active_step_agent.instruction,
                     tools=[update_student_info], 
                     output_key=active_step_agent.output_key
                 )
                 
                 print(f"[DEBUG] instance tools: {[t.__name__ for t in step_agent_instance.tools]}")
                 
                 # Run the specific step agent
                 step_runner = Runner(
                    agent=step_agent_instance,
                    app_name="cloudinha-agent",
                    session_service=session_service
                 )
                 
                 # capture events to decide if we should break (e.g. if we generated text)
                 # But efficiently, we just yield them.
                 # The key is to check if STATE changed after the run.
                 
                 async for event in step_runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=current_message
                 ):
                     yield event
                 
                 # Check State Again to see if we transitioned
                 next_step_agent = onboarding_workflow.get_agent_for_user(user_id)
                 print(f"[DEBUG] Transition Check: Active={active_step_agent.name}, Next={next_step_agent.name if next_step_agent else 'None'}")
                 
                 if next_step_agent and next_step_agent.name != active_step_agent.name:
                     # State Advanced! (Name -> Age)
                     print(f"[DEBUG] State Advanced! Triggering {next_step_agent.name}")
                     
                     # Force the next agent to speak by simulating a System "User" message
                     # This ensures the model knows it's its turn to ask the next question.
                     current_message = Content(role="user", parts=[Part(text="(System: The previous step was completed successfully. Now, proceed immediately to your specific task (e.g. asking for age/city). Do not repeat greetings.)")])
                     
                 elif next_step_agent is None:
                     # State Advanced! (Education -> Complete/Root)
                     print("[DEBUG] Onboarding Complete! Handing off to Root Agent.")
                     # EXPLICITLY set onboarding_completed = True in DB
                     print(f"[DEBUG] Persisting onboarding_completed=True for {user_id}")
                     updateStudentProfileTool(user_id=user_id, updates={"onboarding_completed": True})

                     # Onboarding just finished.
                     # We want to run Root Agent immediately.
                     # We update current_message to None to avoid duplicating user input.
                     current_message = Content(role="user", parts=[Part(text="(System: Onboarding complete. Please answer the user's original request now.)")])
                 else:
                     # State stayed same (Validation failed or question asked)
                     print(f"[DEBUG] State stayed same ({active_step_agent.name}). Waiting for user input.")
                     break
            
            else:
                # 4. Safe & Onboarded -> Root Agent
                # Run root agent
                # Note: We use the original session_id
                
                # If we just came from onboarding (current_message is None), we want RootAgent to pick up context.
                # Use a specific instruction if valid?
                
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
                
                # Exit loop after running root agent
                break
            
            steps_run += 1

    else:
        # Unsafe -> Return the block message generated by Guardrails
        # Yield the buffered events (or just the text)
        print("[Guardrails] Blocked message.")
        for event in guardrails_events_buffer:
             yield event
