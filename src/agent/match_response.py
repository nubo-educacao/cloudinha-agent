from google.adk.agents import LlmAgent
from src.tools.logModeration import logModerationTool
from src.agent.agent import MODEL

from .utils import load_instruction_from_file

match_response_agent = LlmAgent(
    model=MODEL,
    name="match_response_agent",
    description="Persona responsible for communicating search results and questions to the student.",
    instruction=load_instruction_from_file("match_response_instruction.txt"),
    tools=[logModerationTool],
)
