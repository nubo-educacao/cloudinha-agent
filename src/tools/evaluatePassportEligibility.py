from typing import Dict, Any, List
from src.lib.error_handler import safe_execution
from src.agent.agent import supabase_client

def evaluate_json_logic(rule: Any, data: Dict[str, Any]) -> Any:
    """ Evaluates a standard JSON Logic rule against data """
    if not isinstance(rule, dict):
        return rule
    
    if not rule:
        return False
        
    op = list(rule.keys())[0]
    args = rule[op]
    if not isinstance(args, list):
        args = [args]
        
    if op == "var":
        var_name = args[0]
        return data.get(var_name)
    
    eval_args = [evaluate_json_logic(a, data) for a in args]
    
    def compare(a, b, op_str):
        if a is None or b is None: return False
        
        # Try numeric comparison first
        try:
            def clean_num(val):
                if isinstance(val, str):
                    v = val.replace("R$", "").replace(" ", "").strip()
                    if "," in v and "." in v: v = v.replace(".", "").replace(",", ".")
                    elif "," in v: v = v.replace(",", ".")
                    return float(v)
                return float(val)

            a_num = clean_num(a)
            b_num = clean_num(b)
            
            if op_str == ">": return a_num > b_num
            if op_str == ">=": return a_num >= b_num
            if op_str == "<": return a_num < b_num
            if op_str == "<=": return a_num <= b_num
        except (ValueError, TypeError):
            try:
                if op_str == ">": return str(a) > str(b)
                if op_str == ">=": return str(a) >= str(b)
                if op_str == "<": return str(a) < str(b)
                if op_str == "<=": return str(a) <= str(b)
            except:
                return False
        return False
        
    if op in ("==", "==="):
        if isinstance(eval_args[0], str) and isinstance(eval_args[1], str):
            return eval_args[0].strip().lower() == eval_args[1].strip().lower()
        return eval_args[0] == eval_args[1]
    elif op in ("!=", "!=="):
        if isinstance(eval_args[0], str) and isinstance(eval_args[1], str):
            return eval_args[0].strip().lower() != eval_args[1].strip().lower()
        return eval_args[0] != eval_args[1]
    elif op in (">", ">=", "<", "<="):
        return compare(eval_args[0], eval_args[1], op)
    elif op == "in":
        if eval_args[1] is None or eval_args[0] is None: return False
        if isinstance(eval_args[1], list):
            val = eval_args[0]
            if isinstance(val, str):
                return val.strip().lower() in [str(x).strip().lower() for x in eval_args[1]]
            return val in eval_args[1]
        return eval_args[0] in eval_args[1]
    elif op == "and":
        return all(eval_args)
    elif op == "or":
        return any(eval_args)
    elif op == "!":
        return not bool(eval_args[0])
    
    return False


@safe_execution(error_type="evaluate_passport_eligibility_error", default_return={"status": "error", "message": "Failed to evaluate eligibility"})
def evaluatePassportEligibilityTool(user_id: str) -> Dict[str, Any]:
    """
    Evaluates the user's eligibility for available programs based on partner_forms.is_criterion = True.
    It checks mapping_source variables if available in user_profiles.
    
    Args:
        user_id (str): Logging in user ID
        
    Returns:
        dict: List of partners with total criteria and how many are met.
    """
    # 1. Fetch user profile
    parent_res = supabase_client.table("user_profiles").select("active_application_target_id").eq("id", user_id).execute()
    if not parent_res.data:
         return {"status": "error", "message": "User not found"}
    
    target_id = parent_res.data[0].get("active_application_target_id") or user_id
    
    profile_res = supabase_client.table("user_profiles").select("*").eq("id", target_id).execute()
    if not profile_res.data:
         return {"status": "error", "message": "Evaluation target profile not found"}
         
    profile = profile_res.data[0]
    
    # 2. Fetch all criteria forms with partner names
    # First get partners to have names and open status
    partners_res = supabase_client.table("partners").select("id, name, applications_open").execute()
    open_partner_ids = [p["id"] for p in partners_res.data if p.get("applications_open") is True]
    partners_map = {p["id"]: p["name"] for p in partners_res.data}
    
    if not open_partner_ids:
        supabase_client.table("user_profiles").update({
            "eligibility_results": []
        }).eq("id", user_id).execute()
        return {"status": "success", "results": [], "message": "No open partners found."}

    criteria_res = supabase_client.table("partner_forms") \
        .select("partner_id, field_name, mapping_source, criterion_rule") \
        .eq("is_criterion", True) \
        .in_("partner_id", open_partner_ids) \
        .execute()
    
    if not criteria_res.data:
        # Save empty results to parent profile so the UI can safely process the response instead of hanging on null
        supabase_client.table("user_profiles").update({
            "eligibility_results": []
        }).eq("id", user_id).execute()
        return {"status": "success", "results": [], "message": "No criteria found in database."}
         
    # 3. Aggregate by partner
    results = {}
    for crit in criteria_res.data:
        p_id = crit["partner_id"]
        if p_id not in results:
            results[p_id] = {
                "partner_id": p_id,
                "partner_name": partners_map.get(p_id, "Unknown"),
                "total_criteria": 0,
                "met_criteria": 0,
                "details": []
            }
        
        results[p_id]["total_criteria"] += 1
        
        met = False
        mapping = crit.get("mapping_source")
        # mapping_source is usually 'user_profiles.field_name'
        if mapping and mapping.startswith("user_profiles."):
            field = mapping.split(".")[1]
            user_val = profile.get(field)
            
            rule = crit.get("criterion_rule")
            if not rule:
                # If no rule but there's a mapping, simple existence check (or whatever fallback)
                if user_val is not None:
                    met = True
            else:
                # Actual JSON Logic evaluation
                # The 'var' in the DB JSON logic matches the 'field_name' column usually
                var_name = crit["field_name"]
                
                # Check if JSON logic references user_val by field_name or direct mapping
                met = bool(evaluate_json_logic(rule, {var_name: user_val}))
                    
        if met:
            results[p_id]["met_criteria"] += 1
            
        results[p_id]["details"].append({
            "field": crit["field_name"],
            "met": met
        })
        
    final_results = list(results.values())
    
    # 4. Save results to parent profile so UI can render
    supabase_client.table("user_profiles").update({
        "eligibility_results": final_results
    }).eq("id", user_id).execute()
        
    return {
        "status": "success",
        "results": final_results
    }
