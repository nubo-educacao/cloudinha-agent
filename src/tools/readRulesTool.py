from langchain_core.tools import tool
import os

RULES_CONTEXT_DIR = "rules_context"

# @tool("readRulesTool") - Removed to avoid conflict with LlmAgent
def readRulesTool(program: str = None):
    """
    Reads the full text of official rules and documentation for a specific topic (Prouni, Sisu, Cloudinha).
    
    Args:
        program (str): The topic to retrieve rules for. Must be 'prouni', 'sisu', or 'cloudinha'. Case insensitive.
    
    Returns:
        str: The full text content of the relevant documents found in the knowledge base.
    """
    if not program:
        return "Erro: O argumento 'program' é obrigatório (prouni, sisu ou cloudinha)."
        
    program_lower = program.lower().strip()
    
    # Base Knowledge Directory
    base_knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
    target_dir = os.path.join(base_knowledge_dir, program_lower)
    
    if not os.path.exists(target_dir):
        return f"Erro: Tópico '{program}' não encontrado na base de conhecimento (Diretório esperado: {target_dir}). Tente 'prouni', 'sisu' ou 'cloudinha'."
        
    context_files = []
    
    try:
        for f in os.listdir(target_dir):
            if f.endswith(".md") or f.endswith(".txt"):
                context_files.append(os.path.join(target_dir, f))
    except Exception as e:
        return f"Erro ao listar arquivos do diretório {target_dir}: {str(e)}"

    if not context_files:
        return f"Aviso: O diretório para '{program}' existe mas está vazio."

    full_content = ""
    
    for file_path in context_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                filename = os.path.basename(file_path)
                full_content += f"\n\n{'='*20}\nCONTEÚDO DO ARQUIVO: {filename}\n{'='*20}\n\n{content}"
        except Exception as e:
            full_content += f"\n\nErro ao ler {os.path.basename(file_path)}: {str(e)}"
            
    return full_content
