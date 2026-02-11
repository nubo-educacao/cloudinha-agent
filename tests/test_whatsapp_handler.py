import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import asyncio
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# === PRE-IMPORT MOCKING ===
# We must mock these modules BEFORE importing src.agent.whatsapp_handler
# because it (indirectly) imports them at top level.

# 1. Mock Google ADK / GenAI
mock_adk = MagicMock()
mock_genai = MagicMock()
sys.modules["google.adk.agents"] = mock_adk
sys.modules["google.adk.runners"] = mock_adk
sys.modules["google.genai.types"] = mock_genai

# 2. Mock Internal Modules that cause side effects
# Helper to create a dummy module
def create_mock_module(name):
    m = MagicMock()
    sys.modules[name] = m
    return m

mock_supabase_lib = create_mock_module("src.lib.supabase")
mock_workflow = create_mock_module("src.agent.workflow")
mock_agent = create_mock_module("src.agent.agent")
# Mock httpx and client
create_mock_module("httpx")
create_mock_module("src.lib.whatsapp_client")
create_mock_module("src.lib.whatsapp_auth")

# Now we can safely import the handler module
# Use patch.dict for extra safety during import block if needed, 
# but sys.modules set above should persist.

try:
    from src.agent.whatsapp_handler import handle_whatsapp_message
except ImportError as e:
    print(f"Import Error during test setup: {e}")
    sys.exit(1)
except Exception as e:
    print(f"General Error during test setup: {e}")
    sys.exit(1)


class TestWhatsAppHandler(unittest.TestCase):
    
    def setUp(self):
        # Create a new event loop for async tests if needed
        # Or just use asyncio.run in test methods
        pass

    def test_handle_whatsapp_message_success(self):
        async def run_test():
            # Setup Mocks
            mock_auth_cls = MagicMock()
            mock_auth_cls.get_user_id_by_phone.return_value = "user_123"
            
            mock_client_instance = AsyncMock()
            
            # Helper to create text event object
            def create_text_event(text):
                m = MagicMock()
                m.text = text
                # Hide dict attributes to ensure logic uses .text
                m.__class__ = type("Event", (), {"text": text})
                return m

            # Setup workflow generator
            async def event_generator(user_id, session_id, message):
                yield create_text_event("Hello ")
                yield create_text_event("World")
            
            # Patch dependencies
            with patch("src.agent.whatsapp_handler.WhatsAppAuth", mock_auth_cls), \
                 patch("src.agent.whatsapp_handler.whatsapp_client", mock_client_instance), \
                 patch("src.agent.whatsapp_handler.run_workflow", side_effect=event_generator) as mock_run:
                 
                 await handle_whatsapp_message("123456789", "Hi", "msg_id_1")
                 
                 # Verifications
                 mock_auth_cls.get_user_id_by_phone.assert_called_once_with("123456789")
                 mock_client_instance.mark_as_read.assert_called_once_with("msg_id_1")
                 
                 # arguments check
                 mock_run.assert_called_once()
                 call_args = mock_run.call_args
                 self.assertEqual(call_args[0][0], "user_123")
                 
                 # Check message sending (Buffered)
                 mock_client_instance.send_message.assert_called_once_with("123456789", "Hello World")

        asyncio.run(run_test())

    def test_handle_whatsapp_message_unknown_user(self):
        async def run_test():
            mock_auth_cls = MagicMock()
            mock_auth_cls.get_user_id_by_phone.return_value = None
            
            mock_client_instance = AsyncMock()
            
            with patch("src.agent.whatsapp_handler.WhatsAppAuth", mock_auth_cls), \
                 patch("src.agent.whatsapp_handler.whatsapp_client", mock_client_instance):
                 
                 await handle_whatsapp_message("999", "Hi", "msg_id_2")
                 
                 mock_client_instance.send_message.assert_called_with("999", "Desculpe, seu número não está cadastrado no Cloudinha. Entre em contato com o suporte ou cadastre-se no site.")

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
