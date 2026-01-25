import os
import sys
import asyncio
import time

# Add root directory to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lib.supabase import supabase

async def main():
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
    
    start = time.time()
    print("Testing Sisu Search (limit 1)...")
    try:
        res = supabase.rpc('match_opportunities', {
            'program_preference': 'sisu',
            'city_names': ['São Paulo'],
            'page_size': 1
        }).execute()
        print(f"Sisu Search Time: {time.time() - start:.2f}s")
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
