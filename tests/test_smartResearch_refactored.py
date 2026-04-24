"""
TDD RED → GREEN: tests for refactored smartResearchTool
Verifies that hardcoded filesystem reads are replaced by getKnowledgeContentTool calls.
"""
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock, call

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-key"
os.environ["SUPABASE_SERVICE_KEY"] = "mock-service-key"

from src.tools.smartResearch import smartResearchTool

FALLBACK = "Não encontrei informações na base de conhecimento."


# RED 1: program='prouni' must call getKnowledgeContentTool(category='prouni')
def test_prouni_calls_kb_tool_with_category():
    with patch("src.tools.smartResearch.getKnowledgeContentTool") as mock_kb, \
         patch("src.tools.smartResearch.perform_web_fallback", new_callable=AsyncMock) as mock_web:
        mock_kb.return_value = "Conteúdo ProUni do banco de dados"

        result = asyncio.run(smartResearchTool(query="o que é o prouni?", program="prouni"))

        mock_kb.assert_called_once_with(category="prouni")
        assert "PROUNI" in result.upper()
        mock_web.assert_not_called()


# RED 2: program='programs' + partner_name='Insper' calls getKnowledgeContentTool(partner_name='Insper')
def test_programs_with_partner_name_calls_kb_tool():
    with patch("src.tools.smartResearch.getKnowledgeContentTool") as mock_kb, \
         patch("src.tools.smartResearch.perform_web_fallback", new_callable=AsyncMock) as mock_web:
        mock_kb.return_value = "Edital Insper 2026.2"

        result = asyncio.run(smartResearchTool(
            query="quais os requisitos do Insper?",
            program="programs",
            partner_name="Bolsa Integral do Insper",
        ))

        # Must call with partner_name (not category)
        assert call(partner_name="Bolsa Integral do Insper") in mock_kb.call_args_list
        assert "INSPER" in result.upper()
        mock_web.assert_not_called()


# RED 3: when getKnowledgeContentTool returns fallback, must do web fallback
def test_falls_back_to_web_when_kb_empty():
    with patch("src.tools.smartResearch.getKnowledgeContentTool") as mock_kb, \
         patch("src.tools.smartResearch.perform_web_fallback", new_callable=AsyncMock) as mock_web:
        mock_kb.return_value = FALLBACK  # tool returns fallback message
        mock_web.return_value = "FONTE: PESQUISA NA WEB\n\nResultado web."

        result = asyncio.run(smartResearchTool(query="como funciona o sisu?", program="sisu"))

        mock_web.assert_called_once()
        assert "PESQUISA NA WEB" in result


# RED 4: must NOT import readPartnerDocTool or readRulesTool
def test_no_hardcoded_tool_imports():
    import src.tools.smartResearch as mod

    assert not hasattr(mod, "readPartnerDocTool"), (
        "readPartnerDocTool must not be imported in smartResearch.py"
    )
    assert not hasattr(mod, "readRulesTool"), (
        "readRulesTool must not be imported in smartResearch.py"
    )
