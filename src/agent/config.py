# Configuração centralizada de modelos LLM para o Cloudinha Agent
# Facilita manutenção e testes A/B de diferentes modelos

# === MODELOS DE CHAT ===

# Modelo principal para agentes conversacionais (Ilimitado no Tier atual)
# gemini-2.0-flash: Rápido, inteligente e seguro para escala
MODEL_CHAT = "gemini-2.0-flash"

# Modelo leve para classificação/roteamento (Ilimitado no Tier atual)
# gemini-2.0-flash-lite: Versão mais recente e leve da família 2.0
MODEL_ROUTER = "gemini-2.0-flash-lite"

# Modelos para tarefas que exigem maior inteligência (Tools/Reasoning)
# Recomendação: Manter no 2.0 Flash (Ilimitado) para evitar gargalos com 1100 usuários.
# Se quiser arriscar limites (10k/dia), pode testar "gemini-2.5-flash" aqui.
MODEL_ONBOARDING = MODEL_CHAT
MODEL_REASONING = MODEL_CHAT


# === MODELOS DE EMBEDDING ===

# Modelo de embeddings para RAG
# text-embedding-004: Modelo mais recente, substitui embedding-001 (legado)
MODEL_EMBEDDING = "models/text-embedding-004"


# === CONFIGURAÇÕES DE RAG ===

RAG_MATCH_THRESHOLD = 0.3
RAG_MATCH_COUNT = 5
