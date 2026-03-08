from src.tools.knowledgeSearch import knowledgeSearchTool
from src.tools.duckDuckGoSearch import duckDuckGoSearchTool
from src.tools.readRulesTool import readRulesTool
from src.tools.readPartnerDocTool import readPartnerDocTool
# from src.agent.config import MODEL_CHAT # Circular dependency fix
from src.lib.error_handler import safe_execution
import os
import asyncio

# Path to passport workflow documentation (for target_program='passport')
PASSPORT_KNOWLEDGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "documents", "passei_workflow_doc.md"
)

# Path to general partner knowledge base (injected alongside every partner PDF)
PARTNER_GENERAL_KNOWLEDGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "documents", "partners", "Base de conhecimento geral.md"
)

# Initialize client for verification (currently unused, kept for future use)
# VERIFICATION_MODEL = MODEL_CHAT # Currently unused

@safe_execution(error_type="tool_error", default_return="Erro na pesquisa inteligente.")
async def smartResearchTool(query: str, program: str = None, partner_name: str = None, collection_name: str = "documents") -> str:
    """
    Realiza uma pesquisa inteligente sobre programas educacionais.
    
    Fluxo de decisão:
    1. Se target_program é fornecido, usa esse valor diretamente.
    2. Se não, detecta automaticamente pelo conteúdo da query.
    3. Carrega o contexto completo da fonte adequada.
    4. Se nenhuma fonte local é encontrada, faz fallback para busca na web.
    
    Args:
        query (str): A pergunta ou dúvida do usuário.
        program (str, optional): O programa alvo para buscar informações. Valores permitidos EXATOS:
            - 'passport': Dúvidas gerais sobre o fluxo do passaporte, como funciona a plataforma.
            - 'programs': Dúvidas sobre programas educacionais em geral ou sobre um parceiro específico (requer partner_name).
            - 'prouni': Dúvidas sobre o Prouni.
            - 'sisu': Dúvidas sobre o Sisu.
            - 'cloudinha': Dúvidas sobre a Cloudinha.
        partner_name (str, optional): Nome do parceiro quando program='programs'.
            Ex: 'Fundação Estudar', 'Instituto Ponte', 'Programa Aurora', 'Instituto Sol'.
            Ex: 'Fundação Estudar', 'Instituto Ponte', 'Programa Aurora'.
        collection_name (str): Nome da coleção RAG (em standby). Padrão: 'documents'.
    
    Returns:
        str: Texto com o conteúdo relevante encontrado, prefixado com a fonte.
    """
    
    query_lower = query.lower()
    
    # 1. Determine program (explicit or heuristic)
    if not program:
        program = _detect_target_program(query_lower)
    else:
        program = program.lower().strip()
    
    if program:
        print(f"[SmartResearch] program='{program}'. partner_name='{partner_name}'")
    
    # 2. Handle 'passport' — workflow documentation (passei_workflow_doc.md)
    if program == "passport":
        content = _read_file_content(PASSPORT_KNOWLEDGE_PATH)
        if content:
            return f"FONTE: DOCUMENTAÇÃO DO PASSAPORTE - FULL CONTEXT\n\n{content}"
        else:
            print("[SmartResearch] Falha ao ler passei_workflow_doc.md. Fallback web.")
    
    # 3. Handle 'programs' — general knowledge + specific partner PDF
    if program == "programs":
        # Always inject general partner knowledge base
        general_content = _read_file_content(PARTNER_GENERAL_KNOWLEDGE_PATH)
        general_section = ""
        if general_content:
            general_section = f"=== BASE DE CONHECIMENTO GERAL ===\n\n{general_content}\n\n"
        
        # Try to get partner-specific PDF
        if not partner_name:
            partner_name = _detect_partner_from_query(query_lower)
        
        partner_section = ""
        if partner_name:
            partner_content = readPartnerDocTool(partner_name=partner_name)
            if partner_content and "Erro" not in partner_content and "não encontrado" not in partner_content:
                partner_section = f"=== DOCUMENTAÇÃO ESPECÍFICA: {partner_name.upper()} ===\n\n{partner_content}"
            else:
                print(f"[SmartResearch] readPartnerDocTool falhou: {partner_content}")
        
        if general_section or partner_section:
            combined = general_section + partner_section
            source_label = f"PARCEIRO ({partner_name.upper()})" if partner_name else "PROGRAMAS EDUCACIONAIS"
            return f"FONTE: {source_label} - FULL CONTEXT\n\n{combined}"
        else:
            print("[SmartResearch] Nenhum conteúdo encontrado para programs.")
    
    # 4. Handle prouni/sisu/cloudinha — existing behavior via readRulesTool
    if program in ("prouni", "sisu", "cloudinha"):
        print(f"[SmartResearch] Detectado programa '{program}'. Usando Full Context Rules.")
        
        rules_content = readRulesTool(program=program)
        
        if "Erro" not in rules_content and "Nenhum conteúdo" not in rules_content:
            return f"FONTE: DOCUMENTAÇÃO OFICIAL ({program.upper()}) - FULL CONTEXT\n\n{rules_content}"
        else:
            print(f"[SmartResearch] readRulesTool falhou ou não retornou dados: {rules_content}")

    # 5. RAG (Em Standby - Desativado)
    # 6. Fallback para Web
    return await perform_web_fallback(query, "Full Context não aplicável ou RAG em standby.", program=program)


def _detect_target_program(query_lower: str) -> str:
    """Heuristic detection of target_program from query keywords."""
    # Check for specific partner names first (programs)
    partner_keywords = [
        "fundação estudar", "fundacao estudar",
        "instituto ponte",
        "programa aurora", "instituto sol"
    ]
    for kw in partner_keywords:
        if kw in query_lower:
            return "programs"
    
    # Check for prouni/sisu/cloudinha
    if "prouni" in query_lower:
        return "prouni"
    if "sisu" in query_lower:
        return "sisu"
    if "cloudinha" in query_lower or "quem é você" in query_lower:
        return "cloudinha"
    
    # Check for generic passport/educational program keywords
    passport_keywords = [
        "programa educacional", "programas educacionais",
        "apoio educacional", "passaporte",
        "programa de apoio", "programas de apoio",
        "programa parceiro", "programas parceiros",
        "o que são programas", "como funciona o programa",
        "o que é um programa",
        # Process/flow/form questions
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


def _detect_partner_from_query(query_lower: str) -> str:
    """Try to extract partner name from query text."""
    if "fundação estudar" in query_lower or "fundacao estudar" in query_lower:
        return "Fundação Estudar"
    if "instituto ponte" in query_lower:
        return "Instituto Ponte"
    if "programa aurora" in query_lower or "instituto sol" in query_lower:
        return "Programa Aurora"
    return None


def _read_file_content(file_path: str) -> str:
    """Read a text file and return its content, or None on failure."""
    if not os.path.exists(file_path):
        print(f"[SmartResearch] Arquivo não encontrado: {file_path}")
        return None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            return content
    except Exception as e:
        print(f"[SmartResearch] Erro ao ler {file_path}: {e}")
    
    return None


async def perform_web_fallback(query: str, reason: str, program: str = None) -> str:
    print(f"[SmartResearch] Iniciando busca Web. Motivo: {reason}")
    
    # Se o programa for educational programs, use partners.link como referência no DDG
    site = None
    if program == "programs":
        site = "partners.link"
        print(f"[SmartResearch] Usando site='{site}' como referência.")
    
    web_result = duckDuckGoSearchTool(query, site=site)
    
    if web_result and "Desculpe, não consegui" in web_result:
         pass

    print(f"[SmartResearch] Web Search concluído.")
    source_label = f"PESQUISA NA WEB ({reason})"
    if site:
        source_label += f" - REF: {site}"
        
    return f"FONTE: {source_label}\n\n{web_result}"
