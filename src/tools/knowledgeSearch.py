from typing import List
import os
import asyncio
from google import genai
from src.lib.supabase import supabase
from dotenv import load_dotenv

load_dotenv()

# Initialize GenAI Client Globally (or lazy load)
api_key = os.getenv("GOOGLE_API_KEY")
client = None
if api_key:
    client = genai.Client(api_key=api_key)
else:
    print("Warning: GOOGLE_API_KEY not found for knowledgeSearchTool.")

from src.lib.error_handler import safe_execution

@safe_execution(error_type="tool_error", default_return="Desculpe, tive um erro técnico ao consultar minha base de conhecimento.")
async def knowledgeSearchTool(query: str, collection_name: str = "documents") -> str:
    """
    Realiza uma busca na Base de Conhecimento (RAG) sobre Prouni e Sisu.
    
    Args:
        query: A pergunta ou dúvida do usuário.
        collection_name: Nome da coleção (tabela) onde buscar. Padrão: 'documents'.
        
    Returns:
        Um texto contendo os trechos mais relevantes encontrados na documentação.
    """
    global client
    
    if not client:
        return "Erro de configuração: Chave de API do Google não encontrada."

    # 1. Generate Embedding (Async)
    # Using text-embedding-004 (recommended) instead of legacy embedding-001
    print(f"[DEBUG RAG] Generating embedding (Async) using text-embedding-004 for: '{query}'...", flush=True)
    
    response = await client.aio.models.embed_content(
        model="models/text-embedding-004",
        contents=query
    )
    
    if not response:
            print(f"[DEBUG RAG] Response is None/Empty", flush=True)
            return "Erro técnico ao processar sua pergunta."
            
    # Check for 'embedding' (singular) or 'embeddings' (plural)
    if hasattr(response, 'embeddings'):
            # Batch response?
            query_embedding = response.embeddings[0].values
    elif hasattr(response, 'embedding'):
            query_embedding = response.embedding.values
    else:
            print(f"[DEBUG RAG] Response has no embedding(s): {dir(response)}", flush=True)
            return "Erro técnico ao processar sua pergunta."
    print("[DEBUG RAG] Embedding generated successfully.", flush=True)
    
    # 2. Call RPC directly
    print(f"[DEBUG RAG] Calling match_documents RPC...", flush=True)
    
    params = {
        "query_embedding": query_embedding,
        "match_threshold": 0.3,
        "match_count": 5
    }
    
    response_rpc = supabase.rpc("match_documents", params).execute()
    
    print(f"[DEBUG RAG] RPC Response Count: {len(response_rpc.data) if response_rpc.data else 0}", flush=True)
    
    if not response_rpc.data:
        print("[DEBUG RAG] No documents found matching threshold.")
        return "Não encontrei informações específicas sobre isso na minha base de conhecimento."
        
    # 3. Compile results
    docs = response_rpc.data

    context_text = "\n\n".join([f"--- Contexto ---\n{doc.get('content', '')}" for doc in docs])
    return context_text
