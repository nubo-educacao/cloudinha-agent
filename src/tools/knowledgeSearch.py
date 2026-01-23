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

    try:

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
             
        # print(f"[DEBUG RAG] Response type: {type(response)}", flush=True)
        # print(f"[DEBUG RAG] Response dir: {dir(response)}", flush=True)

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
        # Supabase-py async client isn't fully standard, but the 'execute' is sync-blocking usually unless using async_client?
        # The src.lib.supabase seems to be the sync client 'create_client'.
        # However, making the Supabase call inside an async function is standard practice if the lib doesn't block heavily,
        # or we should run it in executor if strictly blocking.
        # Ideally we use an async Supabase client, but let's stick to existing lib for now, 
        # as it was the Embedding step that was hanging.
        
        print(f"[DEBUG RAG] Calling match_documents RPC...", flush=True)
        
        params = {
            "query_embedding": query_embedding,
            "match_threshold": 0.3,
            "match_count": 5
        }
        
        # To avoid blocking the event loop with Supabase sync call, we can wrap it.
        # But let's try direct first (usually network IO is fast via requests/httpx unless heavily blocking).
        # Actually, let's play safe and allow the supabase call to run.
        
        # Wait, supabase-py relies on 'httpx' or 'requests'? 'supbabase' wraps 'postgrest'.
        # If it uses 'httpx' (sync), it might block. But let's proceed.
        
        response_rpc = supabase.rpc("match_documents", params).execute()
        
        print(f"[DEBUG RAG] RPC Response Count: {len(response_rpc.data) if response_rpc.data else 0}", flush=True)
        
        if not response_rpc.data:
            print("[DEBUG RAG] No documents found matching threshold.")
            return "Não encontrei informações específicas sobre isso na minha base de conhecimento."
            
        # 3. Compile results
        docs = response_rpc.data

        context_text = "\n\n".join([f"--- Contexto ---\n{doc.get('content', '')}" for doc in docs])
        return context_text
        
    except Exception as e:
        print(f"Error in knowledgeSearchTool: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return "Desculpe, tive um erro técnico ao consultar minha base de conhecimento."
