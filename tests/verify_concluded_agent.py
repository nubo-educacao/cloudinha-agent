import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock environment variables for ADK/Supabase if needed by imports
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-key"
os.environ["OPENAI_API_KEY"] = "mock-key"

try:
    from src.agent.passport_workflow import concluded_agent
    
    print(f"Agent Name: {concluded_agent.name}")
    print(f"Agent Description: {concluded_agent.description}")
    
    tool_names = [tool.__name__ for tool in concluded_agent.tools]
    print(f"Tools: {', '.join(tool_names)}")
    
    expected_tools = [
        'getStudentProfileTool',
        'evaluatePassportEligibilityTool',
        'startStudentApplicationTool',
        'smartResearchTool',
        'getImportantDatesTool'
    ]
    
    all_present = all(t in tool_names for t in expected_tools)
    print(f"All expected tools present: {all_present}")
    
    if "evaluatePassportEligibilityTool" in concluded_agent.instruction:
        print("Instruction contains evaluatePassportEligibilityTool: True")
    else:
        print("Instruction contains evaluatePassportEligibilityTool: False")
        
    if "startStudentApplicationTool" in concluded_agent.instruction:
        print("Instruction contains startStudentApplicationTool: True")
    else:
        print("Instruction contains startStudentApplicationTool: False")

except Exception as e:
    print(f"Error during verification: {e}")
    import traceback
    traceback.print_exc()
