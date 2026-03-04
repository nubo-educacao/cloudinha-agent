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

    # Fetch eligibility_results from user_profiles
    res = supabase.table("user_profiles") \
        .select("eligibility_results") \
        .eq("id", user_id) \
        .execute()

    if not res.data or len(res.data) == 0:
        return json.dumps({"error": "Perfil não encontrado.", "results": []})

    eligibility = res.data[0].get("eligibility_results")

    if not eligibility or (isinstance(eligibility, list) and len(eligibility) == 0):
        return json.dumps({
            "message": "Os resultados de elegibilidade ainda não foram calculados pelo frontend. Os cards dos parceiros estão na tela do usuário. Pergunte ao estudante qual programa ele deseja e use o nome do parceiro para iniciar a aplicação.",
            "results": []
        })

    return json.dumps({
        "message": f"Encontrados {len(eligibility)} parceiros avaliados.",
        "results": eligibility
    })
