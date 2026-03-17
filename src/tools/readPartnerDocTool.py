from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution


@safe_execution(error_type="tool_error", default_return="Erro ao ler documento do parceiro.")
def readPartnerDocTool(partner_name: str) -> str:
    """
    Reads the full text content of a partner's knowledge document from Supabase Storage.

    Searches the knowledge_documents table for documents linked to the partner,
    then downloads the .md file from the 'knowledge-base' Storage bucket.

    Args:
        partner_name (str): The name of the partner program
            (e.g. 'Fundação Estudar', 'Instituto Ponte', 'Programa Aurora').

    Returns:
        str: The full text content of the partner's document.
    """
    if not partner_name:
        return "Erro: O argumento 'partner_name' é obrigatório."

    name_lower = partner_name.lower().strip()

    # 1. Find partner by name
    partner_result = (
        supabase.from_("partners")
        .select("id, name")
        .ilike("name", f"%{name_lower}%")
        .limit(1)
        .execute()
    )

    if not partner_result.data:
        return f"Parceiro '{partner_name}' não encontrado na base de dados."

    partner_id = partner_result.data[0]["id"]
    partner_display_name = partner_result.data[0]["name"]

    # 2. Search knowledge documents linked to this partner
    result = supabase.rpc("search_knowledge_by_keyword", {
        "p_keyword": None,
        "p_partner_id": partner_id,
        "p_category_name": None,
    }).execute()

    if not result.data:
        return f"Nenhum documento encontrado para o parceiro '{partner_display_name}' na base de conhecimento."

    # 3. Download and combine all partner documents
    full_content = ""
    for doc in result.data:
        storage_path = doc.get("storage_path", "")
        if not storage_path:
            continue

        try:
            response = supabase.storage.from_("knowledge-base").download(storage_path)
            if response:
                content = response.decode("utf-8")
                title = doc.get("title", "Documento")
                full_content += f"\n\n{'='*40}\nCONTEÚDO DO DOCUMENTO: {title}\n{'='*40}\n\n{content}"
        except Exception as e:
            print(f"[ReadPartnerDoc] Erro ao baixar {storage_path}: {e}")

    if not full_content.strip():
        return f"Aviso: Os documentos do parceiro '{partner_display_name}' não contêm texto."

    return full_content
