from langchain_core.tools import tool
import os

RULES_CONTEXT_DIR = "rules_context"

# @tool("readRulesTool") - Removed to avoid conflict with LlmAgent
def readRulesTool(program: str = None):
    """
    Reads the full text of official rules (Edital) and documentation for a specific government program (Prouni or Sisu).
    Use this tool when the user asks about criteria, dates, documentation, or rules of Prouni or Sisu.
    
    Args:
        program (str): The program to retrieve rules for. Must be 'prouni' or 'sisu'. Case insensitive.
    
    Returns:
        str: The full text content of the relevant documents.
    """
    if not program:
        return "Erro: O argumento 'program' é obrigatório (prouni ou sisu)."
        
    program_lower = program.lower().strip()
    
    
    if program_lower not in ['prouni', 'sisu', 'cloudinha']:
        return f"Erro: Programa '{program}' não reconhecido. Use 'prouni', 'sisu' ou 'cloudinha' (para auto-explicação)."
        
    context_files = []
    
    # Define which files to load for each program
    if program_lower == 'prouni':
        context_files = [os.path.join(RULES_CONTEXT_DIR, "prouni_edital_2026.txt"), os.path.join(RULES_CONTEXT_DIR, "prouni_documentacao.txt")]
    elif program_lower == 'sisu':
        context_files = [os.path.join(RULES_CONTEXT_DIR, "sisu_edital_2026.txt"), os.path.join(RULES_CONTEXT_DIR, "sisu_documentacao.txt")]
    elif program_lower == 'cloudinha':
        # New Logic: Dynamic Context from Directory
        context_dir = "cloudinha_context"
        context_files = []
        
        if os.path.exists(context_dir):
            for f in os.listdir(context_dir):
                if f.endswith(".md") or f.endswith(".txt"):
                    context_files.append(os.path.join(context_dir, f))
        else:
            return f"Erro: Diretório de contexto '{context_dir}' não encontrado."

    full_content = ""
    
    for file_path in context_files:
        # For Sisu/Prouni, file_path was just filename before, I changed it to full path in the list
        # We need to handle that logic carefully. 
        # The original code did: os.path.join(RULES_CONTEXT_DIR, filename) inside the loop.
        # I moved the join logic up.
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    filename = os.path.basename(file_path)
                    full_content += f"\n\n{'='*20}\nCONTEÚDO DO ARQUIVO: {filename}\n{'='*20}\n\n{content}"
            except Exception as e:
                full_content += f"\n\nErro ao ler {os.path.basename(file_path)}: {str(e)}"
        else:
             full_content += f"\n\nAviso: Arquivo de contexto {os.path.basename(file_path)} não encontrado no caminho esperado: {file_path}."
            
    if not full_content:
        return "Nenhum conteúdo de regras foi encontrado. Verifique se os arquivos de texto foram gerados."
        
    return full_content
