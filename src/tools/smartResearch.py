from src.tools.knowledgeSearch import knowledgeSearchTool
from src.tools.duckDuckGoSearch import duckDuckGoSearchTool
from src.tools.readRulesTool import readRulesTool
from src.agent.config import MODEL_CHAT
from google.genai import Client
import os
import logging
import asyncio

logger = logging.getLogger("cloudinha-server")

# Initialize client for verification (currently unused, kept for future use)
VERIFICATION_MODEL = MODEL_CHAT 

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
        # readRulesTool is now a plain function (decorator removed to fix LlmAgent type error)
        try:
            # invoccation changed from .invoke({"program": ...}) to direct call
            rules_content = readRulesTool(program=target_program)
        except Exception as tool_err:
            print(f"[SmartResearch] Erro ao executar readRulesTool: {tool_err}")
            rules_content = str(tool_err)
        
        # Se retornou conteúdo válido (não erro), retorna direto
        if "Erro" not in rules_content and "Nenhum conteúdo" not in rules_content:
            # Retornamos o texto com um prefixo indicando a fonte
            return f"FONTE: DOCUMENTAÇÃO OFICIAL ({target_program.upper()}) - FULL CONTEXT\n\n{rules_content}"
        else:
            print(f"[SmartResearch] readRulesTool falhou ou não retornou dados: {rules_content}")

    # 2. RAG (Em Standby - Desativado)
    # print(f"[SmartResearch] Tentando RAG para: '{query}'")
    # rag_result_json = await knowledgeSearchTool(query, collection_name)
    # ... (Código RAG comentado) ...

    # 3. Fallback para Web (Se não for regra específica ou se falhar)
    return await perform_web_fallback(query, "Full Context não aplicável ou RAG em standby.")

async def perform_web_fallback(query: str, reason: str) -> str:
    print(f"[SmartResearch] Iniciando busca Web. Motivo: {reason}")
    try:
        web_result = duckDuckGoSearchTool(query)
        print(f"[SmartResearch] Web Search concluído.")
        return f"FONTE: PESQUISA NA WEB ({reason})\n\n{web_result}"
    except Exception as e:
        logger.error(f"Fallback web search failed: {e}")
        return f"Não encontrei informações na base interna e a busca na web falhou: {str(e)}"
