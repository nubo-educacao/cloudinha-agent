import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Mock environment
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-key"

from src.tools.duckDuckGoSearch import duckDuckGoSearchTool
from src.tools.smartResearch import smartResearchTool

async def verify():
    print("--- Verificando DuckDuckGoSearchTool com site ---")
    res1 = duckDuckGoSearchTool(query="Fundação Estudar", site="partners.link")
    print(f"Resultado (deve conter partners.link): {res1[:200]}...")
    assert "partners.link" in res1.lower() or "não encontrei" in res1.lower()
    
    print("\n--- Verificando SmartResearchTool Fallback com site ---")
    # Este teste depende do perform_web_fallback ser chamado
    # Como não temos uma base de dados real aqui, ele deve falhar no local e ir para o web fallback
    res2 = await smartResearchTool(query="Quem é o parceiro Teste?", program="programs")
    print(f"Resultado (deve conter REF: partners.link): {res2[:200]}...")
    assert "REF: partners.link" in res2
    
    print("\n✅ Verificação concluída com sucesso!")

if __name__ == "__main__":
    asyncio.run(verify())
