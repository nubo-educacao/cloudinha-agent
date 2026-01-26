from typing import Optional, Dict, Any, List, Union
import json
from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution

# Cache for state mappings
_STATES_CACHE = {}

def _load_states_cache():
    """Load and cache all states from the database."""
    global _STATES_CACHE
    if _STATES_CACHE:
        return
    try:
        response = supabase.table("states").select("uf, name").execute()
        if response.data:
            for row in response.data:
                uf = row["uf"].upper()
                name = row["name"].lower()
                _STATES_CACHE[uf] = uf  # UF -> UF
                _STATES_CACHE[name] = uf  # Full name -> UF
                # Also add unaccented version for common cases
                name_simple = name.replace("á", "a").replace("ã", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ô", "o").replace("ú", "u")
                if name_simple != name:
                    _STATES_CACHE[name_simple] = uf
            print(f"!!! [STATES CACHE] Loaded {len(response.data)} states")
    except Exception as e:
        print(f"[WARN] Failed to load states cache: {e}")

def standardize_state(state_input: str) -> Optional[str]:
    """
    Normalizes a state input (full name or UF) to the standard UF code.
    Returns the UF code (e.g., 'GO', 'MG') or None if not found.
    """
    if not state_input:
        return None
    
    _load_states_cache()
    
    # Clean and lowercase for lookup
    cleaned = state_input.strip().lower()
    
    # Direct lookup
    if cleaned in _STATES_CACHE:
        return _STATES_CACHE[cleaned]
    
    # Try uppercase (for UF codes)
    upper = state_input.strip().upper()
    if upper in _STATES_CACHE:
        return _STATES_CACHE[upper]
    
    # Fallback: Query database directly with fuzzy match
    try:
        response = supabase.table("states").select("uf, name").or_(f"uf.ilike.{cleaned},name.ilike.%{cleaned}%").limit(1).execute()
        if response.data:
            uf = response.data[0]["uf"]
            # Add to cache for future lookups
            _STATES_CACHE[cleaned] = uf
            print(f"!!! [STATE STANDARDIZED] '{state_input}' -> '{uf}'")
            return uf
    except Exception as e:
        print(f"[WARN] State lookup failed for '{state_input}': {e}")
    
    return None


CITY_ABBREVIATIONS = {
    "sp": "São Paulo",
    "rj": "Rio de Janeiro",
    "bh": "Belo Horizonte",
    "bsb": "Brasília",
    "salvador": "Salvador",
    "curitiba": "Curitiba",
    "fortaleza": "Fortaleza",
    "manaus": "Manaus",
    "recife": "Recife",
    "poa": "Porto Alegre",
    "goiania": "Goiânia",
    "belem": "Belém",
    "guarulhos": "Guarulhos",
    "campinas": "Campinas",
    "niteroi": "Niterói"
}

def standardize_city(city_input: str) -> Optional[Dict[str, str]]:
    """
    Looks up a city in the 'cities' table and returns standardized data.
    Returns {"name": standardized_name, "state": state_code} or None.
    """
    if not city_input:
        return None
        
    clean_input = city_input.strip().lower()
    
    # 1. Check abbreviations
    if clean_input in CITY_ABBREVIATIONS:
        # Map abbreviation to full name, then verify it exists in DB (or just trust it)
        # It's better to use the full name for the lookup to get the correct state
        expanded_name = CITY_ABBREVIATIONS[clean_input]
        print(f"!!! [CITY ABBREVIATION] '{clean_input}' -> '{expanded_name}'")
        city_input = expanded_name # Update input for lookup
        
    try:
        # Exact match first
        response = supabase.table("cities").select("name, state").ilike("name", city_input.strip()).limit(1).execute()
        if response.data:
            return {"name": response.data[0]["name"], "state": response.data[0]["state"]}
        
        # Fuzzy/partial match - ONLY if length > 2 to avoid "sp" -> "Aspásia"
        if len(city_input.strip()) > 2:
            response = supabase.table("cities").select("name, state").ilike("name", f"%{city_input.strip()}%").limit(1).execute()
            if response.data:
                return {"name": response.data[0]["name"], "state": response.data[0]["state"]}
        else:
             print(f"!!! [CITY SKIPPING FUZZY] Input '{city_input}' too short for fuzzy match")
            
    except Exception as e:
        print(f"[WARN] City lookup failed for '{city_input}': {e}")
    
    return None

@safe_execution(error_type="tool_error", default_return='{"success": false, "error": "Erro ao atualizar perfil."}')
def updateStudentProfileTool(user_id: str, updates: Dict[str, Any]) -> str:
    """Atualiza os dados do aluno durante a conversa."""
    
    print(f"!!! [DEBUG TOOL] updateStudentProfileTool CALLED with user_id={user_id}, updates={updates}")
    
    results = {
        "profile_updated": False,
        "preferences_updated": False,
        "errors": []
    }

    # Update user_profiles if applicable
    profile_updates = {}
    
    # Standardize city name if provided
    if "city_name" in updates:
        raw_city = updates["city_name"]
        standardized = standardize_city(raw_city)
        if standardized:
            profile_updates["city"] = standardized["name"]
            print(f"!!! [CITY STANDARDIZED] '{raw_city}' -> '{standardized['name']}' ({standardized['state']})")
        else:
            profile_updates["city"] = raw_city  # Keep original if not found
            print(f"!!! [CITY NOT FOUND] Keeping original: '{raw_city}'")
    
    if "age" in updates:
        profile_updates["age"] = updates["age"]
    if "full_name" in updates:
        profile_updates["full_name"] = updates["full_name"]
    if "academic_goal" in updates:
        profile_updates["education"] = updates["academic_goal"] # Support legacy input key
    if "education" in updates:
        profile_updates["education"] = updates["education"]
    if "onboarding_completed" in updates:
        profile_updates["onboarding_completed"] = updates["onboarding_completed"]
    if "active_workflow" in updates:
        profile_updates["active_workflow"] = updates["active_workflow"]

    if profile_updates:
        data = profile_updates.copy()
        data["id"] = user_id
        
        # Use upsert to ensure row exists
        # Removed try/catch, rely on safe_execution
        response = supabase.table("user_profiles").upsert(data, on_conflict="id").execute()
        print(f"!!! [DEBUG WRITE] Update response: {response}")
        results["profile_updated"] = True 
        
        # Invalidate cache
        try:
            from src.tools.getStudentProfile import invalidate_profile_cache
            invalidate_profile_cache(user_id)
        except ImportError:
            pass # Avoid circular dependency crash if any, though structure seems fine

    return json.dumps({"success": True, **results}, ensure_ascii=False)
