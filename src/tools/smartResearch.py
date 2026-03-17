from src.tools.duckDuckGoSearch import duckDuckGoSearchTool
from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution
import asyncio

# ============================================================
# Smart Research Tool — DB-backed Knowledge Base
# ============================================================

@safe_execution(error_type="tool_error", default_return="Erro na pesquisa inteligente.")
async def smartResearchTool(query: str, partner_name: str = None) -> str:
    """
    Realiza uma pesquisa inteligente na Base de Conhecimento do Nubo Hub.

    Fluxo de decisão:
    1. Se partner_name é fornecido, busca documentos vinculados a esse parceiro.
    2. Se não, extrai keywords da query e busca documentos correspondentes.
    3. Faz download do conteúdo .md do Supabase Storage.
    4. Se nenhum documento é encontrado, faz fallback para busca na web.

    Args:
        query (str): A pergunta ou dúvida do usuário.
        partner_name (str, optional): Nome do parceiro para buscar documentos específicos.
            Ex: 'Fundação Estudar', 'Instituto Ponte', 'Programa Aurora'.

    Returns:
        str: Texto com o conteúdo relevante encontrado, prefixado com a fonte.
    """

    query_lower = query.lower().strip()

    # 1. Search for relevant documents in the database
    documents = _search_knowledge_documents(query_lower, partner_name)

    if documents:
        print(f"[SmartResearch] Encontrados {len(documents)} documento(s) na base de conhecimento.")

        # 2. Download and concatenate all matching documents from Storage
        combined_content = ""
        for doc in documents:
            content = _download_from_storage(doc.get("storage_path", ""))
            if content:
                title = doc.get("title", "Documento")
                combined_content += f"\n\n{'='*40}\nDOCUMENTO: {title}\n{'='*40}\n\n{content}"

        if combined_content:
            source_label = f"PARCEIRO ({partner_name.upper()})" if partner_name else "BASE DE CONHECIMENTO"
            return f"FONTE: {source_label} - FULL CONTEXT{combined_content}"

    print(f"[SmartResearch] Nenhum documento encontrado. partner_name='{partner_name}'. Fallback web.")

    # 3. Fallback to web search
    return await perform_web_fallback(query, "Nenhum documento encontrado na base de conhecimento.")


def _search_knowledge_documents(query_lower: str, partner_name: str = None) -> list:
    """Search for knowledge documents using the RPC search_knowledge_by_keyword."""
    try:
        params = {
            "p_keyword": None,
            "p_partner_id": None,
            "p_category_name": None,
        }

        if partner_name:
            # Try to find the partner_id by name
            partner_result = supabase.from_("partners").select("id").ilike("name", f"%{partner_name}%").limit(1).execute()
            if partner_result.data:
                params["p_partner_id"] = partner_result.data[0]["id"]
                print(f"[SmartResearch] Partner '{partner_name}' encontrado: {params['p_partner_id']}")
            else:
                # Fallback: search by keyword using the partner name
                params["p_keyword"] = partner_name.lower().strip()
        else:
            # Extract a keyword from the query for searching
            keyword = _extract_keyword_from_query(query_lower)
            if keyword:
                params["p_keyword"] = keyword
            else:
                # Try category-based search
                category = _detect_category_from_query(query_lower)
                if category:
                    params["p_category_name"] = category

        # Only search if we have at least one parameter
        if not any([params["p_keyword"], params["p_partner_id"], params["p_category_name"]]):
            return []

        result = supabase.rpc("search_knowledge_by_keyword", params).execute()

        if result.data:
            return result.data if isinstance(result.data, list) else []

    except Exception as e:
        print(f"[SmartResearch] Erro ao buscar documentos: {e}")

    return []


def _extract_keyword_from_query(query_lower: str) -> str:
    """Extract potential keyword from the query for document matching."""
    # Common educational keywords that might match document keywords
    keyword_candidates = [
        "prouni", "sisu", "cloudinha", "enem",
        "passaporte", "passport",
        "fundação estudar", "fundacao estudar",
        "instituto ponte", "programa aurora", "instituto sol",
    ]

    for kw in keyword_candidates:
        if kw in query_lower:
            return kw

    return None


def _detect_category_from_query(query_lower: str) -> str:
    """Detect which category the query might belong to."""
    category_map = {
        "prouni": ["prouni", "programa universidade para todos"],
        "sisu": ["sisu", "sistema de seleção unificada"],
        "cloudinha": ["cloudinha", "quem é você", "assistente"],
        "passport": ["passaporte", "fluxo", "onboarding", "próximo passo", "como funciona a plataforma"],
    }

    for category, keywords in category_map.items():
        for kw in keywords:
            if kw in query_lower:
                return category

    return None


def _download_from_storage(storage_path: str) -> str:
    """Download a .md file from Supabase Storage bucket 'knowledge-base'."""
    if not storage_path:
        return None

    try:
        response = supabase.storage.from_("knowledge-base").download(storage_path)
        if response:
            content = response.decode("utf-8")
            if content.strip():
                print(f"[SmartResearch] Download OK: {storage_path} ({len(content)} chars)")
                return content
    except Exception as e:
        print(f"[SmartResearch] Erro ao baixar {storage_path}: {e}")

    return None


async def perform_web_fallback(query: str, reason: str) -> str:
    """Fallback to web search when no local documents are found."""
    print(f"[SmartResearch] Iniciando busca Web. Motivo: {reason}")

    web_result = duckDuckGoSearchTool(query)

    print(f"[SmartResearch] Web Search concluído.")
    source_label = f"PESQUISA NA WEB ({reason})"

    return f"FONTE: {source_label}\n\n{web_result}"
