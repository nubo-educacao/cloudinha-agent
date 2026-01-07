
import sys
import os

# Ensure current directory is in path
sys.path.append(os.getcwd())

try:
    from src.agent.memory.supabase_session import SupabaseSessionService
    print("Successfully imported SupabaseSessionService")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
