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
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embeddings,
            table_name=collection_name,
            query_name="match_documents"
        )
        
        # Search for top 3 relevant chunks
        docs = vector_store.similarity_search(query, k=3)
        
        if not docs:
            return "Não encontrei informações específicas sobre isso na minha base de conhecimento."
            
        # Compile results
        context_text = "\n\n".join([f"--- Contexto ---\n{doc.page_content}" for doc in docs])
        return context_text
        
    except Exception as e:
        print(f"Error in knowledgeSearchTool: {e}")
        return "Desculpe, tive um erro técnico ao consultar minha base de conhecimento."
