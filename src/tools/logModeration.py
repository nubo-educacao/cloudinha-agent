from src.lib.supabase import supabase
from datetime import datetime
import pytz

def logModerationTool(
    message_content: str,
    agent_reasoning: str,
    flagged_category: str,
    user_id: str = None
) -> str:
    """
    Logs a message that triggered the moderation filter.
    
    Args:
        message_content: The content of the user's message.
        agent_reasoning: The explanation of why this was flagged.
        flagged_category: The category of sensitive content (e.g., 'Self-Harm', 'Violence', 'Harassment').
        user_id: The UUID of the user (optional).
        
    Returns:
        A success message with the Log ID.
    """
    
    data = {
        "message_content": message_content,
        "agent_reasoning": agent_reasoning,
        "flagged_category": flagged_category,
        "user_id": user_id,
        "created_at": datetime.now(pytz.utc).isoformat()
    }

    try:
        response = supabase.table("moderation_logs").insert(data).execute()
        if response.data:
            return f"Moderation event logged successfully. Log ID: {response.data[0]['id']}"
        else:
            return "Failed to log moderation event: No data returned."
    except Exception as e:
        return f"Error logging moderation event: {str(e)}"
