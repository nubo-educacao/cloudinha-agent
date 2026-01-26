import json
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.lib.supabase import supabase

def test_prouni_search():
    # Test User ID (using a dummy or trying to fetch an existing one for read-only test)
    user_id = "00000000-0000-0000-0000-000000000000" 
    
    print("--- Testing ProUni Search Logic ---")
    
    # Simulate a search that should trigger the new RPC logic
    # Note: Since I couldn't run the migration, this might still hit the old RPC
    # but I want to see if the Python tool correctly prepares the call.
    
    try:
        results = searchOpportunitiesTool(
            user_id=user_id,
            program_preference="prouni",
            university_preference="privada",
            per_capita_income=2000.0, # Should allow Integral in 2025 (1.5 MW = 2277)
            enem_score=650.0
        )
        print("Search Result Summary:")
        print(json.loads(results).get("summary"))
    except Exception as e:
        print(f"Error during search: {e}")

if __name__ == "__main__":
    test_prouni_search()
