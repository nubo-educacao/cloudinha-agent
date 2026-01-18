import os
import asyncio
from supabase import create_client, Client

# Manually set credentials from .env.local
url: str = "https://aifzkybxhmefbirujvdg.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFpZnpreWJ4aG1lZmJpcnVqdmRnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg1OTI5MjUsImV4cCI6MjA4NDE2ODkyNX0.YCnij78ps2si_zl_yT-XGcd9RpOjOht-u04ppSAbpM0"

async def main():
    supabase: Client = create_client(url, key)

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
