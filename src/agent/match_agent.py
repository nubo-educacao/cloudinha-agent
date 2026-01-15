from google.adk.agents import LlmAgent
from src.tools.updateStudentPreferences import updateStudentPreferencesTool
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.suggestRefinement import suggestRefinementTool
from src.tools.logModeration import logModerationTool
from src.agent.agent import MODEL

from .utils import load_instruction_from_file

match_agent = LlmAgent(
    model=MODEL,
    name="match_agent",
    description="Busca e refina oportunidades de faculdade e bolsas (Sisu, Prouni) de forma iterativa.",
    instruction=load_instruction_from_file("match_agent_instruction.txt") + "\n\n" + load_instruction_from_file("persona.txt"),
    tools=[logModerationTool, updateStudentPreferencesTool, searchOpportunitiesTool, suggestRefinementTool],
)
