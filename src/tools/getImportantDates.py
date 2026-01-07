import os
from dotenv import load_dotenv
from supabase import create_client
from typing import Dict, List, Any

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def getImportantDatesTool(program_type: str = None) -> List[Dict[str, Any]]:
    """
    Busca datas importantes e prazos de programas como Prouni, Sisu ou Fies.
    
    Args:
        program_type (str, optional): O tipo de programa para filtrar ('prouni', 'sisu', 'general'). 
                                      Se não informado, retorna tudo.
    """
    try:
        query = supabase.table("important_dates").select("*")
        
        if program_type and program_type.lower() in ['prouni', 'sisu', 'general']:
            query = query.eq("type", program_type.lower())
            
        response = query.execute()
        
        # Sort by start_date ascending locally if needed, or could do in query
        dates = response.data
        if dates:
            dates.sort(key=lambda x: x['start_date'])
            
        print(f"[DEBUG TOOL] getImportantDatesTool found {len(dates)} dates for type={program_type}")
        return dates
    except Exception as e:
        print(f"!!! [ERROR TOOL] getImportantDatesTool failed: {e}")
        return []
