import httpx
import logging
import json
from typing import Dict, Any, Optional
from src.agent.config import WHATSAPP_API_TOKEN, WHATSAPP_PHONE_ID

logger = logging.getLogger("whatsapp-client")

class WhatsAppClient:
    def __init__(self):
        self.api_token = WHATSAPP_API_TOKEN
        self.phone_id = WHATSAPP_PHONE_ID
        self.base_url = f"https://graph.facebook.com/v21.0/{self.phone_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    async def send_message(self, to: str, body: str, preview_url: bool = False) -> Optional[Dict[str, Any]]:
        """Sends a text message to a WhatsApp user."""
        url = f"{self.base_url}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": body
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"WhatsApp API Error: {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message: {str(e)}")
                return None

    async def mark_as_read(self, message_id: str) -> bool:
        """Marks a message as read."""
        url = f"{self.base_url}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload, timeout=5.0)
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(f"Failed to mark message as read: {str(e)}")
                return False
