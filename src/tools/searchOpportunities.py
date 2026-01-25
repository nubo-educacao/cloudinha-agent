import json
from typing import Optional, List, Set, Dict, Union
from src.lib.supabase import supabase
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.suggestRefinement import suggestRefinementTool
from src.lib.error_handler import safe_execution
from src.lib.resilience import retry_with_backoff

@safe_execution(error_type="tool_error", default_return='{"summary": "Ocorreu um erro interno na busca. Por favor, tente novamente.", "results": [], "error": true}')
@retry_with_backoff(retries=3, min_delay=1.0)
def searchOpportunitiesTool(
    user_id: str,
    course_name: Optional[str] = None,
    enem_score: Optional[float] = None,

    per_capita_income: Optional[float] = None,
    city_name: Optional[str] = None,
    city_names: Optional[List[str]] = None, # New: support multiple cities
    state_name: Optional[str] = None, # New: support state
    state_names: Optional[List[str]] = None, # New: support multiple states
    shift: Union[str, List[str], None] = None, # can be str or list
    institution_type: Optional[str] = None,
    program_preference: Optional[str] = None,
    university_preference: Optional[str] = None, # New: Explicit Uni Pref
    quota_types: Optional[List[str]] = None,
    user_lat: Optional[float] = None,
    user_long: Optional[float] = None
) -> str:
    """
    Busca vagas de Sisu e Prouni usando RPC match_opportunities otimizada.
    """
    print(f"!!! [searchOpportunitiesTool CALLED] user_id='{user_id}', course_name='{course_name}'")
    
    # 0. Inputs are assumed to be sanitized by updateStudentPreferences
    
    # Consolidate Cities
    final_city_names = []
    if city_names:
        final_city_names.extend([c for c in city_names if c])
    if city_name:
        final_city_names.append(city_name)

    # Consolidate States
    final_state_names = []
    if state_names:
        final_state_names.extend([s for s in state_names if s])
    if state_name:
        final_state_names.append(state_name)

    # 1. Fetch Profile and Preferences (Unconditional)
    profile = {}
    if user_id and user_id != "user":
        # Safe tool call
        profile = getStudentProfileTool(user_id)
    else:
        print(f"[WARN] Invalid or missing user_id: {user_id}. Skipping profile fetch.")

    # 2. Consolidate Location & Geocoding
    if user_lat is None and profile.get("device_latitude"):
        try:
             user_lat = float(profile["device_latitude"])
             if profile.get("device_longitude"):
                 user_long = float(profile["device_longitude"])
        except:
             pass

    # !!! CRITICAL LOGIC !!!
    if user_lat is not None and user_long is not None:
         # Check if we should enforce proximity
         is_preference_city = False
         pref_city = profile.get("location_preference")
         if final_city_names and pref_city and len(final_city_names) == 1 and final_city_names[0] == pref_city:
             is_preference_city = True
             
         if not final_city_names or is_preference_city:
             print(f"[DEBUG] Using Lat/Long ({user_lat}, {user_long}) for Proximity Search. Clearing city filter only.")
             final_city_names = None
             # NOTE: Keep final_state_names - user's state preference should still apply
    else:
         print(f"[DEBUG] No Lat/Long available. Using Text Search: {final_city_names}")
            
    # 3. Consolidate Filters (Prioritize Profile/Preferences)
    if per_capita_income is None:
        per_capita_income = profile.get("per_capita_income")
    
    if not quota_types:
        quota_types = profile.get("quota_types")

    if enem_score is None and profile.get("enem_score"):
        enem_score = float(profile["enem_score"])

    if final_city_names is not None and len(final_city_names) == 0 and profile.get("location_preference"):
         final_city_names.append(profile.get("location_preference"))
    
    if final_state_names is not None and len(final_state_names) == 0 and profile.get("state_preference"):
         final_state_names.append(profile.get("state_preference"))

    # 4. Consolidate Course Interests
    profile_interests = profile.get("course_interest") or []
    course_interests = []
    if course_name:
        course_interests.append(course_name)
    if profile_interests:
        if isinstance(profile_interests, list):
            course_interests.extend(profile_interests)
        elif isinstance(profile_interests, str):
             course_interests.append(profile_interests)
    course_interests = list(set(c for c in course_interests if c))

    # Normalize Shifts
    saved_shifts = profile.get("preferred_shifts") or []
    current_shifts = []
    if shift:
        if isinstance(shift, list):
            current_shifts.extend(shift)
        else:
            current_shifts.append(str(shift))
    normalized_shifts = list(set(current_shifts + saved_shifts))

    # Normalize Program Preference
    if not program_preference:
        program_preference = profile.get("program_preference")
    
    # Force ProUni defaults for the current version
    if not program_preference or program_preference == 'indiferente':
        program_preference = 'prouni'
        
    if not university_preference:
        university_preference = profile.get("university_preference")
        
    if not university_preference or university_preference == 'indiferente':
        university_preference = 'privada'
    
    # 5. Prepare RPC Parameters
    page_size = 2880
    
    rpc_params = {
        "p_user_id": user_id, 
        "course_interests": course_interests if course_interests else None,
        "income_per_capita": float(per_capita_income) if per_capita_income is not None else None,
        "quota_types": quota_types if quota_types else None,
        "preferred_shifts": normalized_shifts if normalized_shifts else None,
        "program_preference": program_preference,
        "user_lat": user_lat,
        "user_long": user_long,
        "city_names": final_city_names if final_city_names else None,
        "state_names": final_state_names if final_state_names else None,
        "page_size": page_size,
        "page_number": 0 
    }

    print(f"!!! [DEBUG SEARCH] Calling RPC match_opportunities with {rpc_params}")

    try:
        response = supabase.rpc("match_opportunities", rpc_params).execute()
        courses = response.data
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's a timeout error - treat as "too broad search"
        if "timeout" in error_msg.lower() or "57014" in error_msg:
            print(f"!!! [SEARCH TIMEOUT] {error_msg}")
            refinement_msg = "A busca está muito ampla e demorou demais. Por favor, adicione mais critérios."
            try:
                if user_id and user_id != "user":
                    suggestion = suggestRefinementTool(user_id, 9999) 
                    if suggestion:
                        refinement_msg = suggestion
            except:
                pass
            
            return json.dumps({
                "summary": f"A busca foi muito ampla. {refinement_msg}",
                "results": [],
                "needs_refinement": True
            }, ensure_ascii=False)
        
        # Rethrow other errors to be handled by safe_execution
        raise e

    # CHECK OVERFLOW (Strict Requirement: If >= 2880, ask for refinement)
    if courses and len(courses) >= 2880:
        refinement_msg = "A busca está muito ampla. Por favor, peça para o usuário adicionar mais critérios."
        suggestion = None
        
        try:
             if user_id and user_id != "user":
                 suggestion = suggestRefinementTool(user_id, len(courses))
                 if suggestion:
                     refinement_msg = suggestion
        except:
             pass

        return json.dumps({
            "summary": f"Encontrei muitos resultados (mais de 2879). {refinement_msg}",
            "results": [],
            "refinement_suggestion": suggestion
        }, ensure_ascii=False)

    if not courses:
        return json.dumps({
            "summary": "Não encontrei cursos correspondentes com os filtros atuais.",
            "results": []
        }, ensure_ascii=False)

    # 3. Aggregation & Persistence
    match_map = {}
    unique_course_ids = []
    
    for row in courses:
        c_id = row.get("course_id")
        o_id = row.get("opportunity_id")
        
        if c_id:
             if c_id not in match_map:
                 match_map[c_id] = []
                 unique_course_ids.append(c_id) 
             
             if o_id:
                 match_map[c_id].append(o_id)

    # Deduplicate Opportunity IDs per course
    for c_id in match_map:
        match_map[c_id] = list(set(match_map[c_id]))

    # --- PERSISTENCE: Save Found IDs to Workflow Data ---
    print(f"!!! [PERSISTENCE DEBUG] Entering persistence block. user_id='{user_id}', unique courses={len(unique_course_ids)}")
    
    # removed try/catch, handled by safe_execution
    if user_id and user_id != "user":
        curr = supabase.table("user_preferences").select("workflow_data").eq("user_id", user_id).execute()
        current_wf = (curr.data[0].get("workflow_data") if curr.data else {}) or {}
        
        current_wf["last_course_ids"] = unique_course_ids
        current_wf["last_opportunity_map"] = match_map 
        current_wf["match_status"] = "reviewing"
        
        result = supabase.table("user_preferences").update({
            "workflow_data": current_wf
        }).eq("user_id", user_id).execute()
        
        print(f"!!! [SEARCH PERSISTENCE] Saved {len(unique_course_ids)} course IDs and Map to workflow_data.")
    else:
        print(f"!!! [PERSISTENCE SKIPPED] user_id is invalid or 'user': {user_id}")


    # 4. Create Final Output (CONCISE for Agent)
    courses_count = len(unique_course_ids)
    total_opportunities_count = sum(len(v) for v in match_map.values())
    
    if courses_count == 0:
         return json.dumps({
            "summary": "Após a filtragem detalhada, não encontrei cursos compatíveis.",
            "results": []
        }, ensure_ascii=False)

    summary_text = (
        f"Encontrei {courses_count} cursos e um total de {total_opportunities_count} oportunidades nas quais você se encaixa. "
        "Os detalhes estão disponíveis no painel ao lado."
    )
    
    filters_used = []
    if course_interests:
        filters_used.append(f"Cursos: {', '.join(course_interests)}")
    if final_city_names:
        filters_used.append(f"Cidades: {', '.join(final_city_names)}")
    if final_state_names:
        filters_used.append(f"Estados: {', '.join(final_state_names)}")
    if normalized_shifts and not any(s.lower() in ['indiferente', 'qualquer'] for s in normalized_shifts):
        filters_used.append(f"Turno: {', '.join(normalized_shifts)}")
    if program_preference and program_preference != 'indiferente':
        filters_used.append(f"Programa: {program_preference.capitalize()}")
    if enem_score:
         filters_used.append(f"Nota Enem: {enem_score}")
    if per_capita_income:
         filters_used.append(f"Renda: R$ {per_capita_income}")
         
    if filters_used:
        summary_text += " Parâmetros utilizados: " + " | ".join(filters_used) + "."
        
    final_payload = {
        "summary": summary_text,
        "results": [], 
        "refinement_suggestion": None
    }

    if courses_count > 12 and user_id != "user":
         if suggestRefinementTool:
             # safe_execution won't wrap this automatically if imported? 
             # suggestRefinementTool variable refers to what's imported.
             # I need to ensure suggestRefinementTool is also safe.
             suggestion = suggestRefinementTool(user_id, courses_count)
             if suggestion and "SUGGESTION:" in suggestion:
                 final_payload["refinement_suggestion"] = suggestion
                 final_payload["summary"] += f"\n\n{suggestion}"

    return json.dumps(final_payload, ensure_ascii=False)
