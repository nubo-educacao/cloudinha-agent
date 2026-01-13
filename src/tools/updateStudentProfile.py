from typing import Optional, Dict, Any, List, Union
import json
from src.lib.supabase import supabase

def updateStudentProfileTool(user_id: str, updates: Dict[str, Any]) -> str:
    """Atualiza os dados do aluno durante a conversa."""
    
    # --- DEBUG ALIAS ---
    if user_id == "user":
        user_id = "dac47479-079f-4878-bb43-009e4879fa8b"
        print(f"!!! [DEBUG] Aliased 'user' to {user_id}")

    print(f"!!! [DEBUG TOOL] updateStudentProfileTool CALLED with user_id={user_id}, updates={updates}")
    
    results = {
        "profile_updated": False,
        "preferences_updated": False,
        "errors": []
    }

    # Update user_profiles if applicable
    profile_updates = {}
    if "city_name" in updates:
        profile_updates["city"] = updates["city_name"]
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
        try:
            response = supabase.table("user_profiles").upsert(data, on_conflict="id").execute()
            print(f"!!! [DEBUG WRITE] Update response: {response}")
            results["profile_updated"] = True 
        except Exception as e:
            print(f"!!! [ERROR WRITE] Update FAILED: {e}")
            results["errors"].append(str(e))

    # Update user_preferences if applicable
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
                    # try extracting numbers if mixed text? simple cast for now
                    preferences_updates["enem_score"] = float(raw_score)
                except:
                    # Fallback default
                    print(f"[WARN] Could not parse enem_score '{raw_score}', defaulting to 0")
                    preferences_updates["enem_score"] = 0.0
        else:
             preferences_updates["enem_score"] = float(raw_score) if raw_score is not None else 0.0

    if "per_capita_income" in updates:
        preferences_updates["family_income_per_capita"] = updates["per_capita_income"]
    
    # --- 2. Course Normalization ---
    if "course_interest" in updates:
        preferences_updates["course_interest"] = updates["course_interest"]
    if "course_name" in updates:
        preferences_updates["course_interest"] = updates["course_name"]
    
    # --- 3. Workflow Data Merge ---
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
        preferences_updates["state_preference"] = updates["state_preference"]
    if "city_name" in updates:
        preferences_updates["location_preference"] = updates["city_name"]

    # --- 4. Shift Normalization ---
    if "shift" in updates:
        val = updates["shift"]
        # Handle "Indiferente"
        is_indifferent = False
        if isinstance(val, str):
            clean = val.lower()
            if "indiferente" in clean or "qualquer" in clean or "tanto faz" in clean:
                is_indifferent = True
        elif isinstance(val, list) and len(val) == 1 and isinstance(val[0], str):
             clean = val[0].lower()
             if "indiferente" in clean or "qualquer" in clean:
                 is_indifferent = True
                 
        if is_indifferent:
            # We treat indifferent as "Null" in logic often, or "All".
            # Let's map to a comprehensive list to be explicit? Or keep it None?
            # searchOpportunities tool handles `None` as "don't filter".
            # But DB column `preferred_shifts` is array. 
            # Ideally store full list: ['Matutino', 'Vespertino', 'Noturno'] or special value.
            # Storing None/Empty is safer for "No Preference".
            preferences_updates["preferred_shifts"] = [] 
        else:
            if isinstance(val, list):
                preferences_updates["preferred_shifts"] = val
            else:
                 preferences_updates["preferred_shifts"] = [str(val)]

    # --- 5. Institution Type Normalization ---
    if "institution_type" in updates:
        itype = str(updates["institution_type"]).lower()
        if "púb" in itype or "pub" in itype:
            preferences_updates["university_preference"] = "publica"
        elif "priv" in itype:
             preferences_updates["university_preference"] = "privada"
        else:
             # Indiferente/Qualquer -> "indiferente"
             preferences_updates["university_preference"] = "indiferente"
    
    if preferences_updates:
        # Check existence manually first
        existing_prefs_response = supabase.table("user_preferences") \
            .select("id") \
            .eq("user_id", user_id) \
            .maybe_single() \
            .execute()
        
        existing_prefs = existing_prefs_response.data if existing_prefs_response else None

        if existing_prefs:
            # Update
            supabase.table("user_preferences") \
                .update(preferences_updates) \
                .eq("id", existing_prefs["id"]) \
                .execute()
        else:
            # Insert
            data = preferences_updates.copy()
            data["user_id"] = user_id
            supabase.table("user_preferences").insert(data).execute()
        
        results["preferences_updated"] = True

    # --- AUTO-TRIGGER SEARCH LOGIC ---
    # Deterministic flow: If we have the 4 required fields (either from this update or existing), run search.
    
    # helper to get final value (update > existing)
    def get_val(key, update_key=None):
        if update_key and update_key in updates:
            return updates[update_key]
        if key in preferences_updates:
            return preferences_updates[key]
        # Fallback to fetching specific field if not in update (expensive? maybe just fetch all if needed)
        return None 

    # We need a consolidated view of the user's preferences to decide if we can search
    # Since we might have done partial updates, let's fetch the fresh row from DB to be checking "Truth"
    try:
        final_prefs = supabase.table("user_preferences").select("*").eq("user_id", user_id).maybe_single().execute()
        pf = final_prefs.data if final_prefs else {}
        
        # Check requirements
        # 1. Course
        c_interest = pf.get("course_interest")
        # 2. Score
        score = pf.get("enem_score")
        # 3. Shift (array or single?) - DB is array 'preferred_shifts', inputs often single 'shift'
        shifts = pf.get("preferred_shifts")
        # 4. Institution Type
        uni_type = pf.get("university_preference")

        # Validation
        has_course = bool(c_interest)
        # Relaxed validation: We accept 0/None for others if user hasn't provided
        # The agent logic determines when to call this tool. If called with course, we assume readiness or at least partial search capability.
        
        has_score = score is not None 
        has_shift = bool(shifts)
        has_uni = bool(uni_type)

        print(f"!!! [DEBUG AUTO SEARCH] Checking Flags: Course={has_course} ({c_interest}), Score={has_score} ({score}), Shift={has_shift} ({shifts}), Uni={has_uni} ({uni_type})")
        print(f"!!! [DEBUG AUTO SEARCH] Full Prefs: {pf}")

        if has_course:
            print(f"!!! [AUTO SEARCH] Triggering search with: {c_interest}, {score}, {shifts}, {uni_type}")
            
            # Map params
            # searchTool expects: course_name, enem_score, per_capita_income, city_name, shift, institution_type
            
            # Auto-Search
            from src.tools.searchOpportunities import searchOpportunitiesTool
            
            opportunities_json = searchOpportunitiesTool(
                course_name=c_interest,
                enem_score=float(score),
                shift=shifts, # Pass the full list
                institution_type=uni_type
            )
            
            # Return these results directly to the agent
            # We parse it back to an object so the final output is clean JSON (not a string inside JSON)
            try:
                results["auto_search_results"] = json.loads(opportunities_json)
            except:
                # Fallback if search returns distinct type or invalid json
                results["auto_search_results"] = opportunities_json
                
            results["search_performed"] = True
            
    except Exception as e:
        print(f"!!! [AUTO SEARCH ERROR] {e}")


    return json.dumps({"success": True, **results}, ensure_ascii=False)
