
import json
import uuid
from src.tools.searchOpportunities import searchOpportunitiesTool, normalize_shift, get_excluded_tags_by_income

def test_normalization():
    print("\n--- Testing Normalization ---")
    assert normalize_shift("Curso a distância") == "EAD"
    assert normalize_shift("EAD") == "EAD"
    assert normalize_shift("noturno") == "Noturno"
    print("[OK] Shift normalization passed")

    excluded = get_excluded_tags_by_income(5000.0)
    assert 'INTEGRAL' in excluded
    assert 'PARCIAL' in excluded
    print(f"[OK] Income exclusion passed (5000.0 -> {excluded})")

def test_search_tool():
    print("\n--- Testing Search Tool ---")
    
    # 1. Broad Search
    print("1. Broad Search (Direito):")
    result_json = searchOpportunitiesTool(
        course_name="Direito",
        enem_score=700.0,
        city_name="São Paulo"
    )
    result = json.loads(result_json)
    print(f"Summary: {result.get('summary')}")
    if result.get('results'):
        print(f"First Result: {result['results'][0]['institution']} - {result['results'][0]['course']}")
    else:
        print("No results found (Check DB content)")

    # 2. Shift Search (EAD)
    print("\n2. Shift Search (Curso a distância):")
    result_json_ead = searchOpportunitiesTool(
        course_name="Pedagogia",
        enem_score=600.0,
        shift="Curso a distância" # Should translate to EAD
    )
    result_ead = json.loads(result_json_ead)
    print(f"Summary: {result_ead.get('summary')}")
    # Verify shifts in results
    for r in result_ead.get('results', []):
        if 'EAD' not in r['shifts']:
            print(f"WARN: Result {r['course']} does not have EAD shift: {r['shifts']}")

    # 3. Income Filtering
    print("\n3. Income Filtering (High Income):")
    # High income should exclude pure quota/low income scholarships if logic works
    # However, RPC mainly filters by Scholarship Type (Integral vs Parcial).
    # searchOpportunitiesTool logic: income_per_capita=float
    result_json_income = searchOpportunitiesTool(
        course_name="Medicina",
        enem_score=750.0,
        per_capita_income=5000.0 # Should exclude Integral
    )
    result_income = json.loads(result_json_income)
    print(f"Summary: {result_income.get('summary')}")
    for r in result_income.get('results', []):
        # Check if types contains 'Integral' (It shouldn't if RPC works correctly for types)
        # Note: 'types' in result comes from 'scholarship_type' or 'opportunity_type'
        for t in r['types']:
            if 'Integral' in t or '100%' in t:
                 print(f"FAIL: Found Integral scholarship for high income: {t} in {r['institution']}")

if __name__ == "__main__":
    try:
        test_normalization()
        test_search_tool()
    except Exception as e:
        print(f"\n!!! TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
