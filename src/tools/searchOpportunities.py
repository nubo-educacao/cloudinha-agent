import re
import json
from typing import Optional, List, Set, Dict, Union
from src.lib.supabase import supabase
# from geopy.geocoders import Nominatim (Removed)
# from geopy.exc import GeocoderTimedOut (Removed)
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.suggestRefinement import suggestRefinementTool
from src.tools.updateStudentProfile import standardize_state


# Constants for Income Logic
SALARIO_MINIMO = 1621.0
RENDA_INTEGRAL_THRESHOLD = 1.5 * SALARIO_MINIMO  # 2431.50
RENDA_PARCIAL_THRESHOLD = 3.0 * SALARIO_MINIMO   # 4863.00

TAGS_RENDA = {
    'INTEGRAL', 'PARCIAL', 
    'RENDA_ATE_1_SM', 'RENDA_ATE_1_5_SM', 
    'RENDA_ATE_2_SM', 'RENDA_ATE_4_SM'
}

def sanitize_search_input(text: str) -> str:
    """
    Sanitize input string by removing potentially dangerous characters.
    Allows alphanumeric, spaces, hyphens, periods, and accents.
    """
    if not text:
        return ""
    # Keep only safe characters: letters (including unicode), numbers, spaces, - and .
    return re.sub(r'[^a-zA-ZÀ-ÿ0-9\s\-\.]', '', text)

def get_city_coordinates_from_db(city_name: str, state_code: Optional[str] = None):
    """
    Get latitude and longitude for a city name using the Supabase 'cities' table.
    """
    if not city_name:
        return None

    try:
        query = supabase.table("cities").select("latitude, longitude").ilike("name", city_name)
        
        if state_code:
            query = query.eq("state", state_code)
            
        result = query.execute()
        
        if result.data and len(result.data) > 0:
            # Return the first match (usually accurate enough if state is provided)
            record = result.data[0]
            return float(record['latitude']), float(record['longitude'])
            
    except Exception as e:
        print(f"Error fetching coordinates for {city_name} from DB: {e}")
    
    return None

def normalize_shift(shift_value: str) -> str:
    """Normaliza valores de turno, tratando EAD como equivalente."""
    if not shift_value:
        return ""
    
    lower = shift_value.lower().strip()
    
    # Normalizar EAD
    if 'ead' in lower or 'distância' in lower or 'distancia' in lower:
        return 'EAD'
    
    # Capitalizar outros turnos
    shift_map = {
        'matutino': 'Matutino',
        'vespertino': 'Vespertino',
        'noturno': 'Noturno',
        'integral': 'Integral'
    }
    return shift_map.get(lower, shift_value.capitalize())

def get_excluded_tags_by_income(income: float) -> Set[str]:
    """Retorna tags que devem ser excluídas baseado na renda."""
    if income is None:
        return set()
    
    excluded = set()
    
    if income > RENDA_PARCIAL_THRESHOLD:  # > 3 SM
        excluded.update(['INTEGRAL', 'PARCIAL', 'RENDA_ATE_1_SM', 
                        'RENDA_ATE_1_5_SM', 'RENDA_ATE_2_SM'])
    elif income > RENDA_INTEGRAL_THRESHOLD:  # > 1.5 SM
        excluded.update(['INTEGRAL', 'RENDA_ATE_1_SM', 'RENDA_ATE_1_5_SM'])
    elif income > 2 * SALARIO_MINIMO:  # > 2 SM
        excluded.update(['RENDA_ATE_1_SM', 'RENDA_ATE_1_5_SM', 'RENDA_ATE_2_SM'])
    elif income > SALARIO_MINIMO:  # > 1 SM
        excluded.update(['RENDA_ATE_1_SM'])
    
    return excluded

def should_exclude_by_income(opp_tags: list, excluded: Set[str]) -> bool:
    """Verifica se oportunidade deve ser excluída por renda."""
    if not excluded or not opp_tags:
        return False
    
    # opp_tags é JSONB: [[tag1, tag2], [tag3]]
    for tag_group in opp_tags:
        if isinstance(tag_group, list):
            # Se TODOS os tags importantes do grupo são de renda excluída, exclui o grupo
            # Mas cuidado: um grupo pode ter [AMPLA, INTEGRAL]. Se excluir INTEGRAL, sobra AMPLA?
            # A lógica original do Match diz: Tags são cumulativas para a vaga. 
            # Se a vaga pede (RENDA_ATE_1_SM E PPI), e user tem renda alta -> Exclui.
            
            # Simplificação segura: Se o grupo contem ALGUMA tag de renda que o usuario NAO atende
            # E essa tag é restritiva (exige renda baixa), então esse grupo não serve.
            # Se a oportunidade só tem grupos inválidos, ela é excluída.
             
            # Aqui estamos validando SE a oportunidade deve ser excluída.
            # Se o grupo tem uma tag Excluída, esse grupo é invalido.
            pass

    # Simplified Logic: Check if ANY valid group remains.
    # If all groups are invalid, return True (Exclude).
    
    has_valid_group = False
    for tag_group in opp_tags:
        if isinstance(tag_group, list):
            # Check if this group is valid
            group_is_invalid = any(tag in excluded for tag in tag_group)
            if not group_is_invalid:
                has_valid_group = True
                break
                
    return not has_valid_group

def matches_quota_filter(opp_tags: list, user_quotas: List[str]) -> bool:
    """Verifica se oportunidade atende às cotas do usuário."""
    if not user_quotas:
        return True  # Sem filtro explicito de cotas = aceita tudo (ou agente decide)
        # Note: Se o user não passou cotas, assumimos que ele quer ver tudo ou o RPC já filtrou o básico.
        # Mas para ser seguro, se user nao tem cotas, ele só deveria ver Ampla? 
        # Geralmente sim. Mas se o parametro quota_types veio vazio, o RPC traz tudo.
        # Vamos manter permissivo aqui e deixar o RPC ou o user decidir.
    
    # O RPC 'match_opportunities' já faz filtro de inclusão:
    # (quota_types IS NULL ... OR EXISTS ... (AMPLA OR user_quota))
    # Então aqui no Python é só double-check se precisarmos.
    # Mas como o RPC retorna, vamos confiar no RPC para a "Inclusão".
    return True

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
    
    # 0. Sanitize Inputs
    course_name = sanitize_search_input(course_name) if course_name else ""
    
    # Consolidate Cities
    final_city_names = []
    if city_names:
        final_city_names.extend([sanitize_search_input(c) for c in city_names if c])
    if city_name:
        final_city_names.append(sanitize_search_input(city_name))

    # Consolidate States
    final_state_names = []
    if state_names:
        final_state_names.extend([sanitize_search_input(s) for s in state_names if s])
    if state_name:
        final_state_names.append(sanitize_search_input(state_name))

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
    # A. If City provided -> Try to resolve Coords from DB -> If Found, Use Coords + Clear City Filter (Proximity Search)
    # B. If No City but Device Location -> Use Device Location
    
    is_proximity_search = False
    
    # Try to resolve coordinates from the first requested city
    if final_city_names:
        target_city = final_city_names[0]
        # Try to find a hint for the state to disambiguate
        target_state = final_state_names[0] if final_state_names else None
        
        coords = get_city_coordinates_from_db(target_city, target_state)
        
        if coords:
            print(f"[DEBUG] Resolved {target_city} to {coords}. Switch to PROXIMITY SEARCH.")
            user_lat, user_long = coords
            # !!! CRITICAL CHANGE !!!
            # Clear text filters to allow returning results from neighboring cities
            final_city_names = None 
            final_state_names = None 
            is_proximity_search = True
        else:
            print(f"[DEBUG] Could not resolve coordinates for {target_city}. Fallback to TEXT FILTER.")
    
    # Fallback to Device Location if not searching for a specific city
    if (user_lat is None or user_long is None) and not is_proximity_search:
        if profile.get("device_latitude") and profile.get("device_longitude"):
            user_lat = float(profile["device_latitude"])
            user_long = float(profile["device_longitude"])
            
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
         final_city_names.append(sanitize_search_input(profile.get("location_preference")))
    
    # [FIX] Always load State from preferences
    if not final_state_names and profile.get("state_preference"):
         final_state_names.append(sanitize_search_input(profile.get("state_preference")))
    
    # [FIX] Handle Common Abbreviations (Simple Mapping)
    CITY_ABBREVIATIONS = {
        "sp": "São Paulo",
        "rj": "Rio de Janeiro",
        "bh": "Belo Horizonte",
        "df": "Brasília",
        "bsb": "Brasília"
    }

    # Expand/Map cities (Only if we are using text search)
    mapped_cities = []
    if final_city_names:
        for city in final_city_names:
            lower_city = city.lower().strip()
            if lower_city in CITY_ABBREVIATIONS:
                 mapped_cities.append(CITY_ABBREVIATIONS[lower_city])
            else:
                 mapped_cities.append(city)
        final_city_names = list(set(mapped_cities))
    
    # States: Normalize to UF codes using standardize_state
    normalized_states = []
    if final_state_names:
        for s in final_state_names:
            if s:
                normalized = standardize_state(s.strip())
                if normalized:
                    normalized_states.append(normalized)
                else:
                    # Fallback: keep as uppercase if not found in DB
                    normalized_states.append(s.strip().upper())
    final_state_names = list(set(normalized_states))

    # 4. Consolidate Course Interests
    # Get interests from profile
    profile_interests = profile.get("course_interest") or []
    
    # Function allows explicit course_name override/addition
    course_interests = []
    if course_name:
        course_interests.append(sanitize_search_input(course_name))
    
    # Add profile interests if available
    if profile_interests:
        if isinstance(profile_interests, list):
            course_interests.extend(profile_interests)
        elif isinstance(profile_interests, str):
             course_interests.append(profile_interests)
             
    # Remove duplicates and empties
    course_interests = list(set(c for c in course_interests if c))

    # Normalize Shifts
    # [FIX] Merge/Use saved shifts
    saved_shifts = profile.get("preferred_shifts") or []
    
    current_shifts = []
    if shift:
        if isinstance(shift, list):
            current_shifts.extend(shift)
        else:
            current_shifts.append(str(shift))
    
    # Combine current arg shifts with saved shifts
    # (Assuming we want to match ANY preference)
    all_shifts = list(set(current_shifts + saved_shifts))
    
    normalized_shifts = []
    for s in all_shifts:
        norm = normalize_shift(s)
        if norm:
            normalized_shifts.append(norm)
    
    # Remove duplicates
    normalized_shifts = list(set(normalized_shifts))

    # Normalize Program Preference
    # If not provided arg, check profile
    if not program_preference and not institution_type:
        program_preference = profile.get("program_preference")
        
    # [FIX] Consolidate University Preference
    if not university_preference:
        university_preference = profile.get("university_preference")

    if not program_preference and institution_type:
        itype = institution_type.lower()
        if "púb" in itype or "pub" in itype or "sisu" in itype:
            program_preference = 'sisu'
        elif "priv" in itype or "prouni" in itype:
            program_preference = 'prouni'
    elif program_preference:
        program_preference = program_preference.lower()
        if "sisu" in program_preference:
            program_preference = "sisu"
        elif "prouni" in program_preference:
            program_preference = "prouni"
    
    # 5. Prepare RPC Parameters
    # [FIX] If searching for Prouni, ignore Sisu-specific quota tags like 'ESCOLA_PUBLICA'
    # which might block results if the Prouni dataset doesn't use them.
    if program_preference == 'prouni':
        quota_types = None

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
