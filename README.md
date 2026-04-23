# IntelliKnow KMS

AI-powered knowledge management system with multi-channel integrations (Telegram, Discord).

## Features

- **Multi-Channel Access** — Query your knowledge base from Telegram or Discord chat
- **Document Knowledge Base** — Upload PDF/DOCX documents; automatic parsing (MinerU / PaddleOCR-VL / local), chunking, and vectorization
- **Intent Classification** — AI classifies queries and routes them to the right intent space (HR, Legal, Finance, etc.)
- **Hybrid Search** — Combines full-text search (FTS5) and semantic vector search (sqlitevec) with configurable weights
- **Admin Dashboard** — Manage documents, intent spaces, integrations, and view analytics

## Tech Stack

| Layer          | Technology                                       |
|----------------|--------------------------------------------------|
| Frontend       | Vue 3 (TypeScript) + Vite + Naive UI            |
| Backend        | Python 3.10+ + FastAPI + SQLAlchemy             |
| AI             | OpenAI-compatible API (GPT-5, DeepSeek, etc.)   |
| Vector Store   | SQLite + sqlitevec                              |
| Full-Text Search | SQLite FTS5                                    |
| Bot SDKs       | python-telegram-bot, discord.py                  |

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
cp .env.example .env          # Fill in your values — see "Environment Variables" below
python -m venv .venv
source .venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download zh_core_web_sm  # FTS5 Chinese tokenization
python -m spacy download en_core_web_sm  # FTS5 English tokenization
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up --build
```

## Environment Variables

| Variable                | Description                              | Default                    |
|-------------------------|------------------------------------------|----------------------------|
| `ADMIN_USERNAME`         | Admin login username                     | `admin`                    |
| `ADMIN_PASSWORD_HASH`    | bcrypt hash of admin password            | —                          |
| `JWT_SECRET_KEY`         | Secret for signing JWTs                  | —                          |
| `OPENAI_API_KEY`         | Model API key                            | —                          |
| `OPENAI_BASE_URL`        | Model API base URL (for proxies/DeepSeek) | `https://api.openai.com/v1`|
| `DEFAULT_LLM_MODEL`       | Default chat model                       | `gpt-4o`                   |
| `DEFAULT_EMBEDDING_MODEL`| Embedding model                          | `text-embedding-3-small`   |
| `DEFAULT_EMBEDDING_DIM`  | Embedding dimensions                     | `1024`                     |
| `TELEGRAM_BOT_TOKEN`     | Telegram bot token                       | —                          |
| `DISCORD_BOT_TOKEN`      | Discord bot token                         | —                          |
| `HYBRID_WEIGHT_TEXT`     | FTS5 weight in hybrid search             | `0.3`                      |
| `HYBRID_WEIGHT_VECTOR`   | Vector weight in hybrid search           | `0.7`                      |
| `MINERU_API_TOKEN`       | MinerU API token (high-quality PDF/DOCX parsing) | —                 |
| `PADDLE_OCR_VL_API_TOKEN`| PaddleOCR-VL API token (the SOTA solution for PDF/DOCX parsing) | —                        |

## Integrations

### Telegram

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set `TELEGRAM_BOT_TOKEN` environment variable
3. The bot polls for messages automatically on startup

### Discord

1. Create a Discord application at [discord.com/developers](https://discord.com/developers)
2. Enable **Message Content Intent** under "Bot" settings
3. Set `DISCORD_BOT_TOKEN` environment variable
4. The bot responds when **mentioned** (single mention only; `@bot hello`)

## Document Parsing

Three document parsers are available. The factory selects the first available in priority order:

| Parser | Env Variable | Notes |
|--------|-------------|-------|
| **MinerU** | `MINERU_API_TOKEN` | High-quality document parsing via [mineru.net](https://mineru.net) |
| **PaddleOCR-VL** | `PADDLE_OCR_VL_API_TOKEN` | The SOTA solution for document parsing via [Baidu Cloud](https://cloud.baidu.com/doc/OCR/s/7mh8u7ruk) |
| **DocumentParser** | — | Fallback; local text extraction via `pypdf` / `python-docx` |

When neither token is set, the built-in `DocumentParser` is used — it extracts text directly from digitally-born PDFs and DOCX files without OCR capabilities.

## AI Usage Scenarios

### Intent Classification

When a user query arrives, the LLM classifies it into one of the configured intent spaces based on keywords and descriptions. Each intent space (HR, Legal, Finance, etc.) has associated documents that serve as context.

### Document Retrieval (RAG)

1. Query is embedded using the configured embedding model
2. Hybrid search runs across FTS5 (keyword) and sqlitevec (semantic) simultaneously
3. Results are merged with weighted scoring: `final = 0.3 * text_score + 0.7 * vector_score`
4. Top chunks are injected into the LLM prompt with the user's question to generate a cited answer

### User Feedback Loop

Admin can mark query responses as "correct" or "wrong" in the analytics dashboard. Classification accuracy is computed from feedback and displayed per intent space.

## Project Structure

```
backend/
├── api/v1/              # FastAPI route handlers
│   ├── admin.py         # KB, intent, integration management
│   ├── analytics.py     # Query logs, statistics
│   ├── auth.py          # JWT authentication
│   └── bot.py           # Telegram/Discord message handling
├── core/
│   ├── orchestrator.py      # RAG pipeline
│   ├── classifier.py        # Intent classification
│   ├── hybrid_retriever.py # FTS5 + vector hybrid search
│   ├── document_parser.py   # PDF/DOCX parsing (base)
│   ├── paddle_ocr_vl_parser.py  # PaddleOCR-VL cloud parser
│   ├── mineru_parser.py     # MinerU cloud parser
│   ├── parser_factory.py    # Parser selection by env token
│   ├── document_store.py    # SQLite storage
│   └── config.py            # Settings
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── services/
│   ├── llm_factory.py       # Unified LLM client
│   ├── telegram.py         # Telegram bot
│   ├── teams.py            # Teams bot
│   ├── discord.py           # Discord bot
│   └── integrations.py     # Aggregated integration status
└── main.py               # FastAPI app entry point

frontend/
└── src/
    ├── pages/          # Dashboard, Integrations, KB, Intents, Analytics
    ├── api/            # Axios API client
    └── App.vue
```

## Default Intent Spaces

The system creates these intent spaces on first startup:

| Name    | Description                               | Keywords                                           |
|---------|-------------------------------------------|----------------------------------------------------|
| General | General knowledge and common questions    | general, help, info                                |
| HR      | Human resources, policies, benefits       | hr, human resources, employee, benefits, policy    |
| Legal   | Legal matters, contracts, compliance      | legal, law, contract, compliance, regulation      |
| Finance | Financial matters, budgets, expenses      | finance, budget, expense, cost, accounting, payment|
