# Documentação Técnica: Fluxo do Cloudinha Agent

Este documento descreve o funcionamento técnico detalhado do `cloudinha-agent`, desde o recebimento de uma mensagem até a geração da resposta. A arquitetura é baseada no Google ADK (Agent Development Kit) e utiliza um padrão de orquestração de workflows e agentes especialistas.

## 1. Ciclo de Vida da Requisição (Flow Overview)

O fluxo principal acontece da seguinte forma:

1.  **Entrada (API)**: O servidor recebe um POST em `/chat`.
2.  **Processamento (Server)**: Validação de sessão e usuário.
3.  **Orquestração (Agent Loop)**: O `run_workflow` gerencia o estado e roteia para o agente ou workflow correto.
4.  **Streaming (Real-Time)**: O servidor inicia uma `StreamingResponse` (NDJSON) imediatamente.
5.  **Execução (Agents)**: Conforme o agente "pensa" ou usa ferramentas, eventos (`tool_start`, `tool_end`, `text`) são enviados ao cliente em tempo real.
6.  **Saída**: O Frontend consome o stream para exibir o feedback visual ("Processando...") e o texto progressivamente.

---

## 2. Detalhamento do Fluxo

### 2.1. Entrada: `server.py`
*   **Endpoint**: `POST /chat`
*   **Payload**: `ChatRequest` (`chatInput`, `userId`, `sessionId`).
*   **Arquitetura**: **Server-Sent Events / NDJSON Streaming**.
    *   Ao contrário de uma resposta JSON única, o servidor retorna um fluxo de dados.
    *   **Formato de Eventos**:
        *   `{"type": "tool_start", "tool": "nome_tool", ...}`
        *   `{"type": "tool_end", "tool": "nome_tool", "output": "..."}`
        *   `{"type": "text", "content": "parte do texto..."}`
*   **Validação**: Verifica se o usuário está autenticado e se a sessão é válida.
*   **Trigger**: Inicia o generator que itera sobre `run_workflow`.

### 2.2. Orquestração: `src/agent/workflow.py`
Esta é a "máquina central" do agente. É um loop de controle em Python que decide qual agente ou workflow deve processar a mensagem.

**Etapas do Loop:**

1.  **Autenticação**:
    *   Se não logado -> Retorna mensagem de bloqueio imediatamente.

2.  **Roteamento (Main Loop)**:
    *   O sistema verifica o estado do usuário via `getStudentProfileTool`.
    *   **Context Switching (RouterAgent)** (Passo 0):
        *   Um `RouterAgent` (modelo flash, ultra-rápido) analisa a mensagem antes de qualquer decisão.
        *   Se detectar mudança de intenção (ex: está no Match mas perguntou datas do Sisu), ele altera o `active_workflow` no banco **e na memória da execução atual** IMEDIATAMENTE.
        *   Se detectar comando de saída ("Sair", "Menu"), ele limpa o `active_workflow`.
    
    *   **Prioridade de Roteamento (Pós-Router)**:
        1.  **Onboarding**: Se `onboarding_completed` == False -> Ativa `onboarding_workflow` (Máquina de Estados).
        2.  **Match**: Se `active_workflow` == "match_workflow" -> Ativa `match_agent` (Agente Especialista).
        3.  **Specialized Agents**: 
            *   Se `active_workflow` == "sisu_workflow" -> Ativa `sisu_agent`.
            *   Se `active_workflow` == "prouni_workflow" -> Ativa `prouni_agent`.
        4.  **Default**: Se nenhum anterior -> Ativa `root_agent` (Generalista).

3.  **Aprendizado e Contexto (Dynamic Few-Shotting)**:
    *   Antes de invocar o agente selecionado, o sistema busca exemplos de conversas "ideais" no banco vetorial (`retrieve_similar_examples`).
    *   Esses exemplos são injetados dinamicamente no prompt do sistema, permitindo que o agente aprenda novas regras ou melhore o tom de voz sem alteração de código.

### 2.3. Workflows e Agentes

#### A. Onboarding Workflow (`src/agent/onboarding_workflow.py`)
Objetivo: Preencher o perfil inicial do aluno de forma fluida.
*   **Tipo**: Máquina de Estado com Agente (`WorkflowAgent`).
*   **Comportamento**:
    *   Verifica campos faltantes obrigatórios: **Nome**, **Idade**, **Cidade**, **Escolaridade**.
    *   Pergunta apenas o que falta.
    *   Persiste dados via `updateStudentProfileTool`.
*   **Conclusão**: Ao preencher todos os campos, marca `onboarding_completed = True`.

#### B. Match Agent (`src/agent/match_agent.py`)
Objetivo: Encontrar oportunidades de bolsa com alta precisão através de conversação natural.
*   **Tipo**: Agente Especialista (`LlmAgent`).
*   **Estado**: Ativado quando `active_workflow` é "match_workflow".
*   **Input**: Utiliza `updateStudentPreferencesTool` para capturar **Curso**, **Nota**, **Localização**, **Renda**, etc.
*   **Lógica**:
    *   Não segue um script rígido ("hardcoded steps").
    *   O agente decide quais perguntas fazer com base nas preferências que ainda faltam ou precisam de refinamento.
    *   Usa `suggestRefinementTool` para ajudar o usuário se a busca for muito ampla ou vazia.
    *   Usa `searchOpportunitiesTool` para buscar vagas reais no banco de dados.
    *   Usa `logModerationTool` para garantir segurança.

#### C. Agentes de Conhecimento (Sisu / Prouni)
*   **Papel**: Tira-dúvidas baseados em documentos oficiais (RAG).
*   **Ferramentas**:
    *   `getImportantDatesTool`: Consulta datas do calendário.
    *   `readRulesTool`: Lê os arquivos de regras atualizados (`regras_sisu.md`, etc).
    *   `smartResearchTool`: Busca semântica avançada nos documentos processados.
    *   `duckDuckGoSearchTool`: Fallback para informações de última hora na web.

#### D. Root Agent (`root_agent`)
*   **Papel**: Roteador conversacional, "chit-chat" e porta de entrada.
*   **Comportamento**: Acolhe o usuário. Se o usuário pedir algo específico, usa `updateStudentProfileTool` para setar o workflow correto, passando a bola para o especialista.

---

## 3. Ferramentas (Tools)

As ferramentas conectam o agente ao mundo exterior (Banco de Dados, APIs). Todas estão em `src/tools/`.

| Tool | Função | Side Effects |
| :--- | :--- | :--- |
| **`updateStudentProfileTool`** | Atualiza dados cadastrais (nome, idade) e flags de estado do usuário. | Escreve em `user_profiles`. |
| **`getStudentProfileTool`** | Lê dados do usuário e estado atual. | Leitura. |
| **`updateStudentPreferencesTool`** | Atualiza preferências de busca (curso, nota, filtros). Gatilha busca automática se necessário. | Escreve em `user_preferences`. |
| **`searchOpportunitiesTool`** | Busca vagas/bolsas no catálogo. | Leitura em `opportunities`. |
| **`suggestRefinementTool`** | Sugere melhorias na busca (ex: nota de corte próxima). | - |
| **`readRulesTool`** | Lê arquivos markdown de regras/conhecimento. | Leitura FS. |
| **`logModerationTool`** | Registra violações de segurança ou toxicidade. | Escreve em `moderation_logs`. |
| **`getImportantDatesTool`** | Consulta cronogramas. | Leitura. |
| **`smartResearchTool`** | RAG / Busca Vetorial nos documentos do Cloudinha. | Embeddings + Leitura. |
| **`duckDuckGoSearchTool`** | Busca na Web (Fallback). | Request Externo. |

---

## 4. Persistência de Dados

*   **Sessão (Chat History)**: Tabela `chat_messages` (Supabase).
*   **Estado do Usuário**: Tabela `user_profiles`. Armazena flags de workflow (`active_workflow`, `onboarding_completed`).
*   **Preferências**: Tabela `user_preferences`. Armazena critérios de busca do Match.
*   **Isolamento**: O campo `active_workflow` na tabela de mensagens permite reconstruir contexto.

## 5. Arquitetura de Aprendizado (Learning & Feedback)

O sistema implementa o "Virtuous Loop":
1.  **Feedback**: O sistema coleta feedback (implícito/explícito).
2.  **Curadoria**: Exemplos positivos são armazenados como "Golden Examples".
3.  **Injeção**: Durante o `run_workflow`, exemplos relevantes ao contexto atual são recuperados e injetados no prompt do agente, melhorando a performance continuamente sem deploy.

