from typing import Dict, List, Any
from src.lib.supabase import supabase
from src.lib.error_handler import safe_execution

@safe_execution(error_type="tool_error", default_return=[])
def getImportantDatesTool(program_type: str = None) -> List[Dict[str, Any]]:
    """
    Busca datas importantes e prazos de programas como Prouni, Sisu ou Fies.
    
    Args:
        program_type (str, optional): O tipo de programa para filtrar ('prouni', 'sisu', 'general'). 
                                      Se não informado, retorna tudo.
    """
    # Removed manual try/catch block as it is handled by safe_execution
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
