from typing import Optional, Dict, Any, List, Union
import json
from src.lib.supabase import supabase
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.updateStudentProfile import standardize_city, standardize_state
from src.lib.error_handler import safe_execution

@safe_execution(error_type="tool_error", default_return=None)
def get_city_coordinates_from_db(city_name: str, state_code: Optional[str] = None):
    """
    Get latitude and longitude for a city name using the Supabase 'cities' table.
    """
    if not city_name:
        return None

    query = supabase.table("cities").select("latitude, longitude").ilike("name", city_name)
    
    if state_code:
        query = query.eq("state", state_code)
        
    result = query.execute()
    
    if result.data and len(result.data) > 0:
        # Return the first match
        record = result.data[0]
        return float(record['latitude']), float(record['longitude'])
            
    return None

@safe_execution(error_type="tool_error", default_return='{"success": false, "error": "Erro ao atualizar preferências."}')
def updateStudentPreferencesTool(user_id: str, updates: Dict[str, Any]) -> str:
    """
    Atualiza as preferências de busca do aluno (curso, nota, turno, etc.) e dispara a busca de oportunidades.
    
    Args:
        user_id: ID do usuário (pode ser "user" para debug locais).
        updates: Dicionário contendo os campos a atualizar. 
                 Chaves comuns: 'course_interest', 'enem_score', 'preferred_shifts', 'city_name', 
                 'university_preference', 'program_preference', 'quota_types', 'per_capita_income',
                 'state_preference'.
    """
    
    print(f"!!! [DEBUG TOOL] updateStudentPreferencesTool CALLED with user_id={user_id}, updates={updates}")
    
    results = {
        "preferences_updated": False,
        "workflow_switched": False,
        "search_performed": False,
        "errors": []
    }

    preferences_updates = {}
    
    # --- 1. Score Normalization ---
    if "enem_score" in updates:
        preferences_updates["enem_score"] = float(updates["enem_score"])
        print(f"!!! [SCORE UPDATE] enem_score set to: {preferences_updates['enem_score']}")
    
    if "per_capita_income" in updates:
        preferences_updates["family_income_per_capita"] = float(updates["per_capita_income"])
        print(f"!!! [INCOME UPDATE] family_income_per_capita set to: {preferences_updates['family_income_per_capita']}")

    # Registration Step (Wizard Progress)
    if "registration_step" in updates:
        preferences_updates["registration_step"] = str(updates["registration_step"])

    # Program Preference (sisu/prouni/indiferente)
    prog_pref = updates.get("program_preference")
    if not prog_pref or prog_pref == 'indiferente':
        prog_pref = "prouni"
    preferences_updates["program_preference"] = prog_pref

    univ_pref = updates.get("university_preference")
    if not univ_pref or univ_pref == 'indiferente':
        univ_pref = "privada"
    preferences_updates["university_preference"] = univ_pref

    # Quota Types
    if "quota_types" in updates:
        preferences_updates["quota_types"] = updates["quota_types"]
        print(f"!!! [QUOTA UPDATE] quota_types set to: {updates['quota_types']}")
    
    # --- 2. Course Normalization (Parse multiple courses from string) ---
    
    # Cache for course names from DB (avoid repeated calls)
    _course_names_cache = None
    
    def get_course_names_from_db() -> List[str]:
        """Fetch unique course names from database."""
        nonlocal _course_names_cache
        if _course_names_cache is not None:
            return _course_names_cache
        try:
            result = supabase.rpc("get_unique_course_names").execute()
            if result.data:
                _course_names_cache = [r["course_name"] for r in result.data if r.get("course_name")]
                print(f"!!! [COURSE CACHE] Loaded {len(_course_names_cache)} course names from DB")
                return _course_names_cache
        except Exception as e:
            print(f"!!! [COURSE CACHE ERROR] {e}")
        return []
    
    def match_course_to_database(user_input: str, course_list: List[str]) -> Optional[str]:
        """Find the best matching course name."""
        if not user_input or not course_list:
            return None
        
        user_lower = user_input.lower().strip()
        for course in course_list:
            if course.lower() == user_lower:
                return course
        for course in course_list:
            if course.lower().startswith(user_lower):
                return course
        if len(user_lower) >= 4:
            for course in course_list:
                if user_lower in course.lower():
                    return course
        return None
    
    def parse_course_list(raw_value: str) -> List[str]:
        """Parse a string into a list of courses."""
        import re
        clean = raw_value.strip()
        lower = clean.lower()
        if "não sei" in lower or "indeciso" in lower or "ainda não" in lower:
            return []
        parts = re.split(r'\s*[,;/]\s*|\s+e\s+|\s+ou\s+', clean, flags=re.IGNORECASE)
        db_courses = get_course_names_from_db()
        courses = []
        for part in parts:
            stripped = part.strip()
            if stripped and len(stripped) > 1:
                matched = match_course_to_database(stripped, db_courses)
                if matched:
                    courses.append(matched)
                else:
                    courses.append(stripped.title())
        return courses

    if "course_interest" in updates:
        val = updates["course_interest"]
        if isinstance(val, str):
            courses = parse_course_list(val)
            preferences_updates["course_interest"] = courses
            print(f"!!! [COURSE PARSED] '{val}' -> {courses}")
        elif isinstance(val, list):
            normalized = []
            for item in val:
                if isinstance(item, str):
                    parsed = parse_course_list(item)
                    normalized.extend(parsed)
                else:
                    normalized.append(item)
            preferences_updates["course_interest"] = normalized
            
    if "course_name" in updates: # Legacy alias
        val = updates["course_name"]
        if isinstance(val, str):
            preferences_updates["course_interest"] = [val]
        elif isinstance(val, list):
            preferences_updates["course_interest"] = val
    
    # --- 3. Workflow Data Merge (Match Specifics) ---
    workflow_keys = ['match_search_confirmed'] 
    workflow_update = {}
    if "workflow_data" in updates:
        workflow_update.update(updates["workflow_data"])
        
    for key in workflow_keys:
        if key in updates:
            workflow_update[key] = updates[key]
            
    if workflow_update:
        try:
             curr = supabase.table("user_preferences").select("workflow_data").eq("user_id", user_id).execute()
             current_data = (curr.data[0].get("workflow_data") if curr.data else {}) or {}
             current_data.update(workflow_update)
             preferences_updates["workflow_data"] = current_data
        except Exception as e:
             print(f"[WARN] Could not fetch workflow_data for merge: {e}. Overwriting.")
             preferences_updates["workflow_data"] = workflow_update
             
    if "state_preference" in updates:
        raw_state = updates["state_preference"]
        normalized_state = standardize_state(raw_state)
        if normalized_state:
            preferences_updates["state_preference"] = normalized_state
            print(f"!!! [STATE STANDARDIZED] '{raw_state}' -> '{normalized_state}'")
        else:
            preferences_updates["state_preference"] = raw_state
            print(f"!!! [STATE NOT FOUND] Keeping original: '{raw_state}'")
    
    # Standardize city/location preference
    if "city_name" in updates:
        raw_city = updates["city_name"]
        standardized = standardize_city(raw_city)
        if standardized:
            preferences_updates["location_preference"] = standardized["name"]
            preferences_updates["state_preference"] = standardized["state"]
            
            # [NEW] Resolve Lat/Long immediately and save to device_latitude/longitude
            coords = get_city_coordinates_from_db(standardized["name"], standardized["state"])
            if coords:
                preferences_updates["device_latitude"] = coords[0]
                preferences_updates["device_longitude"] = coords[1]
                print(f"!!! [GEOCODING] Resolved {standardized['name']} -> {coords}")
            
            print(f"!!! [PREFS CITY STANDARDIZED] '{raw_city}' -> '{standardized['name']}' ({standardized['state']})")
        else:
            preferences_updates["location_preference"] = raw_city
    elif "location_preference" in updates:
        raw_city = updates["location_preference"]
        standardized = standardize_city(raw_city)
        if standardized:
            preferences_updates["location_preference"] = standardized["name"]
            preferences_updates["state_preference"] = standardized["state"]
            
            # [NEW] Resolve Lat/Long immediately and save to device_latitude/longitude
            coords = get_city_coordinates_from_db(standardized["name"], standardized["state"])
            if coords:
                preferences_updates["device_latitude"] = coords[0]
                preferences_updates["device_longitude"] = coords[1]
                print(f"!!! [GEOCODING] Resolved {standardized['name']} -> {coords}")
            
            print(f"!!! [PREFS CITY STANDARDIZED] '{raw_city}' -> '{standardized['name']}' ({standardized['state']})")
        else:
            preferences_updates["location_preference"] = raw_city

    # --- 4. Shift Normalization ---
    def normalize_shift_value(val: str) -> str:
        lower = val.lower().strip()
        if 'EAD' in lower or 'Curso a distância' in lower:
            return 'EAD'
        shift_map = {
            'matutino': 'Matutino',
            'vespertino': 'Vespertino',
            'noturno': 'Noturno',
            'integral': 'Integral'
        }
        return shift_map.get(lower, val)

    if "shift" in updates or "preferred_shifts" in updates:
        val = updates.get("shift") or updates.get("preferred_shifts")
        is_indifferent = False
        if isinstance(val, str):
            clean = val.lower()
            if "indiferente" in clean or "qualquer" in clean or "tanto faz" in clean:
                is_indifferent = True
        elif isinstance(val, list) and len(val) == 1:
            clean = str(val[0]).lower()
            if "indiferente" in clean or "qualquer" in clean:
                is_indifferent = True
        
        if is_indifferent:
            preferences_updates["preferred_shifts"] = []
        else:
            if isinstance(val, list):
                preferences_updates["preferred_shifts"] = [normalize_shift_value(s) for s in val if s]
            else:
                preferences_updates["preferred_shifts"] = [normalize_shift_value(str(val))]

    # --- 5. Institution Type Normalization ---
    # Forced to ProUni/Private defaults for the current season
    prog_pref = preferences_updates.get("program_preference") or pf.get("program_preference")
    if not prog_pref or prog_pref == 'indiferente':
        preferences_updates["program_preference"] = "prouni"
        
    univ_pref = preferences_updates.get("university_preference") or pf.get("university_preference")
    if not univ_pref or univ_pref == 'indiferente':
        preferences_updates["university_preference"] = "privada"

    print(f"!!! [PROUNI ENFORCED] Program: {preferences_updates.get('program_preference')}, Univ: {preferences_updates.get('university_preference')}")
    
    # --- EXECUTE DB UPDATE ---
    if preferences_updates:
        # DB Updates handled by safe_execution
        existing_prefs_response = supabase.table("user_preferences").select("id").eq("user_id", user_id).maybe_single().execute()
        existing_prefs = existing_prefs_response.data if existing_prefs_response else None

        if existing_prefs:
            supabase.table("user_preferences").update(preferences_updates).eq("id", existing_prefs["id"]).execute()
        else:
            data = preferences_updates.copy()
            data["user_id"] = user_id
            supabase.table("user_preferences").insert(data).execute()
        
        results["preferences_updated"] = True
        
        # Invalidate cache (since getStudentProfile also returns preferences)
        try:
            from src.tools.getStudentProfile import invalidate_profile_cache
            invalidate_profile_cache(user_id)
        except ImportError:
            pass

    # --- AUTO-TRIGGER SEARCH & WORKFLOW SWITCH LOGIC ---
    # Safe execution covers this block
    # Fetch fresh complete state to decide on search
    final_prefs = supabase.table("user_preferences").select("*").eq("user_id", user_id).maybe_single().execute()
    pf = final_prefs.data if final_prefs else {}
    
    c_interest = pf.get("course_interest")
    score = pf.get("enem_score")
    shifts = pf.get("preferred_shifts")
    uni_type = pf.get("university_preference")
    state_pref = pf.get("state_preference")

    # Check for ANY preference that could filter search results
    has_any_filter = (
        bool(c_interest) or 
        (score is not None) or 
        bool(shifts) or 
        bool(uni_type) or 
        bool(state_pref) or 
        bool(pf.get("location_preference")) or
        bool(pf.get("program_preference")) or
        bool(pf.get("quota_types")) or
        (pf.get("family_income_per_capita") is not None)
    )
    
    should_search = has_any_filter
    
    if should_search:
        # Check Workflow State
        try:
            profile_ctx = supabase.table("user_profiles").select("active_workflow").eq("id", user_id).maybe_single().execute()
            active_wf = profile_ctx.data.get("active_workflow") if (profile_ctx and profile_ctx.data) else None
        except:
            active_wf = None
        
        # WORKFLOW SWITCH: If not in match_workflow, force switch
        if active_wf != "match_workflow":
            print(f"!!! [AUTO SWITCH] Switching from {active_wf} to match_workflow to display results.")
            supabase.table("user_profiles").update({"active_workflow": "match_workflow"}).eq("id", user_id).execute()
            results["workflow_switched"] = True

        # EXECUTE SEARCH
        # Note: searchOpportunitiesTool will load course_interest from profile
        print(f"!!! [AUTO SEARCH] Triggering search with: course={c_interest}, score={score}, shifts={shifts}, uni={uni_type}, state={state_pref}")
            
        opportunities_json = searchOpportunitiesTool(
            user_id=user_id,
            course_name=None, 
            enem_score=float(score) if score is not None else 0.0,
            shift=shifts,
            institution_type=uni_type,
            university_preference=uni_type, 
            program_preference=pf.get("program_preference"),
            per_capita_income=pf.get("family_income_per_capita"),
            quota_types=pf.get("quota_types"),
            user_lat=pf.get("device_latitude"),
            user_long=pf.get("device_longitude"),
            city_name=pf.get("location_preference"),
            state_name=pf.get("state_preference")
        )
        
        try:
            results["auto_search_results"] = json.loads(opportunities_json)
        except:
            results["auto_search_results"] = opportunities_json
            
        results["search_performed"] = True

    return json.dumps({"success": True, **results}, ensure_ascii=False)
