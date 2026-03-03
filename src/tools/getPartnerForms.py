from typing import Dict, List, Any
from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution


@safe_execution(error_type="tool_error", default_return=[])
def getPartnerFormsTool(partner_id: str) -> List[Dict[str, Any]]:
    """
    Retorna os campos e regras do formulário de um parceiro específico.
    
    Usado pelo Reasoning Agent para entender a estrutura do formulário
    quando o usuário pergunta sobre campos específicos.
    
    Args:
        partner_id (str): UUID do parceiro.
    
    Returns:
        list: Lista de campos do formulário com question_text, data_type, options, etc.
    """
    response = (
        supabase
        .table("partner_forms")
        .select("field_name, question_text, data_type, options, mapping_source, is_criterion, sort_order")
        .eq("partner_id", partner_id)
        .order("sort_order")
        .execute()
    )
    
    fields = response.data or []
    print(f"[DEBUG TOOL] getPartnerFormsTool found {len(fields)} fields for partner_id={partner_id}")
    return fields
