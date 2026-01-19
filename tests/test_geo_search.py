
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# --- MOCKS ---
mock_supabase = MagicMock()
mock_rpc = MagicMock()
mock_supabase.rpc = mock_rpc
mock_execute_rpc = MagicMock()
mock_rpc.return_value = mock_execute_rpc
mock_execute_rpc.execute.return_value.data = [] # Empty RPC search result

# Mock for DB Cities Table
mock_table = MagicMock()
mock_select = MagicMock()
mock_ilike = MagicMock()
mock_eq = MagicMock()
mock_execute_db = MagicMock()

mock_supabase.table.return_value = mock_table
mock_table.select.return_value = mock_select
mock_select.ilike.return_value = mock_ilike
mock_ilike.eq.return_value = mock_eq # Handled in code (ilike returns query, then .eq is called on it if state provided)
# Also handle case where .eq is NOT called: ilike matches directly to execute
mock_ilike.execute.return_value = mock_execute_db
mock_eq.execute.return_value = mock_execute_db

# We need to mock getStudentProfileTool too
mock_get_profile = MagicMock()
mock_get_profile.return_value = {} # Default empty profile

# Apply Patches
with patch.dict('sys.modules', {
    'src.lib.supabase': MagicMock(supabase=mock_supabase),
    'src.tools.getStudentProfile': MagicMock(getStudentProfileTool=mock_get_profile)
}):
    from src.tools.searchOpportunities import searchOpportunitiesTool

    def setup_city_mock(latitude=None, longitude=None, found=True):
        if found:
            mock_execute_db.data = [{"latitude": latitude, "longitude": longitude}]
        else:
            mock_execute_db.data = []

    def test_proximity_search_city_found():
        print("\n--- Test 1: Proximity Search (City Found in DB) ---")
        # Scenario: User searches for "Guarulhos"
        # Expectation: DB returns coords. RPC called with coords AND city_names=None (cleared).
        
        setup_city_mock(latitude=-23.4, longitude=-46.5) # Guarulhos approx
        
        searchOpportunitiesTool(user_id="test_user", city_name="Guarulhos")
        
        # Verify DB Lookup
        # We can't easily assert exact chain calls on mocks without deep inspection, 
        # but we can verify that searchOpportunitiesTool logic resulted in correct RPC params.
        
        args, kwargs = mock_supabase.rpc.call_args
        params = args[1]
        
        print(f"RPC Params: {str(params)}")
        
        # ASSERT: Coords must be set
        assert params.get("user_lat") == -23.4
        assert params.get("user_long") == -46.5
        
        # ASSERT: city_names should be NONE (Proximity Mode Active)
        assert params.get("city_names") is None
        print("✅ Test 1 Passed (Proximity Active)")

    def test_fallback_search_city_not_found():
        print("\n--- Test 2: Text Search (City NOT Found in DB) ---")
        # Scenario: User searches for "CidadeFantasma"
        # Expectation: DB returns empty. RPC called with city_names=['CidadeFantasma'].
        
        setup_city_mock(found=False)
        
        searchOpportunitiesTool(user_id="test_user", city_name="CidadeFantasma")
        
        args, kwargs = mock_supabase.rpc.call_args
        params = args[1]
        
        print(f"RPC Params: {str(params)}")
        
        # ASSERT: Coords not set (or defaulted to profile/null)
        # assuming profile is empty
        assert params.get("user_lat") is None
        
        # ASSERT: city_names should be PRESSED
        city_names = params.get("city_names", [])
        assert "CidadeFantasma" in city_names
        print("✅ Test 2 Passed (Fallback Text Search)")

    def test_state_search_only():
        print("\n--- Test 3: State Search Only ---")
        # Scenario: User searches for state "SP", no city.
        # Expectation: DB Lookup for city not triggered (or handled safely). RPC called with state_names=['SP'].
        
        # Reset DB mock to ensure it doesn't return anything confusing
        setup_city_mock(found=False) 
        
        searchOpportunitiesTool(user_id="test_user", state_name="SP")
        
        args, kwargs = mock_supabase.rpc.call_args
        params = args[1]
        
        print(f"RPC Params: {str(params)}")
        
        # ASSERT: state_names set
        state_names = params.get("state_names", [])
        # Note: standardize_state might normalize input, check what implementation does
        # Assuming our mock getStudentProfile doesn't have state_preference.
        # But wait, searchOpportunities implementation normalizes states!
        # It calls standardize_state. That function is imported.
        # Since we imported searchOpportunities, it imported the REAL standardize_state or tried to.
        # If it's a simple util, it might work. If it uses DB, it might fail/need mock.
        # Let's verify imports in searchOpportunities.py
        
        # It imports 'from src.tools.updateStudentProfile import standardize_state'.
        # That imports supabase inside it? Or is it pure?
        # Usually it's pure logic or DB. 
        # If it fails, we will see.
        
        # For now, let's assume it passes "SP" through as fallback.
        
        assert "SP" in state_names or "SAO PAULO" in state_names
        
        # ASSERT: city_names None
        assert params.get("city_names") is None
        print("✅ Test 3 Passed (State Search)")

    if __name__ == "__main__":
        try:
            test_proximity_search_city_found()
            test_fallback_search_city_not_found()
            test_state_search_only()
        except Exception as e:
            print(f"❌ Test Failed: {e}")
            import traceback
            traceback.print_exc()
