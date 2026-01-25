from src.tools.knowledgeSearch import knowledgeSearchTool
from src.tools.duckDuckGoSearch import duckDuckGoSearchTool
from src.tools.readRulesTool import readRulesTool
from src.agent.config import MODEL_CHAT
from src.lib.error_handler import safe_execution
import os
import asyncio

# Initialize client for verification (currently unused, kept for future use)
VERIFICATION_MODEL = MODEL_CHAT 

@safe_execution(error_type="tool_error", default_return="Erro na pesquisa inteligente.")
async def smartResearchTool(query: str, collection_name: str = "documents") -> str:
    """
    Realiza uma pesquisa inteligente:
    1. Verifica se a pergunta é sobre regras do Prouni ou Sisu e carrega o contesto completo (Full Context).
    2. Se não for (ou se falhar), faz fallback para Web.
    3. RAG (knowledgeSearch) está em STANDBY (desativado temporariamente).
    """
    
    query_lower = query.lower()
    
    # 1. Full Context Rules (Substitui RAG para Editais)
    target_program = None
    if "prouni" in query_lower:
        target_program = "prouni"
    elif "sisu" in query_lower:
        target_program = "sisu"
    elif "cloudinha" in query_lower or "você" in query_lower or "quem é" in query_lower:
        target_program = "cloudinha"
        
    if target_program:
        print(f"[SmartResearch] Detectado programa '{target_program}'. Usando Full Context Rules.")
        
        # readRulesTool is safe, returns error string or content
        rules_content = readRulesTool(program=target_program)
        
        # Se retornou conteúdo válido (não erro), retorna direto
        # Note: 'readRulesTool' default return on error is "Erro ao ler as regras."
        # It also returns other error strings if dirs don't exist.
        if "Erro" not in rules_content and "Nenhum conteúdo" not in rules_content:
            return f"FONTE: DOCUMENTAÇÃO OFICIAL ({target_program.upper()}) - FULL CONTEXT\n\n{rules_content}"
        else:
            print(f"[SmartResearch] readRulesTool falhou ou não retornou dados: {rules_content}")

    # 2. RAG (Em Standby - Desativado)
    # 3. Fallback para Web (Se não for regra específica ou se falhar)
    return await perform_web_fallback(query, "Full Context não aplicável ou RAG em standby.")

async def perform_web_fallback(query: str, reason: str) -> str:
    print(f"[SmartResearch] Iniciando busca Web. Motivo: {reason}")
    # duckDuckGoSearchTool is safe, returns string (result or error message)
    # If duckDuckGoSearchTool raises an exception (unexpected), smartResearchTool's safe_execution will catch it.
    
    web_result = duckDuckGoSearchTool(query)
    
    # Check if web_result is the default error string from duckDuckGoSearchTool
    # The default return is "Desculpe, não consegui realizar a busca na internet no momento."
    if web_result and "Desculpe, não consegui" in web_result:
         # Logged by inner tool, but we can return it.
         pass

    print(f"[SmartResearch] Web Search concluído.")
    return f"FONTE: PESQUISA NA WEB ({reason})\n\n{web_result}"
