import re
import json
from typing import Optional, List, Set, Dict, Union
from src.lib.supabase import supabase
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from src.tools.getStudentProfile import getStudentProfileTool
from src.tools.suggestRefinement import suggestRefinementTool

# Cache for city coordinates to avoid repeated API calls
_CITY_COORDS_CACHE = {}

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

def get_city_coordinates(city_name: str):
    """
    Get latitude and longitude for a city name using Nominatim.
    Uses a simple in-memory cache.
    """
    if city_name in _CITY_COORDS_CACHE:
        return _CITY_COORDS_CACHE[city_name]

    try:
        geolocator = Nominatim(user_agent="cloudinha_agent")
        location = geolocator.geocode(city_name + ", Brasil") # Assuming Brasil context
        if location:
            coords = (location.latitude, location.longitude)
            _CITY_COORDS_CACHE[city_name] = coords
            return coords
    except (GeocoderTimedOut, Exception) as e:
        print(f"Error geocoding {city_name}: {e}")
    
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
    course_name: Optional[str] = None,
    enem_score: Optional[float] = None,
    user_id: str = "user", # Pass user_id to fetch profile fallback
    per_capita_income: Optional[float] = None,
    city_name: Optional[str] = None,
    shift: Union[str, List[str], None] = None, # can be str or list
    institution_type: Optional[str] = None,
    program_preference: Optional[str] = None,
    quota_types: Optional[List[str]] = None,
    user_lat: Optional[float] = None,
    user_long: Optional[float] = None
) -> str:
    """
    Busca vagas de Sisu e Prouni usando RPC match_opportunities otimizada.
    """
    
    # 0. Sanitize Inputs
    course_name = sanitize_search_input(course_name) if course_name else ""
    if city_name:
        city_name = sanitize_search_input(city_name)

    # 1. Fetch Profile and Preferences (Unconditional)
    try:
        profile = getStudentProfileTool(user_id)
    except Exception as e:
        print(f"[WARN] Failed to fetch profile: {e}")
        profile = {}

    # 2. Consolidate Location
    if user_lat is None or user_long is None:
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
    if not city_name:
        # User preference takes precedence
        if profile.get("location_preference"):
             city_name = sanitize_search_input(profile.get("location_preference"))
        elif profile.get("registered_city_name"):
             city_name = sanitize_search_input(profile.get("registered_city_name"))

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

    page_size = 145
    
    rpc_params = {
        "course_interests": course_interests if course_interests else None,
        "enem_score": float(enem_score) if enem_score else None,
        "income_per_capita": float(per_capita_income) if per_capita_income is not None else None,
        "quota_types": quota_types if quota_types else None,
        "preferred_shifts": normalized_shifts if normalized_shifts else None,
        "program_preference": program_preference,
        "user_lat": user_lat,
        "user_long": user_long,
        "city_name": city_name,
        "page_size": page_size,
        "page_number": 0 
    }

    print(f"!!! [DEBUG SEARCH] Calling RPC match_opportunities with {rpc_params}")

    try:
        response = supabase.rpc("match_opportunities", rpc_params).execute()
        courses = response.data
    except Exception as e:
        error_msg = str(e)
        if "statement timeout" in error_msg.lower() or "57014" in error_msg:
             return json.dumps({
                "summary": "A busca foi muito ampla e excedeu o tempo limite. Por favor, peça para o usuário refinar a busca adicionando um Curso específico, Cidade ou Estado.",
                "results": []
            }, ensure_ascii=False)
        return json.dumps({"error": f"RPC call failed: {str(e)}"}, ensure_ascii=False)

    # CHECK OVERFLOW (Strict Requirement: If >= 145, ask for refinement)
    if courses and len(courses) >= 145:
        return json.dumps({
            "summary": "Encontrei muitos resultados (mais de 144). A busca está muito ampla. Por favor, peça para o usuário adicionar mais critérios (Ex: Curso específico, Cidade, Estado ou Instituição).",
            "results": []
        }, ensure_ascii=False)

    if not courses:
        return json.dumps({
            "summary": "Não encontrei cursos correspondentes com os filtros atuais.",
            "results": []
        }, ensure_ascii=False)

    # 2. Process and Filter Results (Python Side)
    processed_results = []
    
    # Pre-calculate excluded tags based on income
    excluded_tags = get_excluded_tags_by_income(per_capita_income if per_capita_income is not None else None)

    total_opportunities_count = 0

    for course in courses:
        raw_opps = course.get("opportunities_json") or []
        filtered_opps_summary = []
        
        # Track metadata for summary
        shifts_found = set()
        types_found = set()
        min_cutoff = 1000.0
        
        for opp in raw_opps:
            # Income Exclusion (Final Safety Check)
            opp_tags = opp.get("concurrency_tags", [])
            if should_exclude_by_income(opp_tags, excluded_tags):
                continue

            # Shift Filter
            is_indifferent_shift = any(x.lower() in ['indiferente', 'tanto faz', 'qualquer'] for x in (shift if isinstance(shift, list) else [str(shift or '')]))
            
            if normalized_shifts and not is_indifferent_shift:
                 opp_shift = normalize_shift(opp.get("shift", ""))
                 if opp_shift not in normalized_shifts:
                     continue
            
            # Add to summary
            filtered_opps_summary.append(opp)
            shifts_found.add(opp.get("shift"))
            types_found.add(opp.get("scholarship_type") or opp.get("opportunity_type"))
            
            sc = opp.get("cutoff_score")
            if sc and sc < min_cutoff:
                min_cutoff = sc

        if filtered_opps_summary:
            total_opportunities_count += len(filtered_opps_summary)
            # Build Output Object (Needed only for persist logic, not for LLM return now)
            processed_results.append({
                "course": course.get("course_name"),
                "institution": course.get("institution_name"),
                "location": f"{course.get('campus_city')} - {course.get('campus_state')}" + (f" ({course.get('distance_km'):.1f}km)" if course.get('distance_km') is not None else ""),
                "opportunities_count": len(filtered_opps_summary),
                "types": list(types_found),
                "shifts": list(shifts_found),
                "best_cutoff": min_cutoff if min_cutoff < 1000 else None,
                "course_id": course.get("course_id") 
            })

    # --- PERSISTENCE: Save Found IDs to Workflow Data ---
    try:
        # Save even if list is empty (clears formatted results)
        if user_id and user_id != "user":
            found_ids = [r["course_id"] for r in processed_results if r.get("course_id")]
            
            curr = supabase.table("user_preferences").select("workflow_data").eq("user_id", user_id).execute()
            current_wf = (curr.data[0].get("workflow_data") if curr.data else {}) or {}
            
            current_wf["last_course_ids"] = found_ids
            current_wf["match_status"] = "reviewing"
            
            supabase.table("user_preferences").update({
                "workflow_data": current_wf
            }).eq("user_id", user_id).execute()
            
            print(f"!!! [SEARCH PERSISTENCE] Saved {len(found_ids)} course IDs to workflow_data.")

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
    if city_name:
        filters_used.append(f"Cidade: {city_name}")
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

    # Integrate Refinement Suggestion if count is high
    if courses_count > 30 and user_id != "user":
        try:
             # Using suggestRefinementTool logic directly
             suggestion = suggestRefinementTool(user_id, courses_count)
             if suggestion and "SUGGESTION:" in suggestion:
                 final_payload["refinement_suggestion"] = suggestion
                 final_payload["summary"] += f"\n\n{suggestion}"
        except Exception as e:
            print(f"[WARN] Failed to generate refinement suggestion: {e}")

    return json.dumps(final_payload, ensure_ascii=False)
