from google.adk.agents import LlmAgent
from src.tools.updateStudentPreferences import updateStudentPreferencesTool
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.logModeration import logModerationTool
from src.tools.suggestRefinement import suggestRefinementTool
from src.tools.getImportantDates import getImportantDatesTool
from src.agent.config import MODEL_REASONING
from src.lib.error_handler import safe_execution
from src.agent.agent import session_service
from google.adk.runners import Runner
from typing import AsyncGenerator, Any

from .utils import load_instruction_from_file

match_reasoning_agent = LlmAgent(
    model=MODEL_REASONING,
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

@safe_execution(error_type="reasoning_agent_error", default_return=None) # default_return ignored for async gen
async def execute_match_reasoning(
    user_id: str, 
    session_id: str, 
    current_message: Any
) -> AsyncGenerator[Any, None]:
    """
    Executes the Match Reasoning Engine loop.
    Yields events from the runner.
    """
    # 1. Run Reasoning Agent (Tool Execution & Logic)
    # We do NOT let it stream text to the user to avoid breaking character.
    # We DO stream tool events so the user sees "Searching...".
    
    # Dynamically instantiate to inject USER_ID_CONTEXT
    reasoning_instance = LlmAgent(
        model=match_reasoning_agent.model,
        name=match_reasoning_agent.name,
        description=match_reasoning_agent.description,
        instruction=f"USER_ID_CONTEXT: {user_id}\n" + match_reasoning_agent.instruction,
        tools=match_reasoning_agent.tools
    )

    r_runner = Runner(agent=reasoning_instance, app_name="cloudinha-agent", session_service=session_service)
    
    # Yield "Thinking" event? 
    yield {
        "type": "tool_start",
        "tool": "ReasoningEngine",
        "args": {"action": "analyzing_request"}
    }

    async for r_event in r_runner.run_async(user_id=user_id, session_id=session_id, new_message=current_message):
        # Pass through tool events (if ADK sends them as dicts) or convert if objects
        yield r_event
