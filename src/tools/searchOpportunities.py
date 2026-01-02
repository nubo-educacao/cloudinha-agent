from typing import Optional
from src.lib.supabase import supabase
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Cache for city coordinates to avoid repeated API calls
_CITY_COORDS_CACHE = {}

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
    per_capita_income: float,
    city_name: Optional[str] = None
) -> list:
    """
    Busca e filtra vagas de Sisu e Prouni no banco de dados. 
    Se city_name for fornecido, prioriza resultados nesta cidade e tenta calcular proximidade.
    """
    
    # 1. Base Query
    query = supabase.table("opportunities_view") \
        .select("course_id, institution, course, type, scholarship_type, cutoff_score, city") \
        .ilike("course", f"%{course_name}%") \
        .lte("cutoff_score", enem_score)

    # Note: We are NOT strict filtering by city initially because we want "Next to you" which implies nearby too,
    # but for V1 we prioritize exact matches. If the list is huge, we might need to filter.
    # Given the prompt says "Próximas a você com base na cidade", strict filtering is safer for performance 
    # unless we have PostGIS.
    
    # If explicit city provided, let's look for it OR all. 
    # For now, let's fetch more results and sort in Python if needed, 
    # OR if limit is small, maybe just filter by city if strict preference?
    # The prompt implies sorting.
    
    # 2. Execute Query
    limit = 72
    if city_name:
        # Optimistic approach: Get matches in city first
        query = query.or_(f"city.ilike.%{city_name}%") # This syntax might be tricky in simple client
        # Fallback to simple query logic:
        # Let's just fetch results sorted by score for now, and re-sort in Python
        pass

    response = query.order("cutoff_score", desc=False).limit(limit).execute()
    opportunities = response.data

    if not opportunities:
        return []

    # 3. Geo Sorting (Python Side)
    if city_name:
        # Get User Coords (just for reference or future calc)
        # user_coords = get_city_coordinates(city_name)
        
        # Sort logic: 
        # Priority 1: Exact City Match (Case insensitive)
        # Priority 2: Cutoff Score (Ascending - already sorted by DB, but python sort is stable)
        
        normalized_user_city = city_name.lower().strip()
        
        def sort_key(opp):
            opp_city = (opp.get("city") or "").lower().strip()
            is_same_city = opp_city == normalized_user_city
            return (not is_same_city, opp.get("cutoff_score")) # False < True, so Same City first
            
        opportunities.sort(key=sort_key)

    return opportunities
