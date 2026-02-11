import logging
from typing import Optional
from src.lib.supabase import supabase

logger = logging.getLogger("whatsapp-auth")

class WhatsAppAuth:
    """
    Handles authentication of WhatsApp users by matching phone numbers
    to existing auth.users in Supabase.
    """
    
    @staticmethod
    def get_user_id_by_phone(phone_number: str) -> Optional[str]:
        """
        Look up a user_id by phone number using the secure RPC.
        Expected format: E.164 (e.g., +5511999999999)
        """
        try:
            # Ensure phone has + prefix if missing (WhatsApp usually sends it without + in some contexts, 
            # but users table usually has it. Need to verify exact format from webhook later.
            # Assuming widely used E.164 with + for now).
            formatted_phone = phone_number
            if not phone_number.startswith('+'):
                 formatted_phone = f"+{phone_number}"

            response = supabase.rpc("get_user_by_phone_number", {"phone_number": formatted_phone}).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]['result_user_id']
            
            # Try without + just in case
            if formatted_phone != phone_number:
                 response_retry = supabase.rpc("get_user_by_phone_number", {"phone_number": phone_number}).execute()
                 if response_retry.data and len(response_retry.data) > 0:
                    return response_retry.data[0]['result_user_id']
            
            return None

        except Exception as e:
            logger.error(f"Error authenticating WhatsApp user {phone_number}: {e}")
            return None
