from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.updateStudentProfile import updateStudentProfileTool
from src.tools.logModeration import logModerationTool
from src.tools.getImportantDates import getImportantDatesTool
from src.tools.smartResearch import smartResearchTool
from .utils import load_instruction_from_file

load_dotenv()



MODEL="gemini-2.0-flash"

# --- Sub Agent 1: Onboarding Agent ---
onboarding_agent = LlmAgent(
    model=MODEL,
    name="onboarding_agent",
    description="Você é a Cloudinha, uma assistente virtual amigável e acolhedora da Nubo Educação! 🌟",
    instruction=load_instruction_from_file("onboarding_agent_instruction.txt"),
    tools=[getStudentProfileTool, updateStudentProfileTool],
    output_key="onboarding_report",
)

# --- Sub Agent 2: Match Agent (REMOVED - Replaced by Match Workflow)
# match_agent logic is now handled by src/agent/match_workflow.py triggered by active_workflow state.


# --- Sub Agent 3: Prouni Agent (RAG) ---
prouni_agent = LlmAgent(
    model=MODEL,
    name="prouni_agent",
    description="Especialista no Programa Universidade para Todos (Prouni). Responde dúvidas sobre bolsas, regras e documentação.",
    instruction=load_instruction_from_file("prouni_agent_instruction.txt"),
    tools=[smartResearchTool, getImportantDatesTool, getStudentProfileTool, updateStudentProfileTool],
    output_key="prouni_report",
)

# --- Sub Agent 4: Sisu Agent (RAG) ---
sisu_agent = LlmAgent(
    model=MODEL,
    name="sisu_agent",
    description="Especialista no Sistema de Seleção Unificada (Sisu). Responde dúvidas sobre inscrição, nota de corte e cotas.",
    instruction=load_instruction_from_file("sisu_agent_instruction.txt"),
    tools=[smartResearchTool, getImportantDatesTool, getStudentProfileTool, updateStudentProfileTool],
    output_key="sisu_report",
)

root_agent = LlmAgent(
    model=MODEL,
    name="cloudinha_agent",
    description="Você é a Cloudinha do Nubo! Uma assistente virtual animada, acolhedora e cheia de energia positiva ☁️✨. Especialista em ajudar estudantes com Prouni, Sisu e acesso ao ensino superior.",
    instruction=load_instruction_from_file("root_agent_instruction.txt"),
    # sub_agents=[prouni_agent, sisu_agent], # Match agent removed from direct sub-agents
    sub_agents=[prouni_agent, sisu_agent],
    tools=[logModerationTool, getStudentProfileTool, updateStudentProfileTool]
)

# --- Root Agent for the Runner ---
# The runner will now execute the workflow
agent = root_agent

# --- Persistence & Runner Configuration ---
# Initializing here allows both server.py and adk web (debug) to share the same persistence logic.
from supabase import create_client
from google.adk.runners import Runner
from src.agent.memory.supabase_session import SupabaseSessionService
import os

# Initialize Supabase Client
supabase_url = os.getenv("SUPABASE_URL")
service_role_key = os.getenv("SUPABASE_SERVICE_KEY")
anon_key = os.getenv("SUPABASE_KEY")

print(f"[DEBUG KEY] Service Role Key Present: {bool(service_role_key)}")
print(f"[DEBUG KEY] Anon Key Present: {bool(anon_key)}")

if service_role_key:
    print("[DEBUG KEY] Using SUPABASE_SERVICE_KEY")
    supabase_key = service_role_key
else:
    print("[DEBUG KEY] Using SUPABASE_KEY (Anon) - WARNING: RLS may block writes")
    supabase_key = anon_key

if not supabase_url or not supabase_key:
    print("Warning: Supabase credentials not found. Persistence might fail.")
    # Fallback or error handling depending on strictness requirements
    supabase_client = None 
else:
    supabase_client = create_client(supabase_url, supabase_key)

# Initialize Session Service
if supabase_client:
    session_service = SupabaseSessionService()
    session_service.set_client(supabase_client)
else:
    # Fallback to in-memory if no credentials (optional, for safety)
    from google.adk.sessions import InMemorySessionService
    session_service = InMemorySessionService()
    print("Fallback: Using InMemorySessionService due to missing credentials.")

# Initialize Runner
runner = Runner(
    agent=agent,
    app_name="cloudinha-agent",
    session_service=session_service
)

