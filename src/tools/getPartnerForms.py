from typing import Dict, List, Any
from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution


@safe_execution(error_type="tool_error", default_return=[])
def getPartnerFormsTool(user_id: str, partner_id: str = None) -> List[Dict[str, Any]]:
    """
    Retorna os campos e regras do formulário de um parceiro específico.
    Se partner_id for omitido, busca automaticamente o parceiro da aplicação ativa (DRAFT) para o user_id fornecido.
    """
    import uuid
    print(f"[DEBUG TOOL] getPartnerFormsTool called with user_id={user_id}, partner_id={partner_id}")
    
    resolved_partner_id = partner_id
    
    # 1. Auto-detection logic
    if not resolved_partner_id:
        if not user_id:
            print("[DEBUG TOOL] Error: partner_id and user_id are both missing.")
            return []
            
        print(f"[DEBUG TOOL] Attempting auto-detection for user_id={user_id}")
        active_app = (
            supabase
            .table("student_applications")
            .select("partner_id")
            .eq("user_id", user_id)
            .eq("status", "DRAFT")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if not active_app.data:
            print(f"[DEBUG TOOL] No DRAFT application found for {user_id}")
            return []
        resolved_partner_id = active_app.data[0]["partner_id"]
        print(f"[DEBUG TOOL] Auto-detected partner_id={resolved_partner_id}")
    
    # 2. Resolve name to UUID
    try:
        uuid.UUID(str(resolved_partner_id))
    except (ValueError, TypeError):
        # Could be a name
        name_res = supabase.table("partners").select("id").ilike("name", f"%{resolved_partner_id}%").execute()
        if not name_res.data:
            print(f"[DEBUG TOOL] Partner name not found: {resolved_partner_id}")
            return []
        resolved_partner_id = name_res.data[0]["id"]
        print(f"[DEBUG TOOL] Resolved name to ID={resolved_partner_id}")

    # 3. Fetch forms
    response = (
        supabase
        .table("partner_forms")
        .select("field_name, question_text, data_type, options, mapping_source, is_criterion, sort_order, maskking, step_id, partner_steps(step_name)")
        .eq("partner_id", resolved_partner_id)
        .order("sort_order")
        .execute()
    )
    
    fields = []
    for item in (response.data or []):
        step_info = item.pop("partner_steps", {})
        item["step_name"] = step_info.get("step_name") if step_info else None
        fields.append(item)

    print(f"[DEBUG TOOL] Returning {len(fields)} fields.")
    return fields
