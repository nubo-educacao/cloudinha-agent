from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from google.adk.agents import Agent
from google.genai.types import Tool

@dataclass
class WorkflowStep:
    name: str
    condition: Callable[[Dict[str, Any]], bool]  # Returns True if step is COMPLETE
    agent: Agent  # The agent to use for this step

class WorkflowAgent:
    """
    A helper class to manage state-based agent selection.
    This is NOT a direct subclass of ADK Agent because ADK Agents are typically static configurations.
    Instead, this class acts as a factory/router.
    """
    def __init__(
        self,
        name: str,
        steps: List[WorkflowStep],
        get_state_fn: Callable[[str], Dict[str, Any]],
        on_complete_agent: Optional[Agent] = None
    ):
        self.name = name
        self.steps = steps
        self.get_state_fn = get_state_fn
        self.on_complete_agent = on_complete_agent

    def get_agent_for_user(self, user_id: str) -> Optional[Agent]:
        """
        Determines the correct agent for the user based on their workflow state.
        Returns None if workflow is complete and no on_complete_agent is set.
        """
        state = self.get_state_fn(user_id)
        
        for step in self.steps:
            if not step.condition(state):
                # Found the first incomplete step
                return step.agent
        
        return self.on_complete_agent
