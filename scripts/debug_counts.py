import os
import asyncio
from supabase import create_client, Client

# Manually set credentials from .env.local
url: str = "https://aifzkybxhmefbirujvdg.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFpZnpreWJ4aG1lZmJpcnVqdmRnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg1OTI5MjUsImV4cCI6MjA4NDE2ODkyNX0.YCnij78ps2si_zl_yT-XGcd9RpOjOht-u04ppSAbpM0"

async def main():
    supabase: Client = create_client(url, key)

    print("--- Opportunity Counts ---")
    try:
        # Count Sisu 2026
        res = supabase.table('opportunities').select('id', count='exact').eq('opportunity_type', 'sisu').eq('year', 2026).execute()
        print(f"Sisu 2026: {res.count}")
    except Exception as e:
        print(f"Error counting Sisu 2026: {e}")

    try:
        # Count Prouni 2025
        res = supabase.table('opportunities').select('id', count='exact').eq('opportunity_type', 'prouni').eq('year', 2025).execute()
        print(f"Prouni 2025: {res.count}")
    except Exception as e:
        print(f"Error counting Prouni 2025: {e}")

    print("\n--- Checking Indexes (via RPC if possible, else infer from behavior) ---")
    # We can't query pg_indexes directly via PostgREST unless exposed.
    # Instead, we'll try a search query and time it.
    
    import time
    
    start = time.time()
    print("Testing Sisu Search (limit 1)...")
    try:
        res = supabase.rpc('match_opportunities', {
            'program_preference': 'sisu',
            'city_names': ['São Paulo'],
            'page_size': 1
        }).execute()
        print(f"Sisu Search Time: {time.time() - start:.2f}s")
        # print(f"Result count: {len(res.data)}") 
    except Exception as e:
        print(f"Sisu Search Failed/Timed Out: {e}")

    start = time.time()
    print("\nTesting Prouni Search (limit 1)...")
    try:
        res = supabase.rpc('match_opportunities', {
            'program_preference': 'prouni',
            'city_names': ['São Paulo'],
            'page_size': 1
        }).execute()
        print(f"Prouni Search Time: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Prouni Search Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
