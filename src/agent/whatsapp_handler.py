import logging
import asyncio
from typing import Dict, Any, List
from google.genai.types import Content, Part
from src.agent.workflow import run_workflow
from src.lib.whatsapp_client import WhatsAppClient
from src.lib.whatsapp_auth import WhatsAppAuth

logger = logging.getLogger("whatsapp-handler")
whatsapp_client = WhatsAppClient()

async def handle_whatsapp_message(phone_number: str, message_body: str, message_id: str):
    """
    Process an incoming WhatsApp message:
    1. Authenticate user by phone.
    2. Run agent workflow.
    3. Send responses back to WhatsApp.
    """
    try:
        # 1. Authenticate
        user_id = WhatsAppAuth.get_user_id_by_phone(phone_number)
        
        if not user_id:
            logger.warning(f"Message from unknown user: {phone_number}")
            await whatsapp_client.send_message(phone_number, "Desculpe, seu número não está cadastrado no Cloudinha. Entre em contato com o suporte ou cadastre-se no site.")
            return

        # 2. Prepare Session
        # WhatsApp users share the same session ID format but specific to this channel?
        # Or should we reuse the same session logic?
        # server.py uses "session-{user_id}". Let's align with that to maintain state if they switch.
        # But maybe we want distinct history? Let's use same for continuity.
        session_id = f"session-{user_id}" 
        
        # 3. Mark as Read (Good UX)
        await whatsapp_client.mark_as_read(message_id)

        # 4. Run Workflow
        new_message = Content(parts=[Part(text=message_body)])
        
        response_buffer = ""
        
        # We need to adapt the event loop from server.py but for WhatsApp
        async for event in run_workflow(user_id, session_id, new_message):
            try:
                # Handle Dict events (Tools/Control)
                if isinstance(event, dict):
                    event_type = event.get("type")
                    
                    if event_type == "tool_start":
                        # If we have text buffered before a tool starts, flush it
                        if response_buffer.strip():
                            await whatsapp_client.send_message(phone_number, response_buffer)
                            response_buffer = ""
                        
                        # Optional: Send a "typing" or "working" indicator?
                        # For now, silence is golden, or maybe emoji?
                        # await whatsapp_client.send_message(phone_number, "⏳ Buscando informações...")
                        pass

                    elif event_type == "error":
                        error_msg = event.get("content") or event.get("message")
                        await whatsapp_client.send_message(phone_number, f"⚠️ Erro: {error_msg}")
                    
                    continue

                # Handle Text Events from Google ADK
                text_chunk = ""
                
                if hasattr(event, 'text') and event.text:
                    text_chunk = event.text
                elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                     for part in event.content.parts:
                         if hasattr(part, 'text') and part.text:
                             text_chunk += part.text
                
                if text_chunk:
                    response_buffer += text_chunk

            except Exception as loop_error:
                logger.error(f"Error in workflow loop for {phone_number}: {loop_error}")

        # 5. Send remaining buffer
        if response_buffer.strip():
             await whatsapp_client.send_message(phone_number, response_buffer)
        
    except Exception as e:
        logger.error(f"Critical error handling WhatsApp message for {phone_number}: {e}", exc_info=True)
        # Optional: Send generic error to user
