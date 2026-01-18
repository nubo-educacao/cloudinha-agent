from typing import Optional, Dict, Any, List, Union
import json
from src.lib.supabase import supabase
from src.tools.searchOpportunities import searchOpportunitiesTool
from src.tools.updateStudentProfile import standardize_city, standardize_state

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
        raw_score = updates["enem_score"]
        if isinstance(raw_score, str):
            clean = raw_score.lower().strip()
            if "não" in clean or "nao" in clean or "sem" in clean:
                preferences_updates["enem_score"] = 0.0
            else:
                try:
                    preferences_updates["enem_score"] = float(raw_score)
                except:
                    print(f"[WARN] Could not parse enem_score '{raw_score}', defaulting to 0")
                    preferences_updates["enem_score"] = 0.0
        else:
             preferences_updates["enem_score"] = float(raw_score) if raw_score is not None else 0.0

    if "per_capita_income" in updates:
        preferences_updates["family_income_per_capita"] = updates["per_capita_income"]

    # Program Preference (sisu/prouni/indiferente)
    if "program_preference" in updates:
        val = str(updates["program_preference"]).lower()
        if "sisu" in val:
            preferences_updates["program_preference"] = "sisu"
        elif "prouni" in val:
            preferences_updates["program_preference"] = "prouni"
        else:
            preferences_updates["program_preference"] = "indiferente"

    # Quota Types
    if "quota_types" in updates:
        val = updates["quota_types"]
        if isinstance(val, list):
            preferences_updates["quota_types"] = val
        elif isinstance(val, str):
            preferences_updates["quota_types"] = [v.strip() for v in val.split(",")]
    
    # --- 2. Course Normalization ---
    if "course_interest" in updates:
        val = updates["course_interest"]
        if isinstance(val, str):
            clean = val.lower().strip()
            if "não sei" in clean or "indeciso" in clean:
                preferences_updates["course_interest"] = []
            else:
                preferences_updates["course_interest"] = [val]
        elif isinstance(val, list):
            preferences_updates["course_interest"] = val
            
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
            # Keep original but log warning
            preferences_updates["state_preference"] = raw_state
            print(f"!!! [STATE NOT FOUND] Keeping original: '{raw_state}'")
    
    # Standardize city/location preference
    if "city_name" in updates:
        raw_city = updates["city_name"]
        standardized = standardize_city(raw_city)
        if standardized:
            preferences_updates["location_preference"] = standardized["name"]
            preferences_updates["state_preference"] = standardized["state"]
            print(f"!!! [PREFS CITY STANDARDIZED] '{raw_city}' -> '{standardized['name']}' ({standardized['state']})")
        else:
            preferences_updates["location_preference"] = raw_city
    elif "location_preference" in updates:
        raw_city = updates["location_preference"]
        standardized = standardize_city(raw_city)
        if standardized:
            preferences_updates["location_preference"] = standardized["name"]
            preferences_updates["state_preference"] = standardized["state"]
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
    if "institution_type" in updates:
        itype = str(updates["institution_type"]).lower()
        if "púb" in itype or "pub" in itype:
            preferences_updates["university_preference"] = "publica"
        elif "priv" in itype:
             preferences_updates["university_preference"] = "privada"
        else:
             preferences_updates["university_preference"] = "indiferente"
    
    if "university_preference" in updates and "university_preference" not in preferences_updates:
        val = str(updates["university_preference"]).lower()
        if "púb" in val or "pub" in val:
            preferences_updates["university_preference"] = "publica"
        elif "priv" in val:
            preferences_updates["university_preference"] = "privada"
        else:
            preferences_updates["university_preference"] = "indiferente"
    
    # --- EXECUTE DB UPDATE ---
    if preferences_updates:
        try:
            existing_prefs_response = supabase.table("user_preferences").select("id").eq("user_id", user_id).maybe_single().execute()
            existing_prefs = existing_prefs_response.data if existing_prefs_response else None

            if existing_prefs:
                supabase.table("user_preferences").update(preferences_updates).eq("id", existing_prefs["id"]).execute()
            else:
                data = preferences_updates.copy()
                data["user_id"] = user_id
                supabase.table("user_preferences").insert(data).execute()
            
            results["preferences_updated"] = True
        except Exception as e:
             print(f"!!! [ERROR PREFS] Update FAILED: {e}")
             results["errors"].append(str(e))

    # --- AUTO-TRIGGER SEARCH & WORKFLOW SWITCH LOGIC ---
    
    try:
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
        
        # Determine if we should search (Basic logic: if we have any filter, try searching)
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
            print(f"!!! [AUTO SEARCH] Triggering search with: course={c_interest}, score={score}, shifts={shifts}, uni={uni_type}, state={state_pref}")
            
            search_course = ""
            if isinstance(c_interest, list) and len(c_interest) > 0:
                search_course = c_interest[0]
            elif isinstance(c_interest, str):
                search_course = c_interest
                
            opportunities_json = searchOpportunitiesTool(
                user_id=user_id,
                course_name=search_course,
                enem_score=float(score) if score is not None else 0.0,
                shift=shifts,
                institution_type=uni_type,
                university_preference=uni_type, # Explicit: pass uni_type also as university_preference
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
            
    except Exception as e:
        print(f"!!! [AUTO SEARCH ERROR] {e}")
        results["errors"].append(f"Search Error: {str(e)}")


    return json.dumps({"success": True, **results}, ensure_ascii=False)
