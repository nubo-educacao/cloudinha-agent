import json
from typing import Optional, List, Set, Dict, Union
from src.lib.supabase import supabase
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.suggestRefinement import suggestRefinementTool






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
        try:
            profile = getStudentProfileTool(user_id)
        except Exception as e:
            print(f"[WARN] Failed to fetch profile: {e}")
            profile = {}
    else:
        print(f"[WARN] Invalid or missing user_id: {user_id}. Skipping profile fetch.")

    # 2. Consolidate Location
    # 2. Consolidate Location & Geocoding
    # Priority:
    # If device/preference Lat/Long provided -> Use Coordinate Search (Proximity) and DISABLE text filter
    # If no Lat/Long -> Use city/state text filter
    
    # Check if we have coordinates from profile (which now includes preferences geolocation)
    if user_lat is None and profile.get("device_latitude"):
        try:
             user_lat = float(profile["device_latitude"])
             if profile.get("device_longitude"):
                 user_long = float(profile["device_longitude"])
        except:
             pass

    # !!! CRITICAL LOGIC !!!
    # If we have coordinates, we assume the user wants proximity search centered on these coordinates.
    # To enable SQL proximity search order, we MUST clear the text-based city/state filter.
    # The only exception is if the user EXPLICITLY provided city_names to THIS tool call (overriding preferences),
    # but currently we assume preference-based flow.
    # (If city_names is passed as ARGUMENT, it overrides. If it came from preferences, we drop it in favor of coords)
    
    # We differentiate: `city_names` arg vs `profile["location_preference"]` logic
    # In Step 0, `final_city_names` was built.
    # If `final_city_names` matches the preference city, AND we have coords, we drop the text filter.
    
    if user_lat is not None and user_long is not None:
         # Check if we should enforce proximity
         # If the gathered cities are just the preference one, we switch to proximity
         is_preference_city = False
         pref_city = profile.get("location_preference")
         if final_city_names and pref_city and len(final_city_names) == 1 and final_city_names[0] == pref_city:
             is_preference_city = True
             
         if not final_city_names or is_preference_city:
             print(f"[DEBUG] Using Lat/Long ({user_lat}, {user_long}) for Proximity Search. Clearing text filters.")
             final_city_names = None
             final_state_names = None
    else:
         print(f"[DEBUG] No Lat/Long available. Using Text Search: {final_city_names}")
            
    # 3. Consolidate Filters (Prioritize Profile/Preferences)
    if per_capita_income is None:
        per_capita_income = profile.get("per_capita_income")
    
    # [FIX] Always defer to saved quotas if not provided (or even if provided, depending on logic, but here efficient fallback)
    if not quota_types:
        quota_types = profile.get("quota_types")

    # [FIX] Always load ENEM score from preferences if not explicit
    if enem_score is None and profile.get("enem_score"):
        enem_score = float(profile["enem_score"])

    # [FIX] Always load Location from preferences (location_preference > registered_city)
    if not final_city_names and profile.get("location_preference"):
         final_city_names.append(profile.get("location_preference"))
    
    # [FIX] Always load State from preferences
    if not final_state_names and profile.get("state_preference"):
         final_state_names.append(profile.get("state_preference"))

    # 4. Consolidate Course Interests
    # Get interests from profile
    profile_interests = profile.get("course_interest") or []
    
    # Function allows explicit course_name override/addition
    course_interests = []
    if course_name:
        course_interests.append(course_name)
    
    # Add profile interests if available
    if profile_interests:
        if isinstance(profile_interests, list):
            course_interests.extend(profile_interests)
        elif isinstance(profile_interests, str):
             course_interests.append(profile_interests)
             
    # Remove duplicates and empties
    course_interests = list(set(c for c in course_interests if c))

    # Normalize Shifts
    saved_shifts = profile.get("preferred_shifts") or []
    
    current_shifts = []
    if shift:
        if isinstance(shift, list):
            current_shifts.extend(shift)
        else:
            current_shifts.append(str(shift))
    
    # Combine current arg shifts with saved shifts
    # (Assuming we want to match ANY preference)
    normalized_shifts = list(set(current_shifts + saved_shifts))

    # Normalize Program Preference
    # If not provided arg, check profile
    if not program_preference:
        program_preference = profile.get("program_preference")
        
    # [FIX] Consolidate University Preference
    if not university_preference:
        university_preference = profile.get("university_preference")
    
    # 5. Prepare RPC Parameters
    # [FIXED] Removed logic that cleared quota_types for Prouni.
    # We now respect user's selected quotas (even for Prouni) + Ampla Concorrência Logic is handled by SQL.

    page_size = 2880
    
    rpc_params = {
        "course_interests": course_interests if course_interests else None,
        "enem_score": float(enem_score) if enem_score else None,
        "income_per_capita": float(per_capita_income) if per_capita_income is not None else None,
        "quota_types": quota_types if quota_types else None,
        "preferred_shifts": normalized_shifts if normalized_shifts else None,
        "program_preference": program_preference,
        "user_lat": user_lat,
        "user_long": user_long,
        "city_names": final_city_names if final_city_names else None,
        "state_names": final_state_names if final_state_names else None,
        "university_preference": None,  # Always pass None - filter not implemented in RPC yet
        "page_size": page_size,
        "page_number": 0 
    }

    # Search proceeds with any parameter defined - no quota-only guard needed

    print(f"!!! [DEBUG SEARCH] Calling RPC match_opportunities with {rpc_params}")

    try:
        response = supabase.rpc("match_opportunities", rpc_params).execute()
        courses = response.data
    except Exception as e:
        error_msg = str(e)
        print(f"!!! [SEARCH ERROR] RPC failed: {error_msg}")
        
        # Check if it's a timeout error - treat as "too broad search"
        if "timeout" in error_msg.lower() or "57014" in error_msg:
            refinement_msg = "A busca está muito ampla e demorou demais. Por favor, adicione mais critérios."
            try:
                if user_id and user_id != "user":
                    suggestion = suggestRefinementTool(user_id, 9999)  # Fake high count for refinement
                    if suggestion:
                        refinement_msg = suggestion
            except:
                pass
            
            return json.dumps({
                "summary": f"A busca foi muito ampla. {refinement_msg}",
                "results": [],
                "needs_refinement": True
            }, ensure_ascii=False)
        
        # Other RPC errors - generic message
        return json.dumps({
            "summary": "Ocorreu um erro interno na busca. Por favor, tente novamente mais tarde ou refine a busca com cidade e curso específicos.",
            "results": [],
            "error": True
        }, ensure_ascii=False)

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

    # 2. Process Results (Python Side)
    # NOTE: The RPC now returns FLAT records (one per course group), not nested opportunities_json
    processed_results = []
    total_opportunities_count = 0

    for course in courses:
        # Each course record IS the opportunity data (already aggregated by RPC)
        # No more opportunities_json iteration needed
        
        course_shift = course.get("shift", "")
        course_type = course.get("opportunity_type", "")
        course_cutoff = course.get("cutoff_score")
        
        # Build Output Object
        processed_results.append({
            "course": course.get("course_name"),
            "institution": course.get("institution_name"),
            "location": f"{course.get('campus_city')} - {course.get('campus_state')}" + (f" ({course.get('distance_km'):.1f}km)" if course.get('distance_km') is not None else ""),
            "opportunities_count": 1,  # Each record is one grouped opportunity
            "types": [course_type] if course_type else [],
            "shifts": [course_shift] if course_shift else [],
            "best_cutoff": float(course_cutoff) if course_cutoff is not None else None,
            "course_id": course.get("course_id") 
        })
        total_opportunities_count += 1

    # --- PERSISTENCE: Save Found IDs to Workflow Data ---
    print(f"!!! [PERSISTENCE DEBUG] Entering persistence block. user_id='{user_id}', processed_results count={len(processed_results)}")
    try:
        # Save even if list is empty (clears formatted results)
        if user_id and user_id != "user":
            found_ids = [r["course_id"] for r in processed_results if r.get("course_id")]
            print(f"!!! [PERSISTENCE DEBUG] Extracted {len(found_ids)} course_ids to save.")
            
            curr = supabase.table("user_preferences").select("workflow_data").eq("user_id", user_id).execute()
            current_wf = (curr.data[0].get("workflow_data") if curr.data else {}) or {}
            
            current_wf["last_course_ids"] = found_ids
            current_wf["match_status"] = "reviewing"
            
            result = supabase.table("user_preferences").update({
                "workflow_data": current_wf
            }).eq("user_id", user_id).execute()
            
            print(f"!!! [SEARCH PERSISTENCE] Saved {len(found_ids)} course IDs to workflow_data. Update result: {result.data}")
        else:
            print(f"!!! [PERSISTENCE SKIPPED] user_id is invalid or 'user': {user_id}")

    except Exception as e:
        print(f"!!! [SEARCH PERSISTENCE ERROR] Failed to save IDs: {e}")

    # 3. Create Final Output (CONCISE for Agent)
    # Return ONLY the count summary. No results list to save tokens.
    
    courses_count = len(processed_results)
    
    if courses_count == 0:
         return json.dumps({
            "summary": "Após a filtragem detalhada, não encontrei cursos compatíveis.",
            "results": []
        }, ensure_ascii=False)

    summary_text = (
        f"Encontrei {courses_count} cursos e um total de {total_opportunities_count} oportunidades nas quais você se encaixa. "
        "Os detalhes estão disponíveis no painel ao lado."
    )
    
    # Append Active Filters to Summary for Agent Context
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
        "results": [], # Empty results for LLM context optimization
        "refinement_suggestion": None
    }

    # Integrate Refinement Suggestion if count is high (> 12 results)
    if courses_count > 12 and user_id != "user":
        try:
             # Using suggestRefinementTool logic directly
             suggestion = suggestRefinementTool(user_id, courses_count)
             if suggestion and "SUGGESTION:" in suggestion:
                 final_payload["refinement_suggestion"] = suggestion
                 final_payload["summary"] += f"\n\n{suggestion}"
        except Exception as e:
            print(f"[WARN] Failed to generate refinement suggestion: {e}")

    return json.dumps(final_payload, ensure_ascii=False)
