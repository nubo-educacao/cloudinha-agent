import logging
import os
# We need to access supabase client. 
# Ideally we import from src.agent.agent but circular imports could be an issue if agent.py imports workflow which imports retrieval.
# However, agent.py imports simple tools. workflow imports agent.
# So retrieval importing agent might be circular if agent imports workflow?
# agent.py imports workflow? No. 'workflow.py' imports 'agent.py'.
# So 'retrieval.py' importing 'agent.py' is SAFE.

from src.agent.agent import supabase_client

logger = logging.getLogger(__name__)

def retrieve_similar_examples(query: str, intent_category: str = None) -> str:
    """
    Retrieves few-shot examples from the 'learning_examples' table.
    Currently uses basic filtering by intent_category.
    Future: Vector search using embeddings.
    """
    if not supabase_client:
        logger.warning("Supabase client not initialized, skipping retrieval.")
        return ""
    
    try:
        # Build query
        db_query = supabase_client.table("learning_examples").select("*").eq("is_active", True)
        
        if intent_category:
            # Map agent names to categories if needed, or assume 1:1
            # categories in DB: 'sisu_dates', 'match_logic', 'general_qa', etc.
            # We can try to match loosely or fetch generic ones if category doesn't match
            # For now, let's assume intent_category passed IS the category column value
            # or we sort of 'ilike' it.
            # Let's do a direct match for now.
            db_query = db_query.eq("intent_category", intent_category)
        
        # Limit to 3 recent examples
        response = db_query.order("created_at", desc=True).limit(3).execute()
        examples = response.data
        
        if not examples:
            return ""
            
        formatted = []
        for ex in examples:
            q = ex.get('input_query', '').replace('\n', ' ')
            a = ex.get('ideal_output', '').replace('\n', ' ')
            r = ex.get('reasoning', '')
            formatted.append(f"- Exemplo: {q}\n  Resposta Ideal: {a}\n  Motivo: {r}")
            
        block = (
    "\n\n### EXEMPLOS DE TOM E ESTILO (APRENDIZADO)\n"
    "Os exemplos abaixo mostram o tom e a qualidade esperada da RESPOSTA FINAL ao usuário. "
    "ATENÇÃO: Para gerar respostas como estas, você DEVE OBRIGATORIAMENTE usar as ferramentas (Tools) disponíveis primeiro. "
    "Não tente gerar o texto diretamente sem antes consultar a ferramenta.\n\n" 
    + "\n\n".join(formatted)
)
        return block

    except Exception as e:
        logger.error(f"Error retrieving examples: {e}")
        return ""
