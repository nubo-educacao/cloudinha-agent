import asyncio
import sys
import os
from dotenv import load_dotenv

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())
load_dotenv()

from src.tools.getKnowledgeContent import getKnowledgeContentTool

def test_prouni_lookup():
    print("--- Testando Busca de ProUni ---")
    result = getKnowledgeContentTool(category="prouni")
    print(f"Resultado (primeiros 200 caracteres):\n{result[:200]}...")
    
    if "Edital" in result:
        print("\n✅ SUCESSO: Documento encontrado!")
    else:
        print("\n❌ FALHA: Documento não encontrado na base.")

def test_insper_lookup():
    print("\n--- Testando Busca de Insper ---")
    result = getKnowledgeContentTool(partner_name="Insper")
    print(f"Resultado (primeiros 200 caracteres):\n{result[:200]}...")
    
    if "Insper" in result:
        print("\n✅ SUCESSO: Documento encontrado!")
    else:
        print("\n❌ FALHA: Documento não encontrado na base.")

if __name__ == "__main__":
    test_prouni_lookup()
    test_insper_lookup()
