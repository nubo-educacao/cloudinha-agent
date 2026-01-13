from google.adk.agents import LlmAgent
from src.tools.logModeration import logModerationTool
from .utils import load_instruction_from_file

# Define Model (can duplicate from agent.py or import config if available, using strict string for now to match agent.py)
MODEL = "gemini-1.5-flash"

guardrails_agent = LlmAgent(
    model=MODEL,
    name="guardrails_agent",
    description="Agente de segurança responsável por filtrar conteúdo nocivo.",
    instruction=load_instruction_from_file("guardrails_agent_instruction.txt"),
    tools=[logModerationTool],
    output_key="guardrails_decision"
)
