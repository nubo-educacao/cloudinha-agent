from typing import List
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from src.lib.supabase import supabase
from dotenv import load_dotenv

load_dotenv()

def knowledgeSearchTool(query: str, collection_name: str = "documents") -> str:
    """
    Realiza uma busca na Base de Conhecimento (RAG) sobre Prouni e Sisu.
    
    Args:
        query: A pergunta ou dúvida do usuário.
        collection_name: Nome da coleção (tabela) onde buscar. Padrão: 'documents'.
        
    Returns:
        Um texto contendo os trechos mais relevantes encontrados na documentação.
    """
    
    try:
        embeddings_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        
        # 1. Generate Embedding
        query_embedding = embeddings_model.embed_query(query)
        
        # 2. Call RPC directly
        # match_documents(query_embedding, match_threshold, match_count)
        params = {
            "query_embedding": query_embedding,
            "match_threshold": 0.5, # Adjust threshold as needed
            "match_count": 3
        }
        
        response = supabase.rpc("match_documents", params).execute()
        
        if not response.data:
            return "Não encontrei informações específicas sobre isso na minha base de conhecimento."
            
        # 3. Compile results
        # response.data is a list of dicts: {content, metadata, similarity, ...}
        docs = response.data
        context_text = "\n\n".join([f"--- Contexto ---\n{doc.get('content', '')}" for doc in docs])
        return context_text
        
    except Exception as e:
        print(f"Error in knowledgeSearchTool: {e}")
        return "Desculpe, tive um erro técnico ao consultar minha base de conhecimento."
