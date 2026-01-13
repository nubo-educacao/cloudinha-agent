from src.tools.knowledgeSearch import knowledgeSearchTool
from src.tools.duckDuckGoSearch import duckDuckGoSearchTool
from google.genai import Client
import os
import logging
import asyncio

logger = logging.getLogger("cloudinha-server")

# Initialize client for verification
# We use a cheaper model if possible, or the same one.
VERIFICATION_MODEL = "gemini-1.5-flash" 

async def smartResearchTool(query: str, collection_name: str = "documents") -> str:
    """
    Realiza uma pesquisa inteligente com verificação de relevância:
    1. Busca no RAG.
    2. Usa LLM para verificar se o RAG responde à pergunta.
    3. Se não responder, faz fallback para Web.
    """
    
    # 1. Tenta RAG
    print(f"[SmartResearch] Tentando RAG para: '{query}'")
    rag_result_json = await knowledgeSearchTool(query, collection_name)
    rag_text = str(rag_result_json)

    # Heurística Rápida (Short-circuit)
    if "nenhum documento relevante encontrado" in rag_text.lower() or len(rag_text) < 50:
        print("[SmartResearch] RAG vazio ou insuficiente (Heurística).")
        return await perform_web_fallback(query, "RAG retornou vazio.")

    # 2. Verificação com LLM (Relevance Check)
    print(f"[SmartResearch] Verificando relevância do RAG com LLM...")
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        client = Client(api_key=api_key)
        
        verification_prompt = f"""
        Você é um avaliador de relevância.
        Pergunta do usuário: "{query}"
        Contexto recuperado:
        {rag_text[:4000]} 

        O contexto acima contém a RESPOSTA EXATA ou INFORMAÇÕES SUFICIENTES para responder à pergunta do usuário?
        Responda APENAS "SIM" ou "NAO".
        """
        
        # We use a quick diverse call. SDK is sync or async? 
        # The client initialized here is sync by default unless verifying usage.
        # But we are inside an async function. Let's use `await client.aio.models.generate_content`
        
        response = await client.aio.models.generate_content(
            model=VERIFICATION_MODEL,
            contents=verification_prompt
        )
        
        decision = response.text.strip().upper()
        print(f"[SmartResearch] Decisão de Relevância: {decision}")
        
        if "NAO" in decision or "NÃO" in decision:
             return await perform_web_fallback(query, "RAG irrelevante segundo verificação.")
             
        # Se SIM, retorna RAG
        return f"FONTE: BASE DE CONHECIMENTO INTERNA\n\n{rag_text}"

    except Exception as e:
        print(f"[SmartResearch] Erro na verificação: {e}. Assumindo RAG válido para evitar custo extra.")
        return f"FONTE: BASE DE CONHECIMENTO INTERNA\n\n{rag_text}"

async def perform_web_fallback(query: str, reason: str) -> str:
    print(f"[SmartResearch] Iniciando busca Web. Motivo: {reason}")
    try:
        # DuckDuckGoTool is currently sync wrapped in async? Or just sync?
        # Standard tool functions in this repo seem to be sync or async mixed.
        # duckDuckGoSearchTool is SYNC (def duckDuckGoSearchTool).
        # We should run it in executor if we want strict async, but for now direct call is fine 
        # as long as it doesn't block too long.
        
        web_result = duckDuckGoSearchTool(query)
        print(f"[SmartResearch] Web Search concluído.")
        return f"FONTE: PESQUISA NA WEB (O RAG falhou: {reason})\n\n{web_result}"
    except Exception as e:
        logger.error(f"Fallback web search failed: {e}")
        return f"Não encontrei informações na base interna e a busca na web falhou: {str(e)}"
