# Chat Agent Platform

Multi-sector AI chat platform powered by **Google Gemini** with multilingual support (22 Indic languages + English, native or Roman script).

Six built-in personas — Retail, Education, Medical, Real Estate, Banking, Tourism — plus a **custom persona** engine that turns any free-text prompt into a working agent with an auto-generated UI.

---

## Architecture

```
User → Web UI / API → FastAPI
  → [Guardrails] → [Translate in?] → [Intent + RAG]
  → [Prompt Builder] → Google Gemini (chat_completion)
  → [Escalation check] → [Guardrails] → [Translate out?]
  → Response
  → [Redis memory] + [Postgres log] + [File + JSON logs]
```

External services:
- **Google Gemini** — LLM (via API key)
- **IndicTrans2 gateway** — translation (only used when the user picks a non-English language)
- **Redis** — session memory (24h TTL)
- **PostgreSQL** — conversation logs (optional; app runs without it)
- **ChromaDB** — local vector store for RAG documents

---

## Quick Start

### Prerequisites

- Python 3.11+
- A Google Gemini API key: https://aistudio.google.com/app/apikey
- Redis (recommended, for session memory)
- PostgreSQL (optional, only for persistent conversation logs)

### Setup

```bash
# 1. Clone + venv + deps
git clone <repo> && cd Conversational_Agents
python -m venv Agent_env
source Agent_env/bin/activate
pip install -r requirements.txt

# 2. Config — copy template and paste your Gemini key
cp .env.example .env
# then edit .env:
#   GEMINI_API_KEY=AIzaSy...your-real-key
#   GEMINI_MODEL=gemini-flash-latest   # or gemini-2.5-pro etc.

# 3. Start Redis (optional but recommended)
redis-server &

# 4. Run
python -m app.main
```

App starts on http://localhost:5000. Open in browser — redirects to the built-in test UI.

### Smoke test

```bash
curl http://localhost:5000/health
# {"status":"ok","llm_status":"connected","timestamp":"..."}

curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Where is my order #12345?","sector":"retail"}'
```

---

## API Endpoints

Full reference with `curl` examples: [API_DOCS.md](API_DOCS.md).

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/chat` | Send a message to any sector or custom persona |
| `DELETE` | `/api/session/{session_id}` | Clear conversation memory |
| `GET` | `/health` | Health check |
| `GET` | `/api/agents/sectors` | List built-in sectors |
| `GET` | `/api/agents/{sector}` | Get agent config |
| `POST` | `/api/documents/upload` | Upload docs to RAG knowledge base |
| `POST` | `/api/documents/search` | Test RAG retrieval |
| `POST` | `/api/persona/create` | Create a custom persona from a free-text prompt |
| `POST` | `/api/persona/{persona_id}/chat` | Chat directly with a custom persona (easy web-embed) |
| `GET` / `DELETE` | `/api/persona/{persona_id}` | Manage persona |
| `POST` / `GET` | `/api/tenants/` | Multi-tenant management |
| `GET` | `/api/analytics/summary` | Analytics (mock data unless Postgres is wired for queries) |
| Docs UI | `/docs` | Auto-generated Swagger |

---

## Multilingual chat

The `POST /api/chat` request accepts two language fields:

- **`src_lang`** (default `"auto"`) — source language of the user's message
- **`lang`** (default `"ENGLISH"`) — language the reply should be in

Translation runs **only when explicitly needed**:

| src_lang | lang | Translator calls |
|----------|------|------------------|
| `auto` | `ENGLISH` | **0** — Gemini handles input directly, replies in English |
| `HINDI` | `HINDI` | 2 — translate in + translate out |
| `auto` | `HINDI_Latn` | 1 — output translated to Hinglish (Roman script) |
| `ENGLISH` | `ENGLISH` | 0 — everything stays English |

Supported: 22 Indic languages (native script) + 10 Roman-script variants. See [API_DOCS.md](API_DOCS.md#8-language-codes) for the full list.

---

## Embed the chat widget

Drop this into any website:

```html
<script
    src="https://your-domain.com/ui/widget/chat-widget.js"
    data-api="https://your-domain.com"
    data-sector="retail"
    data-title="ShopEasy Support">
</script>
```

For a persona-specific embed:

```html
<script>
  const PERSONA_URL = "https://your-domain.com/api/persona/custom_a1b2c3d4/chat";
  async function ask(text, sessionId) {
    const r = await fetch(PERSONA_URL, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text, session_id: sessionId, lang: "ENGLISH"})
    });
    return r.json();
  }
</script>
```

---

## Tech Stack

- **FastAPI** — HTTP server
- **Google Gemini** — LLM (via API key, no GPU needed)
- **IndicTrans2 gateway** — translation service
- **ChromaDB** — vector store for RAG
- **Redis** — session memory (24h TTL)
- **PostgreSQL** — conversation logs (optional)
- **Rotating file logs** — text + JSONL in `logs/`

## Docs

- [API_DOCS.md](API_DOCS.md) — every endpoint with curl examples
- [TECH_DOCS.md](TECH_DOCS.md) — internal architecture and call graph
- [REFERENCE_GUIDE.md](REFERENCE_GUIDE.md) — setup, deployment, troubleshooting
- [ARCHITECTURAL_IMPROVEMENTS.txt](ARCHITECTURAL_IMPROVEMENTS.txt) — impact analysis for streaming / LangGraph / Prometheus / Alembic (not yet built)

## Known limitations

- Personas, tenants, and per-sector agent configs live in **in-memory dicts** — lost on restart (demo mode).
- API-key auth middleware exists but is **disabled** — anyone reachable can chat. Wire it in [app/main.py](app/main.py) when going live.
- Analytics endpoints return mock zeros — real Postgres queries not implemented.
- CORS is `*` — tighten before public deploy.

See [REFERENCE_GUIDE.md](REFERENCE_GUIDE.md#9-security--limitations) for the full list.
