from src.tools.knowledgeSearch import knowledgeSearchTool
from src.tools.duckDuckGoSearch import duckDuckGoSearchTool
from src.tools.getKnowledgeContent import getKnowledgeContentTool
from src.lib.error_handler import safe_execution

_KB_FALLBACK = "Não encontrei informações na base de conhecimento."


@safe_execution(error_type="tool_error", default_return="Erro na pesquisa inteligente.")
async def smartResearchTool(query: str, program: str = None, partner_name: str = None, collection_name: str = "documents") -> str:
    """
    Realiza uma pesquisa inteligente sobre programas educacionais.

    Fluxo de decisão:
    1. Se target_program é fornecido, usa esse valor diretamente.
    2. Se não, detecta automaticamente pelo conteúdo da query.
    3. Busca o conteúdo na base de conhecimento do banco (Supabase).
    4. Se nenhum conteúdo for encontrado, faz fallback para busca na web.

    Args:
        query (str): A pergunta ou dúvida do usuário.
        program (str, optional): O programa alvo para buscar informações. Valores permitidos EXATOS:
            - 'passport': Dúvidas gerais sobre o fluxo do passaporte, como funciona a plataforma.
            - 'programs': Dúvidas sobre programas educacionais em geral ou sobre um parceiro específico (requer partner_name).
            - 'prouni': Dúvidas sobre o Prouni.
            - 'sisu': Dúvidas sobre o Sisu.
            - 'cloudinha': Dúvidas sobre a Cloudinha.
        partner_name (str, optional): Nome do parceiro quando program='programs'.
            Usar o nome exato como retornado por getEligibilityResultsTool.
            Ex: 'Bolsa Integral do Insper', 'Fundação Behring'.
        collection_name (str): Nome da coleção RAG (em standby). Padrão: 'documents'.

    Returns:
        str: Texto com o conteúdo relevante encontrado, prefixado com a fonte.
    """

    query_lower = query.lower()

    # 1. Determine program (explicit or heuristic)
    if not program:
        program = _detect_target_program(query_lower, partner_name=partner_name)
    else:
        program = program.lower().strip()

    print(f"[SmartResearch] query='{query}'. program='{program}'. partner_name='{partner_name}'")

    # 2. Handle 'passport' — workflow documentation from DB
    if program == "passport":
        content = getKnowledgeContentTool(category="passport")
        if content and _KB_FALLBACK not in content:
            return f"FONTE: DOCUMENTAÇÃO DO PASSAPORTE - FULL CONTEXT\n\n{content}"
        else:
            print("[SmartResearch] Nenhum conteúdo passport no banco. Fallback web.")

    # 3. Handle 'programs' — general knowledge + specific partner from DB
    if program == "programs":
        general_content = getKnowledgeContentTool(category="general")
        general_section = ""
        if general_content and _KB_FALLBACK not in general_content:
            general_section = f"=== BASE DE CONHECIMENTO GERAL ===\n\n{general_content}\n\n"

        partner_section = ""
        if partner_name:
            partner_content = getKnowledgeContentTool(partner_name=partner_name)
            if partner_content and _KB_FALLBACK not in partner_content:
                partner_section = f"=== DOCUMENTAÇÃO ESPECÍFICA: {partner_name.upper()} ===\n\n{partner_content}"
            else:
                print(f"[SmartResearch] getKnowledgeContentTool(partner_name='{partner_name}') sem dados.")

        if general_section or partner_section:
            combined = general_section + partner_section
            source_label = f"PARCEIRO ({partner_name.upper()})" if partner_name else "PROGRAMAS EDUCACIONAIS"
            return f"FONTE: {source_label} - FULL CONTEXT\n\n{combined}"
        else:
            print("[SmartResearch] Nenhum conteúdo encontrado para programs.")

    # 4. Handle prouni/sisu/cloudinha — from DB
    if program in ("prouni", "sisu", "cloudinha"):
        print(f"[SmartResearch] Buscando '{program}' no banco.")
        kb_content = getKnowledgeContentTool(category=program)

        if kb_content and _KB_FALLBACK not in kb_content:
            return f"FONTE: DOCUMENTAÇÃO OFICIAL ({program.upper()}) - FULL CONTEXT\n\n{kb_content}"
        else:
            print(f"[SmartResearch] Nenhum conteúdo para '{program}' no banco.")

    # 5. RAG (Em Standby - Desativado)
    # 6. Fallback para Web
    reason = f"Full Context não disponível no banco para program={program}"
    return await perform_web_fallback(query, reason, program=program)


def _detect_target_program(query_lower: str, partner_name: str = None) -> str:
    """Heuristic detection of target_program from query keywords."""
    if partner_name:
        return "programs"

    if "prouni" in query_lower:
        return "prouni"
    if "sisu" in query_lower:
        return "sisu"
    if "cloudinha" in query_lower or "quem é você" in query_lower:
        return "cloudinha"

    passport_keywords = [
        "programa educacional", "programas educacionais",
        "apoio educacional", "passaporte",
        "programa de apoio", "programas de apoio",
        "programa parceiro", "programas parceiros",
        "o que são programas", "como funciona o programa",
        "o que é um programa",
        "formulário", "formulario",
        "onboarding", "etapa", "etapas",
        "próximo passo", "proximo passo",
        "o que acontece depois", "qual o próximo",
        "fluxo", "processo de aplicação",
        "processo seletivo", "como funciona",
        "passo a passo", "como faço para",
        "preencher", "preenchendo",
    ]
    for kw in passport_keywords:
        if kw in query_lower:
            return "passport"

    return None


async def perform_web_fallback(query: str, reason: str, program: str = None) -> str:
    print(f"[SmartResearch] Iniciando busca Web. Motivo: {reason}")

    site = None
    if program == "programs":
        site = "partners.link"
        print(f"[SmartResearch] Usando site='{site}' como referência.")

    web_result = duckDuckGoSearchTool(query, site=site)

    print(f"[SmartResearch] Web Search concluído.")
    source_label = f"PESQUISA NA WEB ({reason})"
    if site:
        source_label += f" - REF: {site}"

    return f"FONTE: {source_label}\n\n{web_result}"
