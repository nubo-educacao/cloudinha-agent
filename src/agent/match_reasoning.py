from google.adk.agents import LlmAgent
from src.tools.updateStudentPreferences import updateStudentPreferencesTool
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.logModeration import logModerationTool
from src.tools.suggestRefinement import suggestRefinementTool
from src.tools.getImportantDates import getImportantDatesTool
from src.agent.agent import MODEL

from .utils import load_instruction_from_file

match_reasoning_agent = LlmAgent(
    model=MODEL,
    name="match_reasoning_agent",
    description="Engine responsible for executing tools and reasoning about student match preferences.",
    instruction=load_instruction_from_file("match_reasoning_instruction.txt"),
    tools=[
        logModerationTool,
        updateStudentPreferencesTool,
        searchOpportunitiesTool,
        getStudentProfileTool,
        suggestRefinementTool,
        getImportantDatesTool
    ],
)
