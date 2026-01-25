from typing import Any, Dict, Optional, AsyncGenerator
from google.adk.agents import LlmAgent, Agent
from google.genai.types import Content, Part
from src.agent.base_workflow import BaseWorkflow
from src.agent.match_reasoning import match_reasoning_agent
from src.agent.match_response import match_response_agent
from src.agent.config import MODEL_ROUTER

# Simple blocker agent definition
wizard_blocker_agent = LlmAgent(
    model=MODEL_ROUTER, # Lightweight model or just a dummy
    name="wizard_blocker",
    description="Asks user to complete registration.",
    instruction="Check if the user has provided their Enem Score and Income. If not, politely ask them to complete the registration form or provide the missing data here.",
    tools=[]
)

class MatchWorkflow(BaseWorkflow):
    @property
    def name(self) -> str:
        return "match_workflow"

    def get_agent_for_user(self, user_id: str, current_state: Dict[str, Any]) -> Agent:
        # 1. Wizard Check
        registration_step = current_state.get("registration_step")
        is_wizard_complete = (registration_step == 'completed')
        
        if not is_wizard_complete:
            return wizard_blocker_agent

        # 2. Match Pipeline Phase Check
        match_phase = current_state.get("_match_phase") # Transient state
        
        if match_phase == "response":
            # Reasoning done, run Response Agent
            reasoning_output = current_state.get("_reasoning_output", "")
            
            # Inject context into a fresh instance of the response agent
            # We wrap the original agent to modify its instruction/input context dynamically
            # Ideally we'd modify the *message*, but here we return an Agent.
            # We can prepend the context to the system instruction.
            context_instruction = f"\n\nCONTEXT FROM REASONING ENGINE:\n{reasoning_output}\n"
            
            response_instance = LlmAgent(
                model=match_response_agent.model,
                name=match_response_agent.name,
                description=match_response_agent.description,
                instruction=match_response_agent.instruction + context_instruction,
                tools=match_response_agent.tools
            )
            return response_instance
            
        else:
            # Default: Reasoning Agent
            return match_reasoning_agent

    def transform_event(self, event: Any, agent_name: str) -> Optional[Any]:
        if agent_name == "wizard_blocker":
            # Suppress text from wizard_blocker agent to avoid duplication with static message in on_runner_start
            text_content = ""
            if hasattr(event, 'text') and event.text:
                return None
            elif hasattr(event, 'content') and event.content and event.content.parts:
                return None
            return event

        if agent_name == match_reasoning_agent.name:
            # Aggressive Suppression for Reasoning Agent
            
            # Check for text attributes
            text_content = ""
            if hasattr(event, 'text') and event.text:
                text_content = event.text
            elif hasattr(event, 'content') and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_content += part.text
            
            # If it contains the reasoning tag, suppress entirely
            if "[REASONING_REPORT]" in text_content:
                return None
                
            # If it's a tool event, allow it
            if isinstance(event, dict) and event.get("type") in ["tool_start", "tool_end"]:
                return event
            
            # Default to suppressing all text from reasoning agent to be safe
            # The Reasoning agent should ONLY communicate via tool events or internal state
            if text_content.strip():
                 return None

        return event

    async def on_runner_start(self, agent: Agent) -> AsyncGenerator[Any, None]:
        if agent.name == "wizard_blocker":
             yield {
                "type": "control",
                "action": "block_input",
                "reason": "wizard_incomplete"
            }
             yield {
                "type": "text",
                "content": "Para que eu possa encontrar o seu match ideal, preciso que você complete o seu perfil (Nota e Renda) primeiro. 😊"
             }

    def handle_step_completion(self, user_id: str, current_state: Dict[str, Any], step_output: str) -> Optional[Dict[str, Any]]:
        agent_name = "unknown"
        # We need to know which agent just ran.
        # Ideally passed in args, or inferred from state.
        # But 'step_output' implies we just finished a step.
        
        match_phase = current_state.get("_match_phase")
        
        if match_phase == "response":
            # Response finished
            return {
                "_match_phase": None,
                "_reasoning_output": None,
                "_is_turn_complete": True # Signal for workflow engine to stop for this turn
            }
        
        # Check if we were in the wizard blocker
        # If wizard complete? We don't know if the user completed it just by chatting.
        # But if we are here, the agent finished.
        registration_step = current_state.get("registration_step")
        if registration_step != 'completed':
            return None # Still blocked
            
        # Reasoning finished (implied if not response and not blocked)
        return {
            "_match_phase": "response",
            "_reasoning_output": step_output
        }
