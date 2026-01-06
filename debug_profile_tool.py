import os
from dotenv import load_dotenv
load_dotenv()

# Mock supabase client if needed, or rely on src.lib.supabase
# Assuming src.lib.supabase initializes itself from env vars

try:
    from src.tools.getStudentProfile import getStudentProfileTool
except ImportError:
    # Adjust path if running from root
    import sys
    sys.path.append(os.getcwd())
    from src.tools.getStudentProfile import getStudentProfileTool

def test_tool():
    fake_user_id = "a434de58-7a6e-4657-8c50-b527129788a7"
    print(f"Testing getStudentProfileTool with user_id: {fake_user_id}")
    try:
        result = getStudentProfileTool(fake_user_id)
        print("\n--- Result ---")
        print(result)
        print("--------------\n")
        
        if result.get("onboarding_completed") is False:
            print("SUCCESS: onboarding_completed is False")
        else:
            print(f"FAILURE: onboarding_completed is {result.get('onboarding_completed')}")

    except Exception as e:
        print(f"CRASH: Tool execution failed with error: {e}")

if __name__ == "__main__":
    test_tool()
