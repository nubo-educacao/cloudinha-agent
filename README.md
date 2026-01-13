# ☁️ Cloudinha Agent (ADK Version)

Este repositório contém o código fonte do agente **Cloudinha**, reescrito utilizando o **Google ADK (Agent Development Kit)**. A nova arquitetura é modular, baseada em agentes LLM especializados orquestrados por um agente raiz, utilizando modelos Gemini da Google.

## 🏗️ Arquitetura

O sistema adota uma arquitetura hierárquica de agentes:

-   **Root Agent (`cloudinha_agent`)**: O orquestrador principal. Ele analisa a intenção do usuário e delega a tarefa para o sub-agente mais apropriado.
-   **Sub-Agentes**:
    -   **`onboarding_agent`**: Responsável pelo acolhimento inicial, entender o momento do estudante e coletar informações básicas.
    -   **`match_agent`**: Especialista em buscar e recomendar oportunidades educacionais (Prouni, Sisu) alinhadas ao perfil do estudante.
-   **Ferramentas (Tools)**: Funções Python que permitem aos agentes interagir com o banco de dados e APIs externas.

## 📂 Estrutura do Projeto

```
cloudinha-agent/
├── src/
│   ├── agent/
│   │   ├── agent.py            # Definição dos agentes (Root e Sub-agents) e orquestração
│   │   └── util/               # Utilitários e prompts (instruções do sistema)
│   ├── tools/                  # Implementação das ferramentas do agente
│   │   ├── getStudentProfile.py
│   │   ├── updateStudentProfile.py
│   │   └── searchOpportunities.py
│   └── lib/                    # Bibliotecas auxiliares
├── .env                        # Variáveis de ambiente (Segredos)
├── requirements.txt            # Dependências do Python
└── README.md                   # Documentação
```

## 🚀 Como Executar

### Pré-requisitos

-   Python 3.10 ou superior
-   Chave de API do Google AI Studio (Gemini)
-   Acesso ao Supabase (se necessário para persistência)

### Instalação

1.  **Clone o repositório:**
    ```bash
    git clone <seu-repo-url>
    cd cloudinha-agent
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # Linux/Mac
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure o ambiente:**
    Crie um arquivo `.env` na raiz do projeto e defina suas chaves:
    ```env
    GOOGLE_API_KEY=sua_chave_aqui
    SUPABASE_URL=sua_url_supabase
    SUPABASE_KEY=sua_chave_supabase
    ```

### Executando o Agente

Com o ambiente ativado e configurado, você pode executar o agente utilizando a CLI do ADK.

### Integração com Frontend / WhatsApp

O agente expõe uma API REST em `http://localhost:8002/chat`.

**Payload esperado (POST):**
```json
{
  "chatInput": "Olá, Cloudinha!",
  "userId": "12345",  // ID do Supabase ou Telefone (WhatsApp)
  "history": []       // Opcional
}
```

> **Nota Importante:** O `server.py` injeta automaticamente o `userId` no contexto da mensagem para que o agente saiba quem é o usuário.

### Desenvolvimento Local (`adk web`)

Para iniciar a interface web de debug do agente:

```bash
adk web
```

Isso iniciará um servidor local onde você pode conversar com a Cloudinha e visualizar os traces.

**⚠️ Como testar identidade no `adk web`:**

Como o `adk web` ignora o `server.py`, a injeção automática de ID não acontece. Para testar ferramentas que dependem de usuário (ex: `getStudentProfile`), você deve simular a injeção manualmente no chat:

Digite: `context_user_id=SEU_ID_AQUI Olá Cloudinha!`

Exemplo: `context_user_id=123-teste Quero ver meu perfil`

## 🛠️ Ferramentas (Tools)

O agente possui acesso a ferramentas específicas para cumprir suas funções:

-   `getStudentProfile`: Recupera informações do perfil do estudante logado.
-   `updateStudentProfile`: Atualiza dados e preferências do estudante no banco de dados.
-   `searchOpportunities`: Realiza buscas avançadas por cursos e bolsas no catálogo.

## 🧠 Configuração de IA

O agente está configurado para utilizar o modelo `gemini-1.5-flash` para garantir respostas rápidas e alta capacidade de raciocínio. As instruções de sistema (prompts) de cada agente ficam localizadas em `src/agent/util/`.

## 🚧 Melhorias Futuras (Roadmap de Robustez)

Para tornar o agente pronto para produção em escala (Enterprise Grade), as seguintes evoluções estão planejadas:

1.  **Gerenciamento de Sessão Persistente**
    *   Substituir o armazenamento em memória por um banco de dados (Redis ou PostgreSQL).
    *   Garantir a continuidade da conversa mesmo após reinicializações do servidor.

2.  **Workflow Agents & Guardrails**
    *   Implementar agentes de fluxo (Workflow Agents) para processos determinísticos (ex: Onboarding passo-a-passo).
    *   Separar a camada de segurança (Guardrails) do modelo de linguagem principal para maior controle e menor custo.

3.  **Saídas Estruturadas (Structured Output)**
    *   Utilizar *Pydantic Models* para definir esquemas rígidos de resposta.
    *   Garantir que dados complexos (como listas de cursos) sejam entregues em JSON confiável para o Frontend renderizar.

4.  **Observabilidade**
    *   Implementar Tracing distribuído (OpenTelemetry).
    *   Configuração dinâmica de modelos via variáveis de ambiente para fácil fallback.
