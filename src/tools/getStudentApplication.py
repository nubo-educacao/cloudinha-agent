from typing import Dict, Any, Optional
from src.lib.error_handler import safe_execution
from src.agent.agent import supabase_client

@safe_execution(error_type="get_student_application_error", default_return={"status": "error", "message": "Failed to fetch student application"})
def getStudentApplicationTool(user_id: str, partner_id: str = None) -> Dict[str, Any]:
    """
    Fetches the progress of a student's application.
    If partner_id is omitted, auto-detects the latest DRAFT application for the given user_id.
    """
    import uuid
    print(f"[DEBUG TOOL] getStudentApplicationTool called with user_id={user_id}, partner_id={partner_id}")
    
    resolved_partner_id = partner_id
    
    # 1. Resolve partner_id if missing (Auto-detection)
    if not resolved_partner_id:
        if not user_id:
            return {"status": "error", "message": "Missing user_id for auto-detection."}
            
        active_app = (
            supabase_client
            .table("student_applications")
            .select("partner_id")
            .eq("user_id", user_id)
            .eq("status", "DRAFT")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if not active_app.data:
            return {"status": "error", "message": "No active application found."}
        resolved_partner_id = active_app.data[0]["partner_id"]
        print(f"[DEBUG TOOL] Auto-detected partner_id={resolved_partner_id}")

    # 2. Resolve name to UUID if needed
    try:
        uuid.UUID(str(resolved_partner_id))
    except (ValueError, TypeError):
        name_res = supabase_client.table("partners").select("id").ilike("name", f"%{resolved_partner_id}%").execute()
        if not name_res.data:
            return {"status": "error", "message": f"Parceiro não encontrado: {resolved_partner_id}"}
        resolved_partner_id = name_res.data[0]["id"]

    try:
        res = supabase_client.table("student_applications") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("partner_id", resolved_partner_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if not res.data:
            return {"status": "error", "message": "No application found for this partner."}
            
        return res.data[0]
    except Exception as e:
        return {"status": "error", "message": str(e)}
