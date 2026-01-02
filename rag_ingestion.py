import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import SupabaseVectorStore
from src.lib.supabase import supabase
from dotenv import load_dotenv

load_dotenv()

def ingest_documents(directory_path: str = "documents"):
    """
    Ingests documents (PDF/Text) from the specified directory into Supabase Vector Store.
    """
    
    # 1. Setup Embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    
    documents = []
    
    # 2. Load Documents
    if not os.path.exists(directory_path):
        print(f"Directory {directory_path} not found.")
        return

    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        try:
            if filename.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                documents.extend(loader.load())
            elif filename.endswith(".txt") or filename.endswith(".md"):
                loader = TextLoader(file_path)
                documents.extend(loader.load())
            else:
                print(f"Skipping unsupported file: {filename}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")

    if not documents:
        print("No documents found to ingest.")
        return

    # 3. Split Text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    splits = text_splitter.split_documents(documents)
    
    # Sanitize content to remove null bytes
    for split in splits:
        split.page_content = split.page_content.replace('\x00', '')
        
    print(f"Split into {len(splits)} chunks.")

    # 4. Index to Supabase
    # Note: Requires a table 'documents' with 'content', 'metadata', 'embedding' columns in Supabase
    # and pgvector extension enabled.
    
    try:
        vector_store = SupabaseVectorStore.from_documents(
            documents=splits,
            embedding=embeddings,
            client=supabase,
            table_name="documents",
            query_name="match_documents",
            chunk_size=500
        )
        print("Ingestion complete!")
    except Exception as e:
        print(f"Error indexing to Supabase: {e}")

if __name__ == "__main__":
    ingest_documents()
