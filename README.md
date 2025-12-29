# 🤖 Nubo Hub - Agente Cloudinha (n8n)

Repositório para configuração e workflows do agente conversacional **Cloudinha**, construído com n8n para o projeto Nubo Hub.

## 📋 Sobre

A Cloudinha é um agente conversacional de IA que auxilia estudantes no processo de onboarding e descoberta de oportunidades educacionais através do Nubo Hub.

## 🌐 Ambiente Atual

**Estamos usando [n8n.io](https://n8n.io)** (versão cloud hospedada).

- ✅ Workflow já criado e funcionando
- ✅ Zero configuração de infraestrutura
- ✅ URL pública para webhooks
- 📝 Ver instruções de configuração em [`N8N_CONFIG.md`](./N8N_CONFIG.md)

## 🚀 Início Rápido

### Pré-requisitos

- Docker e Docker Compose instalados
- Porta 5678 disponível (ou configure outra no `.env`)

### 1. Configuração Inicial

1. Clone este repositório:
```bash
git clone <url-do-repo>
cd nubo-hub-agent-n8n
```

2. Copie o arquivo de exemplo de variáveis de ambiente:
```bash
cp .env.example .env
```

3. **IMPORTANTE**: Edite o arquivo `.env` e altere as senhas padrão:
```bash
# No Windows
notepad .env

# No Linux/Mac
nano .env
```

Altere pelo menos estas variáveis:
- `N8N_BASIC_AUTH_PASSWORD`
- `POSTGRES_PASSWORD`

### 2. Subir a Instância n8n

Execute o comando:

```bash
docker-compose up -d
```

Aguarde alguns segundos para os containers iniciarem. Você pode acompanhar os logs com:

```bash
docker-compose logs -f
```

### 3. Acessar o n8n

Abra seu navegador e acesse:

```
http://localhost:5678
```

Faça login com as credenciais definidas no `.env`:
- **Usuário**: valor de `N8N_BASIC_AUTH_USER` (padrão: `admin`)
- **Senha**: valor de `N8N_BASIC_AUTH_PASSWORD`

## 📁 Estrutura do Projeto

```
nubo-hub-agent-n8n/
├── docker-compose.yml          # Configuração Docker do n8n + PostgreSQL
├── .env.example                # Exemplo de variáveis de ambiente
├── .env                        # Suas variáveis (NÃO commitar!)
├── workflows/                  # Workflows do n8n (auto-sincronizados)
├── credentials/                # Credenciais (NÃO commitar!)
└── README.md                   # Este arquivo
```

## 🔧 Comandos Úteis

### Parar os serviços
```bash
docker-compose down
```

### Parar e remover volumes (CUIDADO: apaga dados!)
```bash
docker-compose down -v
```

### Ver logs
```bash
docker-compose logs -f n8n
docker-compose logs -f postgres
```

### Reiniciar apenas o n8n
```bash
docker-compose restart n8n
```

## 🔌 Integrações

### Supabase

Para integrar com Supabase, adicione no `.env`:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua-chave-anon
SUPABASE_SERVICE_ROLE_KEY=sua-chave-service-role
```

Depois, configure as credenciais no n8n através da interface web.

### OpenAI / Anthropic

Para usar modelos de IA, adicione no `.env`:

```env
OPENAI_API_KEY=sk-...
# ou
ANTHROPIC_API_KEY=sk-ant-...
```

Configure as credenciais correspondentes no n8n.

## 📚 Próximos Passos

1. ✅ Subir instância n8n (você está aqui!)
2. ⏳ Criar workflow de onboarding da Cloudinha
3. ⏳ Integrar com Supabase
4. ⏳ Criar componente de webchat no Nubo Hub
5. ⏳ Testar fluxo completo de onboarding

## 🆘 Troubleshooting

### Porta 5678 já está em uso

Altere a porta no `.env`:
```env
N8N_PORT=5679
```

E reinicie os containers.

### Erro de conexão com PostgreSQL

Verifique se o container do PostgreSQL está saudável:
```bash
docker-compose ps
```

Se estiver "unhealthy", veja os logs:
```bash
docker-compose logs postgres
```

### Esqueci a senha do n8n

1. Pare os containers: `docker-compose down`
2. Edite o `.env` com uma nova senha
3. Suba novamente: `docker-compose up -d`

## 📝 Licença

Projeto Nubo Hub - Velez Reyes Foundation

## 👥 Contato


## 🛠️ Servidor MCP (Ferramentas da Cloudinha)

O diretório também contém um **Servidor MCP** que expõe ferramentas para o agente Clouinha (e outros clientes MCP) interagirem com o banco de dados do Nubo.

### Ferramentas Disponíveis

1.  `search_opportunities`: Busca cursos e vagas (Sisu/Prouni).
2.  `get_student_profile`: Retorna perfil e preferências do aluno.
3.  `update_student_profile`: Atualiza dados do aluno.

### Como rodar o servidor MCP

#### Localmente (Dev)

```bash
npm install
npm dev
```

#### Docker

O servidor possui seu próprio `Dockerfile` para ser executado isoladamente ou composto.

```bash
docker build -t cloudinha-mcp .
docker run --env-file .env cloudinha-mcp
```
