import os
from pypdf import PdfReader
from src.lib.error_handler import safe_execution

# Map of lowercase keyword → PDF filename
# Multiple keys can point to the same file for fuzzy matching
PARTNER_PDF_MAP = {
    "fundação estudar": "Fundação Estudar.pdf",
    "fundacao estudar": "Fundação Estudar.pdf",
    "estudar": "Fundação Estudar.pdf",
    "instituto ponte": "Instituto Ponte.pdf",
    "ponte": "Instituto Ponte.pdf",
    "programa aurora": "Programa Aurora Instituto Sol.pdf",
    "instituto sol": "Programa Aurora Instituto Sol.pdf",
    "aurora": "Programa Aurora Instituto Sol.pdf",
    "sol": "Programa Aurora Instituto Sol.pdf",
}

PARTNERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "documents", "partners")

@safe_execution(error_type="tool_error", default_return="Erro ao ler documento do parceiro.")
def readPartnerDocTool(partner_name: str) -> str:
    """
    Reads the full text content of a partner's PDF document.

    Args:
        partner_name (str): The name of the partner program (e.g. 'Fundação Estudar', 'Instituto Ponte', 'Programa Aurora').

    Returns:
        str: The full text extracted from the partner's PDF document.
    """
    if not partner_name:
        return "Erro: O argumento 'partner_name' é obrigatório."

    name_lower = partner_name.lower().strip()

    # Try exact match first, then substring match
    pdf_filename = PARTNER_PDF_MAP.get(name_lower)

    if not pdf_filename:
        # Fuzzy: check if any key is contained in the input or vice-versa
        for key, filename in PARTNER_PDF_MAP.items():
            if key in name_lower or name_lower in key:
                pdf_filename = filename
                break

    if not pdf_filename:
        available = ", ".join(sorted(set(PARTNER_PDF_MAP.values())))
        return f"Parceiro '{partner_name}' não encontrado. Parceiros disponíveis: {available}"

    file_path = os.path.join(PARTNERS_DIR, pdf_filename)

    if not os.path.exists(file_path):
        return f"Erro: Arquivo '{pdf_filename}' não encontrado em {PARTNERS_DIR}."

    print(f"[ReadPartnerDoc] Lendo PDF: {pdf_filename}")

    reader = PdfReader(file_path)
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

    if not full_text.strip():
        return f"Aviso: O PDF '{pdf_filename}' não contém texto extraível."

    return f"CONTEÚDO DO DOCUMENTO: {pdf_filename}\n{'=' * 40}\n\n{full_text}"
