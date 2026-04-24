from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution

_FALLBACK = "Não encontrei informações na base de conhecimento."


@safe_execution(error_type="tool_error", default_return=_FALLBACK)
def getKnowledgeContentTool(
    category: str = None,
    partner_name: str = None,
) -> str:
    """
    Busca e retorna conteúdo da base de conhecimento do Supabase Storage.

    Args:
        category (str, optional): Categoria do documento.
            Valores: 'partner', 'prouni', 'sisu', 'passport', 'general', 'cloudinha'.
        partner_name (str, optional): Nome do parceiro para busca fuzzy
            (ex: 'Insper', 'Behring', 'Bolsa Integral do Insper').
            Usa ILIKE no banco — correspondência parcial por substring.

    Returns:
        str: Conteúdo Markdown dos documentos encontrados, concatenados com separadores.
             Retorna mensagem de fallback se nenhum documento for encontrado.
    """
    if not category and not partner_name:
        return _FALLBACK

    docs = _fetch_documents(category=category, partner_name=partner_name)

    if not docs:
        return _FALLBACK

    parts = []
    seen_paths = set()
    for doc in docs:
        storage_path = doc["storage_path"]
        if storage_path in seen_paths:
            continue
        seen_paths.add(storage_path)
        
        title = doc["title"]
        try:
            raw = supabase.storage.from_("knowledge-base").download(storage_path)
            # Use 'replace' to avoid UnicodeDecodeError if there's any corruption
            content = raw.decode("utf-8", errors="replace")
            parts.append(f"=== {title} ===\n\n{content}")
        except Exception as e:
            print(f"[getKnowledgeContent] Erro ao baixar '{storage_path}': {e}")

    if not parts:
        return _FALLBACK

    return "\n\n---\n\n".join(parts)


def _fetch_documents(category: str = None, partner_name: str = None) -> list:
    """Query knowledge_documents filtered by category name or partner name."""
    base_query = (
        supabase.table("knowledge_documents")
        .select("title, storage_path")
        .eq("is_active", True)
    )

    if partner_name:
        query = supabase.table("partners").select("id")
        
        # Tokenize partner_name to allow flexible matches (e.g. "Bolsa do Insper" matches "Bolsa Integral do Insper")
        stop_words = {"das", "dos", "para", "com", "por", "que"}
        keywords = [w for w in partner_name.split() if len(w) > 2 and w.lower() not in stop_words]
        
        if not keywords:
            keywords = [partner_name.strip()]
            
        for kw in keywords:
            query = query.ilike("name", f"%{kw}%")
            
        partners_resp = query.execute()
        if not partners_resp.data:
            return []
        partner_ids = [p["id"] for p in partners_resp.data]
        if len(partner_ids) == 1:
            docs_resp = base_query.eq("partner_id", partner_ids[0]).execute()
        else:
            docs_resp = base_query.in_("partner_id", partner_ids).execute()
        return docs_resp.data or []

    if category:
        # Use ilike for category name to be case-insensitive
        cat_resp = (
            supabase.table("knowledge_categories")
            .select("id")
            .ilike("name", category)
            .execute()
        )
        if not cat_resp.data:
            return []
        category_id = cat_resp.data[0]["id"]
        docs_resp = base_query.eq("category_id", category_id).execute()
        return docs_resp.data or []

    return []
