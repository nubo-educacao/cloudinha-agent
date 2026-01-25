import os
import sys
import asyncio

# Add root directory to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lib.supabase import supabase

async def main():
    print("--- Sampling Campus States ---")
    try:
        # Get distinct states
        res = supabase.table('campus').select('state').limit(20).execute()
        states = set(item['state'] for item in res.data if item['state'])
        print(f"Sample States: {states}")
    except Exception as e:
        print(f"Error fetching states: {e}")

if __name__ == "__main__":
    asyncio.run(main())
