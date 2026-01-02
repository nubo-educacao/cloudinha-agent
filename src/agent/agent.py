from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.updateStudentProfile import updateStudentProfileTool
from util import load_instruction_from_file

load_dotenv()



MODEL="gemini-2.0-flash-exp"

# --- Sub Agent 1: Onboarding Agent ---
onboarding_agent = LlmAgent(
    model=MODEL,
    name="onboarding_agent",
    description="Você é a Cloudinha, uma assistente virtual amigável e acolhedora da Nubo Educação! 🌟",
    instruction=load_instruction_from_file("onboarding_agent_instruction.txt"),
    tools=[getStudentProfileTool, updateStudentProfileTool],
    output_key="onboarding_report",
)

# --- Sub Agent 2: Match Agent ---
match_agent = LlmAgent(
    model=MODEL,
    name="match_agent",
    description="Você é o Match, um assistente especializado em Prouni e Sisu.",
    instruction=load_instruction_from_file("match_agent_instruction.txt"),
    tools=[searchOpportunitiesTool, getStudentProfileTool],
    output_key="match_report",
)

root_agent = LlmAgent(
    model=MODEL,
    name="cloudinha_agent",
    description="Você é a Cloudinha, uma assistente especializada em Prouni e Sisu.",
    instruction=load_instruction_from_file("root_agent_instruction.txt"),
    sub_agents=[onboarding_agent, match_agent]
)

# --- Root Agent for the Runner ---
# The runner will now execute the workflow
agent = root_agent

from google.genai import types
from google.adk.sessions import InMemorySession
from google.adk.runners import Runner
from util import load_instruction_from_file