from src.lib.error_handler import safe_execution
from src.lib.supabase import supabase


@safe_execution(error_type="get_eligibility_results_error", default_return="Erro ao buscar resultados de elegibilidade.")
def getEligibilityResultsTool(user_id: str) -> str:
    """
    Busca os resultados de elegibilidade (eligibility_results) salvos no perfil do usuário.
    Retorna a lista de parceiros com seus critérios atendidos e não atendidos.
    Use esta ferramenta na fase PROGRAM_MATCH para saber quais parceiros o estudante tem match.

    Args:
        user_id: string. O ID do usuário (geralmente passado por USER_ID_CONTEXT).
    """
    import json

    # Fetch eligibility_results and active target from user_profiles
    res = supabase.table("user_profiles") \
        .select("eligibility_results, active_application_target_id") \
        .eq("id", user_id) \
        .execute()

    if not res.data or len(res.data) == 0:
        return json.dumps({"error": "Perfil não encontrado.", "results": []})

    eligibility = res.data[0].get("eligibility_results")
    active_target = res.data[0].get("active_application_target_id")
    
    # Determine who the target is
    target_type = "dependente" if active_target and active_target != user_id else "estudante"

    if not eligibility or (isinstance(eligibility, list) and len(eligibility) == 0):
        return json.dumps({
            "message": f"Os resultados de elegibilidade para o {target_type} ainda não foram calculados pelo frontend. Os cards dos parceiros estão na tela do usuário. Pergunte ao estudante qual programa ele deseja e use o nome do parceiro para iniciar a aplicação.",
            "target": target_type,
            "results": []
        })

    # Fetch external_redirect_config for the partners found in eligibility
    partner_ids = [item.get("partner_id") for item in eligibility if item.get("partner_id")]
    if partner_ids:
        partners_res = supabase.table("partners") \
            .select("id, external_redirect_config") \
            .in_("id", partner_ids) \
            .execute()
        
        if partners_res.data:
            redirect_map = {p["id"]: p.get("external_redirect_config") for p in partners_res.data}
            for item in eligibility:
                pid = item.get("partner_id")
                if pid in redirect_map:
                    item["external_redirect_config"] = redirect_map[pid]

    return json.dumps({
        "message": f"Encontrados {len(eligibility)} parceiros avaliados para o {target_type}.",
        "target": target_type,
        "results": eligibility
    })
