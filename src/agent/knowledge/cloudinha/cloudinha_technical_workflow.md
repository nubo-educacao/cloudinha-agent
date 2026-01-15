# Documentação Técnica: Fluxo do Cloudinha Agent

Este documento descreve o funcionamento técnico detalhado do `cloudinha-agent`, desde o recebimento de uma mensagem até a geração da resposta. A arquitetura é baseada no Google ADK (Agent Development Kit) e utiliza um padrão de orquestração de workflows.

## 1. Ciclo de Vida da Requisição (Flow Overview)

O fluxo principal acontece da seguinte forma:

1.  **Entrada (API)**: O servidor recebe um POST em `/chat`.
2.  **Processamento (Server)**: Validação de sessão e usuário.
3.  **Orquestração (Agent Loop)**: O `run_workflow` gerencia o estado e roteia para o agente correto.
4.  **Streaming (Real-Time)**: O servidor inicia uma `StreamingResponse` (NDJSON) imediatamente.
5.  **Execução (Sub-Agents)**: Conforme o agente "pensa" ou usa ferramentas, eventos (`tool_start`, `tool_end`, `text`) são enviados ao cliente em tempo real.
6.  **Saída**: O Frontend cosome o stream para exibir o feedback visual ("Processando...") e o texto progressivamente.

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
*   **Validação**: Same as before.
*   **Resiliência**:
    *   A conexão mantida aberta (Keep-Alive) evita timeouts em requisições longas de RAG/Pensamento.
    *   Erros são retornados como evento `{"type": "error"}` dentro do stream.
*   **Trigger**: Inicia o generator que itera sobre `run_workflow`.

### 2.2. Orquestração: `src/agent/workflow.py`
Esta é a "máquina central" do agente. Ela não é um LLM, mas um loop de controle em Python.

**Etapas do Loop:**

1.  **Autenticação**:
    *   Se não logado -> Retorna mensagem de bloqueio imediatamente.

2.  **Guardrails (Segurança)**:
    *   Cria uma sessão transiente `guardrails-check`.
    *   Executa o `guardrails_agent` para analisar o input.
    *   Se classificado como `UNSAFE` -> Retorna mensagem de bloqueio e encerra.
    *   Se `SAFE` -> Prossegue.

3.  **Roteamento (Main Loop)**:
    *   O sistema verifica o estado do usuário via `getStudentProfileTool`.
    *   **Passo 0: Context Switching (RouterAgent)**:
        *   Um `RouterAgent` (leve, flash model) analisa a mensagem antes de qualquer decisão.
        *   Se detectar mudança de assunto (ex: está no Match mas perguntou de Sisu), ele altera o `active_workflow` no banco **e na memória da execução atual** IMEDIATAMENTE (mitigando latência de banco).
        *   Se detectar comando de saída ("Sair"), ele limpa o `active_workflow`.
    *   **Prioridade de Roteamento (Pós-Router)**:
        1.  **Onboarding**: Se `onboarding_completed` == False -> Ativa `onboarding_workflow`.
        2.  **Match**: Se `active_workflow` == "match_workflow" -> Ativa `match_workflow`.
        3.  **Specialized Agents**: 
            *   Se `active_workflow` == "sisu_workflow" -> Ativa `sisu_agent`.
            *   Se `active_workflow` == "prouni_workflow" -> Ativa `prouni_agent`.
        4.  **Default**: Se nenhum anterior -> Ativa `root_agent`.

4.  **Context Isolation**:
    *   O `workflow.py` atualiza a tag `active_workflow` na sessão do banco de dados antes de processar a mensagem. Isso garante que o histórico de chat seja "particionado" ou tagueado corretamente para análises futuras.

### 2.3. Workflows (Máquinas de Estado)

Diferente de agentes puramente conversacionais, os Workflows (`WorkflowAgent`) impõem uma sequência rígida de passos.

#### A. Onboarding Workflow (`src/agent/onboarding_workflow.py`)
Objetivo: Preencher o perfil inicial do aluno de forma fluida.
*   **Lógica**: Agente único (`onboarding_agent`) com conversação dinâmica ("Loose Mode").
*   **Comportamento**:
    *   Verifica o estado atual do perfil (`get_profile_state`).
    *   Identifica campos faltantes: **Nome**, **Idade**, **Cidade**, **Escolaridade**.
    *   Pergunta apenas o que falta, aceitando múltiplos dados em uma única mensagem.
    *   Persiste dados via `updateStudentProfileTool`.
*   **Conclusão**: A função de condição `check_profile_complete` monitora se os 4 campos obrigatórios foram preenchidos para finalizar o workflow (`onboarding_completed = True`).

#### B. Match Workflow (`src/agent/match_workflow.py`)
Objetivo: Encontrar oportunidades de bolsa com alta precisão.
*   **Lógica**: Coleta preferências refinadas, verifica elegibilidade financeira e expande opções geograficamente.
*   **Passos**:
    1.  **Basic Prefs (Smart Step)**: 
        *   Coleta 4 pontos de dados: **Curso**, **Nota ENEM**, **Turno Preferido** (Mat/Vesp/Not/Int) e **Tipo de Instituição** (Pública/Privada).
        *   Tenta extrair tudo da primeira mensagem, perguntando apenas o que faltar.
        *   Executa `searchOpportunitiesTool` com os filtros iniciais.
    2.  **Socioeconomic (Income Calculator)**: 
        *   Instrui o usuário a usar o componente de UI `IncomeCalculator` (via Client-Side Tool ou Tag).
        *   Recebe `income_per_capita`.
        *   Calcula elegibilidade (Prouni Integral <= 1.5 SM, Parcial <= 3.0 SM, Sisu > 3.0 SM).
        *   Filtra buscas subsequentes baseado na elegibilidade.
    3.  **Refinement (Geo & Quality)**: 
        *   **Geografia**: Verifica flexibilidade para outras cidades/regiões próximas.
        *   **Qualidade**: Ordena resultados finais priorizando qualidade MEC (`sort_by='quality'`).
*   **Conclusão**: Define `active_workflow = None` para retornar ao Root Agent.

### 2.4. Agentes Especialistas

#### Root Agent (`root_agent`)
*   **Papel**: Roteador conversacional e "chit-chat".
*   **Comportamento**: Analisa a intenção livre do usuário. Se o usuário pedir algo específico (ex: "Quero ajuda com o Sisu"), o Root Agent pode usar `updateStudentProfileTool` para setar `active_workflow="sisu_workflow"`.
*   **Efeito**: Na próxima iteração do loop (ou continuidade imediata), o `workflow.py` detectará a mudança e passará a bola para o agente especialista.

#### Sisu / Prouni Agents
*   **Papel**: Tira-dúvidas (RAG).
*   **Ferramentas**:
    *   `getImportantDatesTool`: Consulta datas do calendário (PRIORIDADE 1).
    *   `knowledgeSearchTool`: Busca na base vetorial de documentos (PRIORIDADE 2).
    *   `duckDuckGoSearchTool`: Busca na Web como fallback (PRIORIDADE 3).
    *   **Lógica de "Tool Cascade"**: O agente é instruído a seguir estritamente essa ordem de prioridade para evitar alucinações. Se a base interna não tiver a resposta, ele recorre à internet.

#### Router Agent (`src/agent/router_agent.py`)
*   **Papel**: Classificador de Intenção.
*   **Input**: Mensagem do Usuário + Estado Atual.
*   **Output**: JSON `{intent: "CHANGE_WORKFLOW", target: "sisu_workflow"}`.
*   **Diferencial**: Detecta mudanças implícitas de contexto (perguntas fora do escopo atual) e explícitas (comandos de saída).

---

## 3. Ferramentas (Tools)

As ferramentas conectam o agente ao mundo exterior (Banco de Dados, APIs). Todas estão em `src/tools/`.

> **Nota de UX**: A execução de cada ferramenta emite um evento `tool_start` e `tool_end`. No Frontend, isso é renderizado como um indicador de progresso ("Consultando seu perfil...", "Buscando datas..."), aumentando a transparência para o usuário.

| Tool | Função | Inputs | Side Effects |
| :--- | :--- | :--- | :--- |
| **`updateStudentProfileTool`** | Atualiza dados do usuário | `user_id` (str), `updates` (dict) | Escreve na tabela `user_profiles`. |
| **`getStudentProfileTool`** | Lê dados do usuário | `user_id` (str) | N/A (Leitura). Use para decidir roteamento. |
| **`searchOpportunitiesTool`** | Busca vagas/bolsas | `query` (str), `filters` (dict: cidade, nota, renda, turno, tipo_inst), `sort_by` (quality) | N/A (Leitura no DB `opportunities`). Inclui sanitização de input contra SQL Injection. |
| **`knowledgeSearchTool`** | RAG (Busca semântica) | `query` (str), `collection` (prouni/sisu) | Embeds query (Async via `google-genai`) e busca na tabela `documents`. |
| **`getImportantDatesTool`** | Calendário | N/A | Lê CSV `important_dates.csv` da memória/disco. |
| **`duckDuckGoSearchTool`** | Busca Web | `query` (str) | Realiza busca no DuckDuckGo (backend `api`) para fallback. |
| **`logModerationTool`** | Segurança | `user_id`, `reason`, `message` | Insere registro na tabela `moderation_logs`. |

---

## 4. Persistência de Dados

*   **Sessão (Chat History)**: Gerenciada pelo `SupabaseSessionService` (`src/agent/memory/supabase_session.py`). As mensagens são salvas na tabela `chat_messages`.
*   **Estado do Usuário**: Tabela `user_profiles`. Armazena flags de workflow (`active_workflow`, `onboarding_completed`) e dados demográficos.
*   **Isolamento**: O campo `active_workflow` na tabela de mensagens permite reconstruir em qual contexto uma conversa aconteceu.

## 5. Exemplo de Trace (Happy Path - Match)

1.  **Usuário**: "Quero achar uma faculdade."
2.  **Server**: Recebe request.
3.  **Workflow**:
    *   `onboarding_completed` é True.
    *   `active_workflow` é None.
    *   Executa **Root Agent**.
4.  **Root Agent**:
    *   Interpreta intenção de busca.
    *   Chama `updateStudentProfileTool(updates={"active_workflow": "match_workflow"})`.
    *   Responde: "Claro! Vamos encontrar a melhor opção para você."
5.  **Workflow (Loop)**:
    *   Detecta mudança para `match_workflow`.
    *   Instancia `Match Workflow`.
    *   Identifica passo 1 (`basic_prefs`).
    *   Executa `basic_prefs_agent`.
6.  **Match Agent**:
    *   Pergunta: "Qual curso você quer e qual sua nota do Enem?"
7.  **Usuário**: "Direito, tirei 700."
8.  **Match Agent**:
    *   Chama `updateStudentProfileTool`.
    *   Chama `searchOpportunitiesTool`.
    *   Retorna resultados.

---

## 6. Arquitetura de Aprendizado (Learning & Feedback)

O sistema implementa um ciclo de melhoria contínua (Virtuous Loop) baseado em três pilares, conforme especificado em `nubo-ops/specs/learning_agent_feedback_loops.md`.

### 6.1. Ciclos de Feedback
1.  **Explícito (Human-in-the-Loop)**: Captura de "Joinha/Dedo para baixo" na interface. Feedback negativo gera alertas para revisão.
2.  **Implícito (Sinais)**: Monitoramento de CTR (cliques em cards) e abandono de fluxo para inferir a qualidade do match.
3.  **Algorítmico (LLM-as-a-Judge)**: Processo em batch que utiliza um modelo superior (ex: Gemini 1.5 Pro) para auditar conversas e extrair "Golden Examples".

### 6.2. Aplicação do Conhecimento
*   **Dynamic Few-Shotting**: Exemplos de alta qualidade (curados humana ou automaticamente) são indexados e injetados dinamicamente no prompt do agente.
*   Isso permite que o agente "aprenda" novas regras ou corrija comportamentos sem alteração imediata de código (Code-less updates).
