# Mutual Fund FAQ Assistant

A facts-only RAG (Retrieval-Augmented Generation) chatbot that answers objective questions about mutual fund schemes from official AMC sources. Every response is grounded in scraped data, capped at three sentences, and includes a single verified citation. Investment advice and recommendations are explicitly refused.

**Covered AMCs:** PPFAS Mutual Fund (7 schemes) · JioBlackRock Mutual Fund (14 schemes)

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────┐
│  Intent Router (Phase 7)                │
│  Factual → continue  Advisory → refuse  │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Query Preprocessor (Phase 5)           │
│  Alias resolution · Query expansion     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Retriever (Phase 5)                    │
│  Dense top-20 → Reranker → top-3 chunks │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Generator (Phase 6)                    │
│  Groq llama-3.1-8b-instant · temp 0.1  │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Validator (Phase 6/7)                  │
│  Sentence limit · Citation check · PII  │
└─────────────────────────────────────────┘
```

See [`rag_architecture.md`](rag_architecture.md) for the full 14-section design document.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Embeddings** | `BAAI/bge-small-en-v1.5` (local, 384-dim) |
| **Vector DB** | ChromaDB (Chroma Cloud) |
| **LLM** | Groq API (`llama-3.1-8b-instant`) |
| **Scraping** | requests + BeautifulSoup4 |
| **Thread DB** | SQLite |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS |
| **Backend host** | Render (Singapore) |
| **Frontend host** | Vercel |
| **Scheduler** | GitHub Actions (daily 09:15 IST) |

---

## Project Structure

```
Groww/
├── src/
│   ├── api/            # FastAPI app and endpoints (Phase 9)
│   ├── ingestion/      # Scraping, chunking, embedding, indexing (Phase 4)
│   ├── retrieval/      # Query preprocessing, dense retrieval, reranking (Phase 5)
│   ├── generation/     # Prompt building, Groq calls, response validation (Phase 6)
│   ├── safety/         # Intent routing, PII detection, orchestrator (Phase 7)
│   └── threads/        # SQLite thread/message persistence (Phase 8)
├── frontend/           # Next.js 14 chat UI
├── data/
│   ├── raw/            # Raw HTML from scraping
│   ├── scraped/        # Normalised text chunks
│   ├── hashes.json     # SHA-256 change-detection registry
│   └── threads.db      # Conversation history
├── tests/              # Pytest suite — one module per phase
├── docs/               # Architecture and design documents
├── .github/workflows/  # Daily ingestion scheduler
├── .env.example        # Environment variable template
├── render.yaml         # Render deployment config
└── requirements.txt
```

---

## API Reference

Base URL: `https://<your-render-service>.onrender.com`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health and version |
| `POST` | `/threads` | Create a new chat thread |
| `GET` | `/threads` | List all threads |
| `GET` | `/threads/{id}/messages` | Fetch thread history |
| `POST` | `/threads/{id}/messages` | Send a query, receive a RAG answer |
| `POST` | `/admin/reindex` | Trigger full ingestion (admin-only) |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Chroma Cloud](https://trychroma.com) account
- A [Groq](https://console.groq.com) API key

### Backend

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Fill in CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE, GROQ_API_KEY

# 4. Run the ingestion pipeline (first-time, ~5–10 min)
python -m src.ingestion.run_pipeline

# 5. Start the API server
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Point the frontend at the local backend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
# Open http://localhost:3000
```

### Tests

```bash
pytest tests/ -v

# Run a single phase
pytest tests/test_phase9_api.py -v
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CHROMA_API_KEY` | Chroma Cloud API key | — |
| `CHROMA_HOST` | Chroma Cloud host | `api.trychroma.com` |
| `CHROMA_TENANT` | Chroma tenant name | — |
| `CHROMA_DATABASE` | Chroma database name | — |
| `GROQ_API_KEY` | Groq API key | — |
| `GROQ_MODEL` | LLM model ID | `llama-3.1-8b-instant` |
| `GROQ_TEMPERATURE` | Sampling temperature | `0.1` |
| `GROQ_MAX_TOKENS` | Max tokens per response | `300` |
| `EMBED_MODEL` | Sentence-transformers model | `BAAI/bge-small-en-v1.5` |
| `INGEST_CHROMA_COLLECTION` | Chroma collection name | `mf_faq_chunks` |
| `THREAD_DB_PATH` | SQLite path | `./data/threads.db` |
| `PORT` | Backend port | `8000` |
| `ADMIN_REINDEX_SECRET` | Guard for `/admin/reindex` | — |
| `NEXT_PUBLIC_API_URL` | Backend URL for frontend | `http://localhost:8000` |
| `CORS_ORIGINS` | Allowed CORS origins | Vercel deploy URL |

See `.env.example` for the full template.

---

## Deployment

### Backend — Render

1. Connect your GitHub repo in the Render dashboard.
2. Use `render.yaml` (already in the repo) — no extra config needed.
3. Set all secrets from the table above in **Render → Environment**.
4. Render auto-deploys on every push to `main`.

Start command (from `render.yaml`):
```
uvicorn src.api.app:app --host 0.0.0.0 --port $PORT
```

### Frontend — Vercel

1. Import the `frontend/` directory as a Vercel project.
2. Set `NEXT_PUBLIC_API_URL` to your Render service URL.
3. Vercel auto-deploys on every push to `main`.

### Data Refresh — GitHub Actions

`.github/workflows/scheduler.yml` runs `python -m src.ingestion.run_pipeline` every day at **09:15 IST (03:45 UTC)**. Trigger it manually from the **Actions** tab with `workflow_dispatch`.

Required GitHub secrets: `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`, `GROQ_API_KEY`.

---

## Adding a New Scheme

1. **`src/ingestion/url_registry.py`** — add an entry with `url`, `scheme_id`, `amc`, `category`.
2. **`src/generation/prompt_builder.py`** — add the URL to `ALLOWLISTED_URLS`.
3. **`src/retrieval/query_preprocessor.py`** — add aliases to `SCHEME_ALIASES`.
4. Re-run the pipeline: `python -m src.ingestion.run_pipeline`.

> **Note:** Changing the embedding model requires deleting the Chroma collection and re-ingesting all data.

---

## Safety & Compliance

- **No investment advice** — advisory queries are refused with a polite template and educational links.
- **Citation required** — every answer cites exactly one allowlisted source URL.
- **Response length** — capped at three sentences enforced by the post-generation validator.
- **PII redacted** — emails, phone numbers, Aadhaar, PAN, and OTP patterns are detected and redacted from logs.
- **Allowlist-only** — only the 21 pre-approved Groww scheme-page URLs are ever cited.

---

## Documentation

| File | Contents |
|---|---|
| [`rag_architecture.md`](rag_architecture.md) | End-to-end system design (14 sections) |
| [`chunking-embedding-architecture.md`](chunking-embedding-architecture.md) | Chunking strategy and embedding model details |
| [`data-storage-architecture.md`](data-storage-architecture.md) | Vector store, metadata schema, persistence |
| [`deployment.md`](deployment.md) | GitHub Actions, Render, and Vercel setup |
| [`edge_cases.md`](edge_cases.md) | Known limitations and troubleshooting |

---

## Known Limitations

- **Ephemeral threads on Render free tier** — conversation history resets on redeploy (mitigated by using `/tmp/threads.db`).
- **HTML-only corpus** — PDFs, videos, and audio are not ingested.
- **Narrow context window** — `top_k_final=3` may miss context for broad multi-scheme queries.
- **Scheme name collisions** — queries must use unambiguous aliases when PPFAS and JioBlackRock have similarly named funds.

See [`edge_cases.md`](edge_cases.md) for the full list.

---

## License

This project is intended for educational and internal use. Refer to the individual AMC websites for official scheme information.
