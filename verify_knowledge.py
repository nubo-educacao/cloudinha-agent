import sys
import os

# Adjust path to import src
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.tools.readRulesTool import readRulesTool

def test_program(program):
    print(f"\n--- Testing '{program}' ---")
    content = readRulesTool(program=program)
    if "Erro" in content or "Aviso" in content:
        print(f"FAILED: {content}")
        return False
    else:
        print(f"SUCCESS: Retrieved {len(content)} bytes.")
        print(f"Preview: {content[:100]}...")
        return True

if __name__ == "__main__":
    prouni = test_program("prouni")
    sisu = test_program("sisu")
    cloudinha = test_program("cloudinha")
    
    if prouni and sisu and cloudinha:
        print("\nALL TESTS PASSED")
    else:
        print("\nSOME TESTS FAILED")
