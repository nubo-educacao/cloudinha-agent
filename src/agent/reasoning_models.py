"""
Pydantic models for the Reasoning → Response agent pipeline.

ReasoningOutput is the structured contract between the Reasoning Agent and the Response Agent.
It uses a generic tools_called[] array so new tools don't require contract changes.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any


class ToolCall(BaseModel):
    """A single tool call made by the Reasoning Agent."""
    tool: str = Field(description="Name of the tool that was called")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters passed to the tool")
    result: Any = Field(default=None, description="Raw result from the tool (generic schema)")
    success: bool = Field(default=True, description="Whether the tool call succeeded")
    error: Optional[str] = Field(default=None, description="Error message if the tool call failed")


class ReasoningOutput(BaseModel):
    """
    Structured output from the Reasoning Agent.
    
    This is the sole interface between reasoning and response.
    The Response Agent can ONLY use data present in this object.
    """
    user_message: str = Field(description="Original user message, passed through verbatim")
    user_intention: str = Field(
        description=(
            "Classified intention. Examples: "
            "question_about_form_field, question_about_dates, "
            "question_about_eligibility, question_about_next_step, "
            "question_about_programs_general, workflow_response, "
            "workflow_action, greeting, unknown"
        )
    )
    intention_confidence: str = Field(
        default="medium",
        description="Confidence level: high, medium, or low"
    )
    reasoning: str = Field(
        description="1-2 sentence explanation of WHY these tools were chosen"
    )
    context_used: dict[str, Any] = Field(
        default_factory=dict,
        description="Subset of default context relevant to this decision (phase, partner, etc.)"
    )
    tools_called: List[ToolCall] = Field(
        default_factory=list,
        description="All tool calls made, in execution order. Generic schema for extensibility."
    )

    @classmethod
    def fallback(cls, user_message: str, error: str = "") -> "ReasoningOutput":
        """Creates a minimal fallback output when reasoning fails after retries."""
        return cls(
            user_message=user_message,
            user_intention="unknown",
            intention_confidence="low",
            reasoning=f"Falha na geração de output estruturado. {error}".strip(),
            context_used={},
            tools_called=[]
        )
