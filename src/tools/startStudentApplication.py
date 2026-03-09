from src.lib.error_handler import safe_execution
import json
from src.agent.agent import supabase_client

@safe_execution(error_type="start_student_application_error", default_return="Erro ao iniciar aplicação.")
def startStudentApplicationTool(user_id: str, partner_id: str) -> str:
    """
    Inicia uma nova aplicação para um programa parceiro e pré-preenche os dados com base no mapping_source definido no formulário.
    É usada quando o usuário escolhe um programa parceiro para se aplicar.
    Só permite iniciar 1 aplicação por parceiro a cada 6 meses.
    
    Args:
        user_id: string. O ID do usuário (geralmente passado por USER_ID_CONTEXT).
        partner_id: string. O ID do parceiro (UUID) ou o NOME do parceiro para o qual será feita a inscrição.
    """
    import uuid
    from datetime import datetime, timedelta
    
    # 1. Resolve partner ID if a name was provided
    resolved_partner_id = partner_id
    try:
        uuid.UUID(partner_id)
    except ValueError:
        # It's not a UUID, so treat it as a name
        name_res = supabase_client.table("partners").select("id").ilike("name", f"%{partner_id}%").execute()
        if not name_res.data:
            return f"Nenhum parceiro encontrado com o nome fornecido: {partner_id}."
        resolved_partner_id = name_res.data[0]["id"]

    # 2. Determine who is applying (self or dependent)
    # Fetch parent profile to check what the active target is
    parent_res = supabase_client.table("user_profiles").select("active_application_target_id").eq("id", user_id).execute()
    student_id = user_id
    if parent_res.data and parent_res.data[0].get("active_application_target_id"):
        student_id = parent_res.data[0]["active_application_target_id"]

    # 3. Check for existing application within 6 months FOR THE STUDENT
    six_months_ago = (datetime.now() - timedelta(days=180)).isoformat()
    existing_app_res = supabase_client.table("student_applications") \
        .select("id, status, created_at") \
        .eq("user_id", student_id) \
        .eq("partner_id", resolved_partner_id) \
        .gte("created_at", six_months_ago) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if existing_app_res.data:
        existing_app = existing_app_res.data[0]
        status = existing_app.get("status")
        
        # Bump updated_at so the frontend picks this application as the most recent
        supabase_client.table("student_applications").update({"updated_at": datetime.now().isoformat()}).eq("id", existing_app["id"]).execute()
        
        # Advance passport_phase to correct state anyway
        next_phase = "CONCLUDED" if status == "SUBMITTED" else "EVALUATE"
        supabase_client.table("user_profiles").update({"passport_phase": next_phase}).eq("id", user_id).execute()
        
        if status == "SUBMITTED":
            return "Você já enviou uma candidatura para este programa nos últimos 6 meses. Como ela já foi enviada, estou te levando para a tela de conclusão para você ver o resultado."
        else:
            return "Você já tem uma candidatura em andamento para este programa. Estou te levando de volta para o formulário para você continuar de onde parou."

    # 4. Fetch partner form mapping source and field names
    form_res = supabase_client.table("partner_forms").select("field_name, mapping_source").eq("partner_id", resolved_partner_id).execute()
    if not form_res.data:
        return f"Nenhum formulário ou mapeamento encontrado para o partner_id {resolved_partner_id}."
        
    mapping_data = [{"field_name": f.get("field_name"), "mapping_source": f.get("mapping_source")} 
                  for f in form_res.data if f.get("mapping_source")]
    
    # 5. Fetch User Profile & Preferences for data pre-fill
    profile_res = supabase_client.table("user_profiles").select("*").eq("id", student_id).execute()
    pref_res = supabase_client.table("user_preferences").select("*").eq("user_id", user_id).execute()
    
    profile_data = profile_res.data[0] if profile_res.data else {}
    pref_data = pref_res.data[0] if pref_res.data else {}
    
    # 6. Build Dynamic Answers (Pre-fill)
    answers = {}
    for item in mapping_data:
        mapping = item["mapping_source"]
        field_name_key = item["field_name"]
        if not mapping or not field_name_key: continue
        
        parts = mapping.split(".")
        if len(parts) == 2:
            source_table, field_name = parts
            value = None
            if source_table == "user_profiles" and field_name in profile_data:
                value = profile_data[field_name]
            elif source_table == "user_preferences" and field_name in pref_data:
                value = pref_data[field_name]
            
            if value is not None and value != "":
                answers[field_name_key] = value
    
    # 7. Insert into student_applications
    payload = {
        "user_id": student_id,
        "partner_id": resolved_partner_id,
        "answers": answers,
        "status": "DRAFT"
    }
    
    supabase_client.table("student_applications").insert(payload).execute()
    
    # 8. Advance passport_phase to EVALUATE
    supabase_client.table("user_profiles").update({"passport_phase": "EVALUATE"}).eq("id", user_id).execute()
    
    # Build human-friendly labels for pre-filled fields
    FIELD_LABELS = {
        "user_profiles.full_name": "Nome Completo",
        "user_profiles.age": "Idade",
        "user_profiles.education": "Escolaridade",
        "user_profiles.registered_city_name": "Cidade",
        "user_profiles.registered_state": "Estado",
        "user_profiles.family_income": "Renda Familiar",
        "user_profiles.school_type": "Tipo de Escola",
    }
    prefilled_labels = [FIELD_LABELS.get(k, k.split(".")[-1]) for k in answers.keys()]
    prefilled_str = ", ".join(prefilled_labels) if prefilled_labels else "nenhum"
    
    return f"Aplicação iniciada com sucesso. Fase avançada para EVALUATE. O formulário do programa está aberto na tela do estudante. Campos pré-preenchidos automaticamente: {prefilled_str}."
