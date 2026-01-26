
import pytest
from unittest.mock import patch
import sys
import os
import json

# Setup Path and Env
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-key"
os.environ["OPENAI_API_KEY"] = "mock-key"

from src.tools.updateStudentPreferences import updateStudentPreferencesTool

@patch("src.tools.updateStudentPreferences.supabase")
@patch("src.tools.updateStudentPreferences.searchOpportunitiesTool")
@patch("src.tools.updateStudentPreferences.get_city_coordinates_from_db")
def test_update_student_preferences_basic(mock_geo, mock_search, mock_supabase):
    """
    Revised test based on debug_tools.py which was verified to work.
    """
    # Mock setups
    # Basic select for existing prefs
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"id": "test-id"}
    # Update returns empty dict (or whatever execute returns)
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = {}
    
    # Mock search return
    mock_search.return_value = '{"opportunities": []}'
    
    # Mock final prefs fetch for search trigger
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
         "course_interest": ["Medicina"],
         "enem_score": 700.0,
         "preferred_shifts": ["Matutino"]
    }

    user_id = "test_user_123"
    updates = {"shift": "matutino"}
    
    result_json = updateStudentPreferencesTool(user_id, updates)
    result = json.loads(result_json)
    
    assert result["success"] is True
    assert result["preferences_updated"] is True
    
    # Verify update was called
    assert mock_supabase.table.return_value.update.called is True
