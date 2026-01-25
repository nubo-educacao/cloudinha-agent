from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, AsyncGenerator
from google.adk.agents import Agent

class BaseWorkflow(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_agent_for_user(self, user_id: str, current_state: Dict[str, Any]) -> Optional[Agent]:
        # Returns the agent object to be executed.
        pass

    def transform_event(self, event: Any, agent_name: str) -> Optional[Any]:
        """
        Allows the workflow to filter or modify events from the agent runner.
        Return None to suppress the event.
        """
        return event

    async def on_runner_start(self, agent: Agent) -> AsyncGenerator[Any, None]:
        """
        Yields events before the runner starts (e.g., control events).
        """
        if False: yield
        return

    def handle_step_completion(self, user_id: str, current_state: Dict[str, Any], step_output: str) -> Optional[Dict[str, Any]]:
        """
        Hook for post-step logic (e.g., transitions, state cleanup).
        Called after the agent execution loop finishes a turn.
        Returns a dictionary of profile updates if any.
        """
        return None

class SingleAgentWorkflow(BaseWorkflow):
    """
    A simple wrapper for a single agent (like Sisu or Prouni) that acts as a workflow.
    """
    def __init__(self, agent: Agent, workflow_name: str):
        self.agent = agent
        self._name = workflow_name

    @property
    def name(self) -> str:
        return self._name

    def get_agent_for_user(self, user_id: str, current_state: Dict[str, Any]) -> Optional[Agent]:
        return self.agent
