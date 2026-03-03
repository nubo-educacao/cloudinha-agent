from src.lib.error_handler import safe_execution
import json
from src.agent.agent import supabase_client

@safe_execution(error_type="rewind_workflow_error", default_return="Erro ao tentar retroceder fluxo.")
def rewindWorkflowStatusTool(user_id: str) -> str:
    """
    Volta uma fase no fluxo do usuário (passport_phase) caso ele deseje reiniciar, 
    corrigir alguma informação anterior ou reportar erro.
    
    Args:
        user_id: string. O ID do usuário (geralmente passado por USER_ID_CONTEXT).
    """
    try:
        # Fetch current profile
        profile_res = supabase_client.table("user_profiles").select("passport_phase").eq("id", user_id).execute()
        if not profile_res.data:
            return "Erro: Perfil não encontrado."
            
        current_phase = profile_res.data[0].get("passport_phase")
        if not current_phase:
            return "Nenhuma fase atual definida."
            
        # Determine previous phase mapping 
        # State rewind: CONCLUDED → EVALUATE → PROGRAM_MATCH → ASK_DEPENDENT
        if current_phase == "CONCLUDED":
            new_phase = "EVALUATE"
        elif current_phase == "EVALUATE":
            new_phase = "PROGRAM_MATCH"
        elif current_phase == "PROGRAM_MATCH":
            new_phase = "ASK_DEPENDENT" 
        elif current_phase == "DEPENDENT_ONBOARDING":
            new_phase = "ASK_DEPENDENT"
        else:
            return f"Não é possível retroceder a partir da fase atual: {current_phase}."

        # Update the database
        upd = supabase_client.table("user_profiles").update({"passport_phase": new_phase}).eq("id", user_id).execute()
        
        return f"Sucesso: Fluxo retornado para a fase {new_phase}. Peça ao usuário para recomeçar o preenchimento daqui."
    except Exception as e:
        return f"Erro ao tentar retroceder fluxo: {str(e)}"
