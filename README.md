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

Para iniciar a interface web de debug do agente:

```bash
adk web
```

Isso iniciará um servidor local onde você pode conversar com a Cloudinha e visualizar os traces de execução, trocas de mensagens entre sub-agentes e chamadas de ferramentas.

## 🛠️ Ferramentas (Tools)

O agente possui acesso a ferramentas específicas para cumprir suas funções:

-   `getStudentProfile`: Recupera informações do perfil do estudante logado.
-   `updateStudentProfile`: Atualiza dados e preferências do estudante no banco de dados.
-   `searchOpportunities`: Realiza buscas avançadas por cursos e bolsas no catálogo.

## 🧠 Configuração de IA

O agente está configurado para utilizar o modelo `gemini-2.0-flash-exp` para garantir respostas rápidas e alta capacidade de raciocínio. As instruções de sistema (prompts) de cada agente ficam localizadas em `src/agent/util/`.
