from src.lib.error_handler import safe_execution
import json
from src.agent.agent import supabase_client

@safe_execution(error_type="start_student_application_error", default_return="Erro ao iniciar aplicação.")
def startStudentApplicationTool(user_id: str, partner_id: str) -> str:
    """
    Inicia uma nova aplicação para um programa parceiro e pré-preenche os dados com base no mapping_source definido no formulário.
    É usada quando o usuário escolhe um programa parceiro para se aplicar.
    
    Args:
        user_id: string. O ID do usuário (geralmente passado por USER_ID_CONTEXT).
        partner_id: string. O ID do parceiro para o qual será feita a inscrição.
    """
    try:
        # 1. Fetch partner form mapping source
        form_res = supabase_client.table("partner_forms").select("mapping_source").eq("partner_id", partner_id).execute()
        if not form_res.data:
            return f"Nenhum formulário ou mapeamento encontrado para o partner_id {partner_id}."
            
        # mapping_source could be something like "user_profiles.full_name", etc.
        # Very basic extraction. If it's a full JSON object mapping, we will capture it below.
        mapping_source_list = [f.get("mapping_source") for f in form_res.data if f.get("mapping_source")]
        
        # 2. Fetch User Profile & Preferences
        profile_res = supabase_client.table("user_profiles").select("*").eq("id", user_id).execute()
        pref_res = supabase_client.table("user_preferences").select("*").eq("user_id", user_id).execute()
        
        profile_data = profile_res.data[0] if profile_res.data else {}
        pref_data = pref_res.data[0] if pref_res.data else {}
        
        # 3. Build Dynamic Answers (Pre-fill)
        answers = {}
        for mapping in mapping_source_list:
            if not mapping: continue
            
            # Simple dot-notation parsing (e.g. 'user_profiles.full_name')
            parts = mapping.split(".")
            if len(parts) == 2:
                source_table, field_name = parts
                if source_table == "user_profiles" and field_name in profile_data:
                    answers[mapping] = profile_data[field_name]
                elif source_table == "user_preferences" and field_name in pref_data:
                    answers[mapping] = pref_data[field_name]
        
        # 4. Insert into student_applications
        payload = {
            "user_id": user_id,
            "partner_id": partner_id,
            "answers": answers,
            "status": "DRAFT" # Starting application
        }
        
        ins_res = supabase_client.table("student_applications").insert(payload).execute()
        
        # 5. Advance passport_phase to EVALUATE (doc items 17-18)
        supabase_client.table("user_profiles").update({"passport_phase": "EVALUATE"}).eq("id", user_id).execute()
        
        return f"Aplicação iniciada com sucesso para o parceiro {partner_id}. Fase avançada para EVALUATE. Respostas pré-preenchidas: {list(answers.keys())}."
    except Exception as e:
        return f"Erro ao iniciar aplicação: {str(e)}"
