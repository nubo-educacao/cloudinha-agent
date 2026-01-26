from ddgs import DDGS
from src.lib.error_handler import safe_execution
from src.lib.resilience import retry_with_backoff

@safe_execution(error_type="tool_error", default_return="Desculpe, não consegui realizar a busca na internet no momento.")
@retry_with_backoff(retries=3)
def duckDuckGoSearchTool(query: str) -> str:
    """
    Realiza uma busca na internet utilizando o DuckDuckGo.
    Útil para encontrar informações recentes ou que não estão na base de conhecimento interna.
    
    Args:
        query: O termo ou pergunta a ser pesquisada.
        
    Returns:
        Um resumo dos resultados encontrados na web.
    """
    print(f"[DuckDuckGo] Iniciando busca para: '{query}'", flush=True)
    
    # Primeira tentativa: com região BR
    try:
        print(f"[DuckDuckGo] Tentativa 1: Busca com região 'br-pt'", flush=True)
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="br-pt", max_results=5, safesearch="off", timelimit=None))
            
        print(f"[DuckDuckGo] Resultados obtidos (região BR): {len(results)}", flush=True)
        
        if results:
            return format_results(results)
            
    except Exception as e:
        print(f"[DuckDuckGo] Erro na busca regional: {type(e).__name__}: {e}", flush=True)
        # Continue to next attempt
    
    # Segunda tentativa: sem restrição de região (Global)
    # Exceptions here will be caught by safe_execution
    print(f"[DuckDuckGo] Tentativa 2: Busca SEM restrição de região", flush=True)
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5, safesearch="off", timelimit=None))
        
    print(f"[DuckDuckGo] Resultados obtidos (global): {len(results)}", flush=True)
    
    if results:
        return format_results(results)
    else:
        print(f"[DuckDuckGo] ⚠️ NENHUM resultado encontrado para query: '{query}'", flush=True)
        return "Não encontrei resultados na internet para essa busca."

def format_results(results: list) -> str:
    """Formata os resultados da busca em texto legível."""
    summary = ""
    for i, res in enumerate(results, 1):
        title = res.get('title', 'Sem título')
        body = res.get('body', '')
        url = res.get('href', '')
        summary += f"{i}. **{title}**\n   {body}\n   Fonte: {url}\n\n"
    
    print(f"[DuckDuckGo] ✅ Resumo formatado com {len(results)} resultados", flush=True)
    return summary.strip()
