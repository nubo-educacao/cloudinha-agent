import os
from src.lib.error_handler import safe_execution

RULES_CONTEXT_DIR = "rules_context"

@safe_execution(error_type="tool_error", default_return="Erro ao ler as regras.")
def readRulesTool(program: str = None):
    """
    Reads the full text of official rules and documentation for a specific topic (Prouni, Sisu, Cloudinha).

    IMPORTANT: Use this tool with program='cloudinha' whenever the user asks about how the bot works, its architecture, or who created it.
    
    Args:
        program (str): The topic to retrieve rules for. Must be 'prouni', 'sisu', or 'cloudinha'. Case insensitive.
    
    Returns:
        str: The full text content of the relevant documents found in the knowledge base.
    """
    if not program:
        return "Erro: O argumento 'program' é obrigatório (prouni, sisu ou cloudinha)."
        
    program_lower = program.lower().strip()
    
    # Base Knowledge Directory
    # Adjusted to point to src/agent/knowledge
    base_knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent", "knowledge")
    target_dir = os.path.join(base_knowledge_dir, program_lower)
    
    if not os.path.exists(target_dir):
        return f"Erro: Tópico '{program}' não encontrado na base de conhecimento (Diretório esperado: {target_dir}). Tente 'prouni', 'sisu' ou 'cloudinha'."
        
    context_files = []
    
    for f in os.listdir(target_dir):
        if f.endswith(".md") or f.endswith(".txt"):
            context_files.append(os.path.join(target_dir, f))

    if not context_files:
        return f"Aviso: O diretório para '{program}' existe mas está vazio."

    full_content = ""
    
    for file_path in context_files:
        # Note: safe_execution wraps the whole function, so if one file fails unexpectedly it will fail the whole call unless we handle it locally. 
        # But file reading is simple enough. If strict 'no manual try/catch', I'm removing it.
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            filename = os.path.basename(file_path)
            full_content += f"\n\n{'='*20}\nCONTEÚDO DO ARQUIVO: {filename}\n{'='*20}\n\n{content}"
            
    return full_content
