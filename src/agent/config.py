# Configuração centralizada de modelos LLM para o Cloudinha Agent
# Facilita manutenção e testes A/B de diferentes modelos

# === MODELOS DE CHAT ===

# Modelo principal para agentes conversacionais
# gemini-2.0-flash: Rápido, bom custo-benefício para chatbot
MODEL_CHAT = "gemini-2.0-flash"

# Modelo leve para classificação/roteamento
# gemini-2.0-flash-lite: Modelo leve para tarefas simples como intent classification
MODEL_ROUTER = "gemini-2.0-flash-lite"

# Modelo para raciocínio complexo (match workflow)
# Mantemos flash por enquanto, pode evoluir para Pro se necessário
MODEL_REASONING = "gemini-2.0-flash"


# === MODELOS DE EMBEDDING ===

# Modelo de embeddings para RAG
# text-embedding-004: Modelo mais recente, substitui embedding-001 (legado)
MODEL_EMBEDDING = "models/text-embedding-004"


# === CONFIGURAÇÕES DE RAG ===

RAG_MATCH_THRESHOLD = 0.3
RAG_MATCH_COUNT = 5
