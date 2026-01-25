from datetime import datetime, timedelta, timezone
from src.lib.supabase import supabase
import logging

logger = logging.getLogger("middleware")

MAX_MESSAGES = 20
WINDOW_SECONDS = 60

async def check_rate_limit(user_id: str) -> bool:
    """
    Checks if a user has exceeded the rate limit.
    Returns True if allowed, False if blocked.
    """
    if not user_id or user_id == "user":
        # Skip for generic/test users if needed, or enforce. 
        # Let's enforce for anyone not "anon" (which server already checks).
        pass

    now = datetime.now(timezone.utc)
    
    try:
        # 1. Get current limit info
        response = supabase.table("user_rate_limits").select("*").eq("user_id", user_id).execute()
        data = response.data
        
        if not data:
            # First time user, insert record
            supabase.table("user_rate_limits").insert({
                "user_id": user_id,
                "last_message_at": now.isoformat(),
                "message_count_window": 1
            }).execute()
            return True
        
        record = data[0]
        last_at = datetime.fromisoformat(record["last_message_at"])
        count = record["message_count_window"]
        
        # Check window
        time_diff = (now - last_at).total_seconds()
        
        if time_diff > WINDOW_SECONDS:
            # Reset window
            supabase.table("user_rate_limits").update({
                "last_message_at": now.isoformat(),
                "message_count_window": 1
            }).eq("user_id", user_id).execute()
            return True
        else:
            # Inside window, check count
            if count >= MAX_MESSAGES:
                logger.warning(f"Rate limit exceeded for user {user_id}: {count} messages in {time_diff:.1f}s")
                return False
            else:
                # Increment
                supabase.table("user_rate_limits").update({
                    "message_count_window": count + 1,
                    # We don't update last_message_at to keep the window fixed from start? 
                    # OR we use sliding window?
                    # The prompt says "Max 20 messages per minute".
                    # Simple implementation: Reset if last_message_at > 60s ago. 
                    # Else increment.
                    # This creates a "fixed window from first message" bucket.
                }).eq("user_id", user_id).execute()
                return True

    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        # Fail open (allow) if DB error to avoid blocking valid users during outages?
        # Or Fail closed? 
        # "O sistema não possui proteção ... Objetivo: Adicionar proteção"
        # Safe to fail open for resilience if DB is down, but bad for DDOS.
        # Let's fail open but log.
        return True
