import re
import json
from typing import Optional
from src.lib.supabase import supabase
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Cache for city coordinates to avoid repeated API calls
_CITY_COORDS_CACHE = {}

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

def searchOpportunitiesTool(
    course_name: str,
    enem_score: float,
    per_capita_income: Optional[float] = None,
    city_name: Optional[str] = None,
    shift: Optional[str] = None,
    institution_type: Optional[str] = None
) -> str:
    """
    Busca e filtra vagas de Sisu e Prouni no banco de dados. 
    Se city_name for fornecido, prioriza resultados nesta cidade e tenta calcular proximidade.
    """
    
    # 0. Sanitize Inputs
    course_name = sanitize_search_input(course_name)
    if not course_name: 
        # If sanitization removed everything (or it was empty), might want to abort or allow broad search?
        # For safety, let's proceed with empty, but the LIKE %% might return everything if not careful.
        # But course_name is required. If empty, return empty.
        return []

    if city_name:
        city_name = sanitize_search_input(city_name)
    
    # 1. Prepare RPC Parameters
    page_number = 0
    page_size = 20 # Fetch enough courses to find opportunities
    
    # Map institution_type to RPC category
    category = None
    if institution_type:
        itype = institution_type.lower()
        if "púb" in itype or "pub" in itype:
            category = 'SISU'
        elif "priv" in itype:
            category = 'Prouni'
            
    # Determine Sort Strategy
    sort_by = 'relevancia' # Default
    if city_name:
        sort_by = 'proximas'
        
    rpc_params = {
        "page_number": page_number,
        "page_size": page_size,
        "search_query": course_name,
        "category": category,
        "sort_by": sort_by,
        "user_city": city_name,
        # "user_state": ... # We could accept state if available
    }

    print(f"!!! [DEBUG SEARCH] Calling RPC get_courses_with_opportunities with {rpc_params}")

    response = supabase.rpc("get_courses_with_opportunities", rpc_params).execute()
    courses = response.data

    if not courses:
        return []

    # 2. Process and Filter Results (Python Side)
    # We want to return a list of Courses (grouped), not flat opportunities.
    # This matches CourseDisplayData for the frontend.
    
    grouped_courses = []
    
    normalized_shift_filter = str(shift).lower() if shift else None
    
    for course in courses:
        # Each course has an 'opportunities' list
        raw_opps = course.get("opportunities") or []
        filtered_opps = []
        
        for opp in raw_opps:
            # Filter by Cutoff Score
            # Only filter if user has a valid score (>0)
            if enem_score and enem_score > 0:
                opp_score = opp.get("cutoff_score")
                if opp_score and opp_score > enem_score:
                    continue
                
            # Filter by Shift
            if shift:
                # Normalize `shift` argument to a set of lower-case strings for checking
                if isinstance(shift, list):
                    target_shifts = {s.lower() for s in shift if s}
                elif isinstance(shift, str):
                    target_shifts = {shift.lower()}
                else:
                    target_shifts = set()

                # Check for indifference
                is_indifferent = any(x in target_shifts for x in ["indiferente", "tanto faz", "qualquer", "todos"])
                
                if not is_indifferent and target_shifts:
                    opp_shift = str(opp.get("shift", "")).lower()
                    # Check if ANY of the target shifts matches the opportunity shift
                    # (e.g. target=['matutino'], opp='Integral' -> No match?)
                    # Usually stricter match: if target has 'matutino', opp must be 'matutino'.
                    
                    match = False
                    for t in target_shifts:
                        if t in opp_shift or opp_shift in t:
                            match = True
                            break
                    
                    if not match:
                        continue

            # Construct Opportunity Item
            filtered_opps.append({
                "id": opp.get("id"),
                "shift": opp.get("shift"),
                "scholarship_type": opp.get("scholarship_type"),
                "opportunity_type": opp.get("opportunity_type"),
                "cutoff_score": opp.get("cutoff_score"),
                # Add tags if needed, e.g. from concurrency_tags
            })
            
        # Only add course if it has matching opportunities
        if filtered_opps:
            # Map Course Fields to match CourseDisplayData
            # CourseDisplayData: { id, title, institution, location, logoUrl, opportunities: [...] }
            # Note: logoUrl is not in DB yet, can be mocked or omitted.
            
            grouped_courses.append({
                "id": course.get("id"),
                "title": course.get("course_name"),
                "institution": course.get("institution_name"),
                "location": f"{course.get('city')} - {course.get('state')}",
                "distance_km": course.get("distance_km"),
                "opportunities": filtered_opps
            })

    # Extract only IDs for the agent/frontend
    course_ids = [c["id"] for c in grouped_courses]
    total_found = sum(len(c["opportunities"]) for c in grouped_courses)
    
    result_payload = {
        "summary": f"Found {total_found} opportunities in {len(course_ids)} courses.",
        "total_opportunities": total_found,
        "total_courses": len(course_ids),
        "course_ids": course_ids
    }

    # Return as JSON string
    return json.dumps(result_payload, ensure_ascii=False)
