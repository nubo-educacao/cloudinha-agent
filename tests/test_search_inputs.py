
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock supabase to avoid real calls and just check params
mock_supabase = MagicMock()
mock_rpc = MagicMock()
mock_supabase.rpc = mock_rpc
mock_execute = MagicMock()
mock_rpc.return_value = mock_execute
mock_execute.execute.return_value.data = [] # Empty return

# We need to mock getStudentProfileTool too
mock_get_profile = MagicMock()

with patch.dict('sys.modules', {
    'src.lib.supabase': MagicMock(supabase=mock_supabase),
    'src.tools.getStudentProfile': MagicMock(getStudentProfileTool=mock_get_profile)
}):
    from src.tools.searchOpportunities import searchOpportunitiesTool

    def test_search_with_profile_interests():
        print("--- Test 1: Search with Profile Interests ---")
        # Setup Profile
        mock_get_profile.return_value = {
            "course_interest": ["Direito", "Medicina"],
            "device_latitude": -23.55,
            "device_longitude": -46.63,
            "per_capita_income": 1000.0,
            "quota_types": ["AMPLA"]
        }
        
        # Run Tool
        searchOpportunitiesTool(user_id="test_user")
        
        # Verify RPC call
        args, kwargs = mock_supabase.rpc.call_args
        rpc_name = args[0]
        params = args[1]
        
        print(f"RPC Name: {rpc_name}")
        print(f"Params: {json.dumps(params, indent=2, ensure_ascii=False)}")
        
        interests = params.get("course_interests", [])
        assert "Direito" in interests
        assert "Medicina" in interests
        assert params.get("search_text") is None # Should be gone or not passed
        print("✅ Test 1 Passed")

    def test_search_with_explicit_course_and_profile():
        print("\n--- Test 2: Explicit Course + Profile ---")
        mock_get_profile.return_value = {
            "course_interest": ["Engenharia"],
        }
        
        searchOpportunitiesTool(user_id="test_user", course_name="Psicologia")
        
        args, kwargs = mock_supabase.rpc.call_args
        params = args[1]
        
        print(f"Params: {json.dumps(params, indent=2, ensure_ascii=False)}")
        interests = params.get("course_interests", [])
        assert "Engenharia" in interests
        assert "Psicologia" in interests
        print("✅ Test 2 Passed")

    if __name__ == "__main__":
        try:
            test_search_with_profile_interests()
            test_search_with_explicit_course_and_profile()
        except Exception as e:
            print(f"❌ Test Failed: {e}")
            import traceback
            traceback.print_exc()
