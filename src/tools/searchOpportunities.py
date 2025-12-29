from typing import Optional
from src.lib.supabase import supabase

def searchOpportunitiesTool(
    course_name: str,
    enem_score: float,
    per_capita_income: float,
    city_name: Optional[str] = None
) -> list:
    """Busca e filtra vagas de Sisu e Prouni no banco de dados. É a única forma de obter a lista de cursos."""
    
    query = supabase.table("opportunities_view") \
        .select("course_id, institution, course, type, scholarship_type, cutoff_score, city") \
        .ilike("course", f"%{course_name}%") \
        .lte("cutoff_score", enem_score)

    if city_name:
        query = query.ilike("city", f"%{city_name}%")

    # Ordenar por cutoff_score ascendente (menor nota de corte primeiro) e limitar resultados
    response = query.order("cutoff_score", desc=False).limit(72).execute()

    return response.data
