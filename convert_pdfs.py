import pdfplumber
import os

DOCS_DIR = "documents"
OUTPUT_DIR = "rules_context"

# Mapeamento de arquivos de entrada para saída
FILES_TO_CONVERT = {
    "editalProUni2026.pdf": "prouni_edital_2026.txt",
    "PROUNI_documentacao.92fe389a.pdf": "prouni_documentacao.txt",
    "editalSisu2026.pdf": "sisu_edital_2026.txt",
    "SISU_documentacao.1c5f3edc.pdf": "sisu_documentacao.txt"
}

def convert_pdfs():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Diretório '{OUTPUT_DIR}' criado.")

    for pdf_file, txt_file in FILES_TO_CONVERT.items():
        pdf_path = os.path.join(DOCS_DIR, pdf_file)
        txt_path = os.path.join(OUTPUT_DIR, txt_file)

        if not os.path.exists(pdf_path):
            print(f"Aviso: Arquivo {pdf_path} não encontrado. Pulando.")
            continue

        print(f"Convertendo {pdf_file} para {txt_file}...")
        
        try:
            full_text = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        # Limpa caracteres nulos e tenta decodificar corretamente
                        clean_text = text.replace('\x00', '')
                        full_text.append(f"--- Página {i+1} ---\n{clean_text}")
            
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"FONTE: {pdf_file}\n\n")
                f.write("\n\n".join(full_text))
            
            print(f"Sucesso! Salvo em {txt_path}")
            
        except Exception as e:
            print(f"Erro ao converter {pdf_file}: {e}")

if __name__ == "__main__":
    convert_pdfs()
