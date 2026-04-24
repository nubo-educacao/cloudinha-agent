"""
TDD RED → GREEN: tests for getKnowledgeContentTool
Verifies DB-backed knowledge retrieval replacing filesystem hardcodes.
"""
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-key"
os.environ["SUPABASE_SERVICE_KEY"] = "mock-service-key"

from src.tools.getKnowledgeContent import getKnowledgeContentTool

FALLBACK = "Não encontrei informações na base de conhecimento."


def _make_mocks(cat_data=None, partner_data=None, doc_data=None, storage_bytes=b""):
    """Build a configured supabase mock for the given scenario."""
    mock_cat = MagicMock()
    mock_cat.select.return_value.eq.return_value.execute.return_value.data = cat_data or []

    mock_partners = MagicMock()
    mock_partners.select.return_value.ilike.return_value.execute.return_value.data = partner_data or []

    mock_docs = MagicMock()
    # category path: .select().eq(is_active).eq(category_id).execute()
    mock_docs.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = doc_data or []
    # partner path (single): same chain (eq partner_id is the second .eq())
    # partner path (multiple): .select().eq(is_active).in_(partner_ids).execute()
    mock_docs.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = doc_data or []

    def table_side_effect(name):
        if name == "knowledge_categories":
            return mock_cat
        if name == "partners":
            return mock_partners
        if name == "knowledge_documents":
            return mock_docs
        return MagicMock()

    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = table_side_effect
    mock_supabase.storage.from_.return_value.download.return_value = storage_bytes
    return mock_supabase


# RED 1: returns content when category='prouni' has active docs in DB
@patch("src.tools.getKnowledgeContent.supabase")
def test_category_prouni_returns_content(mock_supabase):
    sb = _make_mocks(
        cat_data=[{"id": "cat-prouni-123"}],
        doc_data=[{"title": "Edital ProUni", "storage_path": "documents/prouni.md"}],
        storage_bytes=b"# Conteudo ProUni\n\nEdital completo do ProUni 2026.",
    )
    mock_supabase.table.side_effect = sb.table.side_effect
    mock_supabase.storage = sb.storage

    result = getKnowledgeContentTool(category="prouni")

    assert FALLBACK not in result
    assert "Edital ProUni" in result
    assert "Conteudo ProUni" in result


# RED 2: returns content when partner_name='Insper' (fuzzy ILIKE match)
@patch("src.tools.getKnowledgeContent.supabase")
def test_partner_name_insper_fuzzy_match(mock_supabase):
    sb = _make_mocks(
        partner_data=[{"id": "partner-insper-456"}],
        doc_data=[{"title": "Edital Insper 2026.2", "storage_path": "documents/insper.md"}],
        storage_bytes=b"# Edital Insper\n\nProcesso seletivo Insper 2026.",
    )
    mock_supabase.table.side_effect = sb.table.side_effect
    mock_supabase.storage = sb.storage

    result = getKnowledgeContentTool(partner_name="Insper")

    assert FALLBACK not in result
    assert "Edital Insper" in result
    assert "Processo seletivo" in result


# RED 3: returns friendly fallback when no document found
@patch("src.tools.getKnowledgeContent.supabase")
def test_no_document_returns_fallback(mock_supabase):
    sb = _make_mocks(
        cat_data=[{"id": "cat-sisu-789"}],
        doc_data=[],  # empty — no active docs
        storage_bytes=b"",
    )
    mock_supabase.table.side_effect = sb.table.side_effect
    mock_supabase.storage = sb.storage

    result = getKnowledgeContentTool(category="sisu")

    assert result == FALLBACK


# RED 4: filters only is_active=True — no docs when category returns no category_id
@patch("src.tools.getKnowledgeContent.supabase")
def test_returns_fallback_when_category_not_found_in_db(mock_supabase):
    sb = _make_mocks(
        cat_data=[],  # category doesn't exist in DB
        doc_data=[{"title": "Should not appear", "storage_path": "x.md"}],
        storage_bytes=b"secret content",
    )
    mock_supabase.table.side_effect = sb.table.side_effect
    mock_supabase.storage = sb.storage

    result = getKnowledgeContentTool(category="nonexistent")

    assert result == FALLBACK
    assert "secret content" not in result


# RED 5: concatenates multiple docs from same category with separators
@patch("src.tools.getKnowledgeContent.supabase")
def test_multiple_docs_are_concatenated(mock_supabase):
    sb = _make_mocks(
        cat_data=[{"id": "cat-prouni-123"}],
        doc_data=[
            {"title": "Edital ProUni", "storage_path": "documents/edital.md"},
            {"title": "Docs Renda ProUni", "storage_path": "documents/renda.md"},
        ],
        storage_bytes=b"CONTEUDO DO ARQUIVO",
    )
    mock_supabase.table.side_effect = sb.table.side_effect
    mock_supabase.storage = sb.storage

    result = getKnowledgeContentTool(category="prouni")

    assert "Edital ProUni" in result
    assert "Docs Renda ProUni" in result
    # Both docs concatenated — there should be content from both sections
    assert result.count("CONTEUDO DO ARQUIVO") == 2
