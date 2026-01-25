import pytest
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Set dummy env vars
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-key"
os.environ["GOOGLE_API_KEY"] = "mock-key"

from src.agent.router_agent import parse_router_json

def test_router_parse_clean_json():
    text = '{"intent": "CHANGE_WORKFLOW", "target_workflow": "match_workflow"}'
    result = parse_router_json(text)
    assert result["intent"] == "CHANGE_WORKFLOW"
    assert result["target_workflow"] == "match_workflow"

def test_router_parse_markdown_json():
    text = """
    Here is the decision:
    ```json
    {
        "intent": "CONTINUE_WORKFLOW",
        "target_workflow": null,
        "confidence": "high"
    }
    ```
    """
    result = parse_router_json(text)
    assert result["intent"] == "CONTINUE_WORKFLOW"
    assert result["confidence"] == "high"

def test_router_parse_nested_braces():
    # Regex {.*} might be greedy or not handle nested well if naive, 
    # but re.DOTALL with greedy * usually grabs start to last }.
    # Let's test standard behaviour.
    text = 'prefix {"data": {"nested": 1}} suffix'
    result = parse_router_json(text)
    assert result["data"]["nested"] == 1

def test_router_parse_failure():
    text = "No json here"
    result = parse_router_json(text)
    assert result == {}
