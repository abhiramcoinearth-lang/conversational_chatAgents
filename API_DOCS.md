# API_DOCS — Chat Agent Platform

Complete reference for every endpoint. Copy-pasteable `curl` examples for each one.

**Base URL** (local): `http://localhost:5000`
**Live Swagger UI**: `http://localhost:5000/docs`
**ReDoc**: `http://localhost:5000/redoc`

---

## Table of Contents

1. [Chat](#1-chat)
2. [Persona (Custom Agents)](#2-persona-custom-agents)
3. [Agents (Sector Configs)](#3-agents-sector-configs)
4. [Documents (RAG Knowledge Base)](#4-documents-rag-knowledge-base)
5. [Tenants](#5-tenants)
6. [Analytics](#6-analytics)
7. [Health & System](#7-health--system)
8. [Language Codes](#8-language-codes)
9. [Common Errors](#9-common-errors)
10. [Web Integration Recipes](#10-web-integration-recipes)

---

## 1. Chat

### `POST /api/chat`

Send a message to any built-in sector or custom persona.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `message` | string | ✅ | — | The user's message (1–4000 chars) |
| `session_id` | string | ❌ | auto | UUID; omit for first turn, then reuse |
| `sector` | string | ❌ | `"retail"` | `retail`, `education`, `medical`, `real_estate`, `banking`, `tourism`, or `custom_<id>` |
| `tenant_id` | string | ❌ | `null` | Multi-tenant identifier |
| `src_lang` | string | ❌ | `"auto"` | Source language of user's message |
| `lang` | string | ❌ | `"ENGLISH"` | Target language of the reply |

**Response:**

```json
{
  "reply": "string",
  "session_id": "string",
  "intent": "string|null",
  "confidence": "float|null",
  "sources": [{"doc_id": "...", "chunk_index": 0, "relevance": 0.92}] ,
  "escalated": false
}
```

**Example — English:**

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Where is my order #12345?","sector":"retail"}'
```

**Example — multi-turn (reuse session_id):**

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the courier name?","session_id":"abc-123","sector":"retail"}'
```

**Example — Hindi → Hinglish reply:**

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"मेरा ऑर्डर कहाँ है","sector":"retail","src_lang":"HINDI","lang":"HINDI_Latn"}'
```

### `DELETE /api/session/{session_id}`

Clear a chat's memory (Redis).

```bash
curl -X DELETE http://localhost:5000/api/session/abc-123
# → {"status":"cleared","session_id":"abc-123"}
```

---

## 2. Persona (Custom Agents)

### `POST /api/persona/create`

Create a custom agent from a free-text system prompt. The LLM extracts metadata automatically.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | ✅ | System prompt (10–2000 chars) defining the agent |
| `name` | string | ❌ | Optional display name (max 100 chars) |

**Response:**

```json
{
  "persona_id": "custom_a1b2c3d4",
  "name": "QuickKart Support",
  "agent_name": "Roopa",
  "company": "QuickKart",
  "description": "Customer support for electronics e-commerce",
  "services": [
    {"t": "Track Order", "h": 1},
    {"t": "Refund", "h": 0},
    {"t": "Returns", "h": 0},
    {"t": "Product Info", "h": 1}
  ],
  "prompt": "<original prompt text>"
}
```

`h: 1` = highlighted service (top button in UI). `h: 0` = regular.

**Example:**

```bash
curl -X POST http://localhost:5000/api/persona/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "QuickKart Support",
    "prompt": "You are Roopa, a customer support agent at QuickKart, an e-commerce platform for electronics. You handle order tracking, returns, refunds, and product inquiries. Be warm and solution-oriented. Keep responses under 3 sentences."
  }'
```

### `POST /api/persona/{persona_id}/chat` ⭐ **integration-friendly**

Chat with a specific persona. Same as `POST /api/chat` but the persona is implicit from the URL — perfect for embedding.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `message` | string | ✅ | — | User's message |
| `session_id` | string | ❌ | auto | For multi-turn |
| `tenant_id` | string | ❌ | `null` | Multi-tenant identifier |
| `src_lang` | string | ❌ | `"auto"` | Source language |
| `lang` | string | ❌ | `"ENGLISH"` | Reply language |

Note: **no `sector` field** — the persona is fixed by the URL.

**Response:** same shape as `POST /api/chat`.

**Example:**

```bash
curl -X POST http://localhost:5000/api/persona/custom_a1b2c3d4/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Where is my order?","lang":"ENGLISH"}'
```

### `GET /api/persona/list`

List all custom personas.

```bash
curl http://localhost:5000/api/persona/list
# → {"personas":[{...}], "total":3}
```

### `GET /api/persona/{persona_id}`

Get one persona's details.

```bash
curl http://localhost:5000/api/persona/custom_a1b2c3d4
```

### `DELETE /api/persona/{persona_id}`

Remove a custom persona.

```bash
curl -X DELETE http://localhost:5000/api/persona/custom_a1b2c3d4
# → {"status":"deleted","persona_id":"custom_a1b2c3d4"}
```

---

## 3. Agents (Sector Configs)

### `GET /api/agents/sectors`

List the 6 built-in sectors.

```bash
curl http://localhost:5000/api/agents/sectors
# → {"sectors":["retail","education","medical","real_estate","banking","tourism"],"total":6}
```

### `GET /api/agents/{sector}`

Get the full config for a sector (persona + intents).

```bash
curl http://localhost:5000/api/agents/retail
```

### `PUT /api/agents/{sector}`

Override a sector's config (in-memory, lost on restart).

```bash
curl -X PUT http://localhost:5000/api/agents/retail \
  -H "Content-Type: application/json" \
  -d '{
    "sector": "retail",
    "name": "Retail Agent",
    "system_prompt": "You are ...",
    "intents": []
  }'
```

### `GET /api/agents/{sector}/intents`

List intents available for a sector.

```bash
curl http://localhost:5000/api/agents/retail/intents
```

---

## 4. Documents (RAG Knowledge Base)

### `POST /api/documents/upload`

Upload a text file. Supported: `.txt`, `.md`, `.csv`. Chunked (500 words, 50 overlap) and stored in ChromaDB.

```bash
curl -X POST http://localhost:5000/api/documents/upload \
  -F "sector=retail" \
  -F "file=@product_catalog.txt"
# → {"status":"uploaded","doc_id":"retail_abc12345","filename":"product_catalog.txt","sector":"retail","chunks":12}
```

### `POST /api/documents/add-text`

Add raw text directly.

```bash
curl -X POST 'http://localhost:5000/api/documents/add-text?sector=retail&title=Return%20Policy&content=Returns%20accepted%20within%2015%20days...'
```

### `POST /api/documents/search`

Test retrieval (returns the chunks the LLM would receive).

```bash
curl -X POST 'http://localhost:5000/api/documents/search?sector=retail&query=warranty&top_k=3'
```

### `DELETE /api/documents/{sector}/{doc_id}`

Remove a document.

```bash
curl -X DELETE http://localhost:5000/api/documents/retail/retail_abc12345
```

---

## 5. Tenants

⚠️ In-memory only — lost on restart.

### `POST /api/tenants/`

Create a tenant + API key.

```bash
curl -X POST 'http://localhost:5000/api/tenants/?name=ShopEasy&sectors=retail'
# → {"tenant_id":"abc12345","api_key":"sk-...","message":"Save your API key — it won't be shown again."}
```

### `GET /api/tenants/`

List tenants.

```bash
curl http://localhost:5000/api/tenants/
```

### `GET /api/tenants/{tenant_id}`

Get one tenant.

```bash
curl http://localhost:5000/api/tenants/abc12345
```

### `PATCH /api/tenants/{tenant_id}/rate-limit`

Update rate limit.

```bash
curl -X PATCH 'http://localhost:5000/api/tenants/abc12345/rate-limit?rate_limit=600'
```

### `DELETE /api/tenants/{tenant_id}`

Deactivate a tenant.

```bash
curl -X DELETE http://localhost:5000/api/tenants/abc12345
```

---

## 6. Analytics

⚠️ Currently returns mock zeros. Wire up the `conversation_logs` PostgreSQL queries to enable real data.

### `GET /api/analytics/summary`

```bash
curl 'http://localhost:5000/api/analytics/summary?days=7'
```

### `GET /api/analytics/conversations`

```bash
curl 'http://localhost:5000/api/analytics/conversations?sector=retail&limit=20'
```

### `GET /api/analytics/intents`

```bash
curl 'http://localhost:5000/api/analytics/intents?sector=retail&days=7'
```

---

## 7. Health & System

### `GET /health`

Checks whether the LLM server is reachable.

```bash
curl http://localhost:5000/health
# → {"status":"ok","llm_status":"connected","timestamp":"2026-05-11T12:34:56"}
```

`llm_status: "disconnected"` means llama.cpp / Ollama isn't reachable.

### `GET /`

Redirects (307) to `/ui/test-ui.html`.

### `GET /api/me`

Stub — returns `{"authenticated": false}`. Only exists to silence browser extension polling.

---

## 8. Language Codes

Used in `src_lang` and `lang` fields.

### Native scripts

| Code | Language |
|---|---|
| `ENGLISH` | English |
| `HINDI` | Hindi (हिन्दी) |
| `BENGALI` | Bengali (বাংলা) |
| `TAMIL` | Tamil (தமிழ்) |
| `TELUGU` | Telugu (తెలుగు) |
| `KANNADA` | Kannada (ಕನ್ನಡ) |
| `MALAYALAM` | Malayalam (മലയാളം) |
| `MARATHI` | Marathi (मराठी) |
| `GUJARATI` | Gujarati (ગુજરાતી) |
| `PUNJABI` | Punjabi (ਪੰਜਾਬੀ) |
| `ODIA` | Odia (ଓଡ଼ିଆ) |
| `ASSAMESE` | Assamese (অসমীয়া) |
| `URDU` | Urdu (اُردُو) |
| `NEPALI` | Nepali |
| `KASHMIRI` | Kashmiri |
| `SINDHI` | Sindhi |
| `KONKANI` | Konkani |
| `MAITHILI` | Maithili |
| `MANIPURI` | Manipuri |
| `BODO` | Bodo |
| `DOGRI` | Dogri |
| `SANTALI` | Santali |

### Roman-script variants (for output rendering)

| Code | Example |
|---|---|
| `HINDI_Latn` | "Aapka order kahan hai?" |
| `TELUGU_Latn` | "Mee order ekkada undi?" |
| `TAMIL_Latn` | Tamil in Latin |
| `BENGALI_Latn` | Bengali in Latin |
| `KANNADA_Latn` | Kannada in Latin |
| `MALAYALAM_Latn` | Malayalam in Latin |
| `MARATHI_Latn` | Marathi in Latin |
| `GUJARATI_Latn` | Gujarati in Latin |
| `PUNJABI_Latn` | Punjabi in Latin |
| `ODIA_Latn` | Odia in Latin |

### Special value

- `auto` — Only valid for `src_lang`. Gateway auto-detects source language.

### Combinations

| `src_lang` | `lang` | Behavior |
|---|---|---|
| `ENGLISH` | `ENGLISH` | No translation (fastest) |
| `auto` | `ENGLISH` | Detect → English (no output translation) |
| `auto` | `HINDI` | Detect → English → Hindi |
| `HINDI` | `HINDI_Latn` | Hindi → English → Hinglish |
| `TELUGU_Latn` | `TELUGU` | Roman Telugu → English → native Telugu |

---

## 9. Common Errors

| HTTP | Cause | Fix |
|---|---|---|
| 422 | Validation — missing/invalid field | Check request body against spec above |
| 404 (persona) | `persona_id` doesn't exist | Create it first via `POST /api/persona/create` |
| 404 (sector) | Unknown sector | Use one of the 6 built-ins or a `custom_...` id |
| 500 | LLM not reachable | Check `curl http://localhost:8090/health`; restart llama-server |
| 503 | LLM service unavailable | Same — LLM is down |
| 500 (Redis auth) | Redis has password, not in config | Update `REDIS_URL` or disable auth |

Non-fatal warnings (visible in logs, chat still works):
- `translation failed` → gateway down, text passes through untranslated
- `PostgreSQL unavailable` → conversation logs not persisted, chat continues
- `Redis get_history failed` → session memory lost, chat still replies (no context)

---

## 10. Web Integration Recipes

### Recipe A — Embed a persona on any website

Once you've created a persona, hardcode its URL into an embed script:

```html
<!-- On your website -->
<div id="chat-container"></div>
<script>
const PERSONA_URL = "https://your-domain.com/api/persona/custom_a1b2c3d4/chat";
let sessionId = null;

async function ask(text) {
  const r = await fetch(PERSONA_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message: text, session_id: sessionId, lang: "ENGLISH"})
  });
  const d = await r.json();
  sessionId = d.session_id;
  return d.reply;
}
</script>
```

### Recipe B — Multilingual widget

Pass user's browser language as the reply target:

```javascript
const userLang = navigator.language.startsWith("hi") ? "HINDI"
               : navigator.language.startsWith("ta") ? "TAMIL"
               : "ENGLISH";

const r = await fetch(PERSONA_URL, {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({message: text, session_id: sessionId, src_lang: "auto", lang: userLang})
});
```

### Recipe C — Feed your knowledge base via curl

Batch-upload docs after `POST /api/persona/create`:

```bash
for f in docs/*.txt; do
  curl -X POST http://localhost:5000/api/documents/upload \
    -F "sector=custom_a1b2c3d4" \
    -F "file=@$f"
done
```

⚠️ RAG is currently only wired for **built-in sectors**. Custom personas skip the RAG step — they use the raw system prompt only. If you need RAG for a custom persona, you'd need to modify `chat.py` to run it for `custom_` sectors too.

### Recipe D — Track multi-turn sessions cleanly

Store the `session_id` in the browser's `localStorage`:

```javascript
let sessionId = localStorage.getItem("chatSession");

async function ask(text) {
  const r = await fetch(PERSONA_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message: text, session_id: sessionId})
  });
  const d = await r.json();
  if (d.session_id) {
    sessionId = d.session_id;
    localStorage.setItem("chatSession", sessionId);
  }
  return d.reply;
}

function newChat() {
  localStorage.removeItem("chatSession");
  sessionId = null;
}
```

---

*See [TECH_DOCS.md](TECH_DOCS.md) for internal architecture and [REFERENCE_GUIDE.md](REFERENCE_GUIDE.md) for setup/troubleshooting.*
