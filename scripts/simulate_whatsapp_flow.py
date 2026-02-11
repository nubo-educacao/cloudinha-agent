import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, patch

# Configure Environment (Mock)
os.environ["WHATSAPP_API_TOKEN"] = "mock_token"
os.environ["WHATSAPP_PHONE_ID"] = "mock_phone_id"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "mock_verify"

# 1. Mock External Dependencies BEFORE imports
sys.modules["google.adk.agents"] = MagicMock()
sys.modules["google.adk.runners"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()

# Mock Supabase
mock_supabase_mod = MagicMock()
mock_supabase_client = MagicMock()
mock_supabase_mod.supabase = mock_supabase_client
sys.modules["src.lib.supabase"] = mock_supabase_mod

# Setup path
sys.path.append(os.path.join(os.getcwd(), 'src'))
sys.path.append(os.getcwd())

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulation")

async def simulate():
    print("--- Starting WhatsApp Simulation ---")
    
    # Patch Client
    with patch('src.agent.whatsapp_handler.whatsapp_client') as mock_client:
        mock_client.send_message = MagicMock(side_effect=lambda to, body: print(f"[WHATSAPP_SEND] To: {to}\nBody: {body}"))
        mock_client.mark_as_read = MagicMock(return_value=True)

        # Import Handler (Safe now due to mocks)
        from src.agent.whatsapp_handler import handle_whatsapp_message
        
        # Test Case 1: Unknown User
        print("\n>>> TEST 1: Unknown User")
        with patch('src.lib.whatsapp_auth.WhatsAppAuth.get_user_id_by_phone', return_value=None):
            await handle_whatsapp_message("55999999999", "Olá", "msg_1")

        # Test Case 2: Known User
        print("\n>>> TEST 2: Known User (Mocked Auth)")
        with patch('src.lib.whatsapp_auth.WhatsAppAuth.get_user_id_by_phone', return_value="user_123_uuid"):
             
             # Mock run_workflow generator
             async def mock_gen(user_id, session_id, message):
                 # Yield some fake events
                 yield {"type": "tool_start", "tool": "searchOpportunities", "args": {}}
                 
                 # Mock text events usually have .text attribute or content.parts
                 # Simple Mock Object for text event
                 t1 = MagicMock(); t1.text = "Olá! "
                 yield t1
                 
                 t2 = MagicMock(); t2.text = "Encontrei vagas."
                 yield t2
                 
                 yield {"type": "tool_end", "tool": "searchOpportunities", "output": "results"}

             with patch('src.agent.whatsapp_handler.run_workflow', side_effect=mock_gen):
                 await handle_whatsapp_message("5511987654321", "Quero vagas", "msg_2")

if __name__ == "__main__":
    asyncio.run(simulate())
