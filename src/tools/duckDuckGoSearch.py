from duckduckgo_search import DDGS

def duckDuckGoSearchTool(query: str) -> str:
    """
    Realiza uma busca na internet utilizando o DuckDuckGo.
    Útil para encontrar informações recentes ou que não estão na base de conhecimento interna.
    
    Args:
        query: O termo ou pergunta a ser pesquisada.
        
    Returns:
        Um resumo dos resultados encontrados na web.
    """
    try:
        # Using direct library with 'api' backend as it proved more stable in tests
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="br-pt", max_results=5))
            
        if not results:
             return "Não encontrei resultados na internet para essa busca."
             
        # Format results
        summary = ""
        for res in results:
            title = res.get('title', 'Sem título')
            body = res.get('body', '')
            url = res.get('href', '')
            summary += f"- {title}: {body} ({url})\n"
            
        return summary
        
    except Exception as e:
        print(f"[ERROR] duckDuckGoSearchTool failed: {e}", flush=True)
        return "Desculpe, não consegui realizar a busca na internet no momento."
