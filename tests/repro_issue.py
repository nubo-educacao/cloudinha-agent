import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.tools.updateStudentProfile import standardize_city

def test_city_matching(input_city, expected_name=None):
    print(f"\nTesting input: '{input_city}'")
    result = standardize_city(input_city)
    
    if result:
        print(f"Result: {result['name']} ({result['state']})")
        if expected_name:
            if result['name'] == expected_name:
                 print("✅ SUCCESS")
            else:
                 print(f"❌ FAIL: Expected '{expected_name}', got '{result['name']}'")
    else:
        print("Result: None")
        if expected_name:
            print(f"❌ FAIL: Expected '{expected_name}', got None")

if __name__ == "__main__":
    print("--- REPRODUCING ISSUE ---")
    # Current buggy behavior: 'sp' matches 'Aspásia' (fuzzy match)
    test_city_matching("sp", expected_name="São Paulo") 
    
    # Desired behavior for abbreviations
    test_city_matching("bh", expected_name="Belo Horizonte")
    
    # Regular city
    test_city_matching("Campinas", expected_name="Campinas")
