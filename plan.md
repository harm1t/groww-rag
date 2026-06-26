# Plan: Add Jio BlackRock MF (14 URLs)

## Overview
Add Jio BlackRock as a second AMC alongside PPFAS. 14 new URLs, all indexed into the same
ChromaDB collection. No architectural changes — purely incremental additions to existing files.

**Corpus after:** ~7 (PPFAS) + 14 (Jio BlackRock) = 21 URLs → ~250–300 estimated chunks

---

## Step 1 — Confirm URL types before writing any code

Before touching any file, answer this:

> Are the 14 Jio BlackRock URLs **Groww scheme pages** (groww.in/mutual-funds/...) or **official
> Jio BlackRock AMC pages** (jioBlackrock.com / blackrock.com)?

| URL type | Chunker needed | source_type value |
|---|---|---|
| Groww pages | ✅ Already works (`GrowwPageChunker`) | `groww_scheme_page` |
| AMC / official pages | ⚠️ New `JioBlackRockChunker` required | `jio_blackrock_page` |

**If any URL is from the official AMC site → complete Step 1b before Step 2.**

### Step 1b (only if official AMC pages) — Add new chunker
- File: `src/ingestion/chunker.py`
- Add `JioBlackRockChunker` class with section patterns matching that site's layout
- Register it in `Chunker.strategies` dict under key `jio_blackrock_page`
- **Test it in isolation** before running the full pipeline

---

## Step 2 — Add URLs to the registry
- File: `src/ingestion/url_registry.py`
- Add 14 new entries, one per URL
- Required fields per entry:
  ```python
  {
      "url": "...",
      "source_type": "groww_scheme_page",   # or jio_blackrock_page if Step 1b
      "scheme_name": "Jio BlackRock <Name> Fund",
      "scheme_id": "jbr_<slug>",            # e.g. jbr_large_cap, jbr_flexi_cap
      "amc": "Jio BlackRock Mutual Fund",
      "category": "equity/debt/hybrid",
      "sub_category": "...",
  }
  ```
- Keep `scheme_id` short and consistent — it becomes the Chroma metadata key used for filtering

---

## Step 3 — Add URLs to the allowlist
- File: `src/generation/prompt_builder.py`
- Add all 14 URLs to `ALLOWLISTED_URLS`
- **This must be done before running ingestion** — if missed, the validator will reject every
  Jio BlackRock citation and return the fallback error (same bug we hit with Dynamic AA fund)

---

## Step 4 — Add scheme aliases to the query preprocessor
- File: `src/retrieval/query_preprocessor.py`
- Two changes:

  **4a. Add aliases to `SCHEME_ALIASES`** for each Jio BlackRock scheme:
  ```python
  # Jio BlackRock Large Cap (example)
  "jio blackrock large cap": "jbr_large_cap",
  "jbr large cap": "jbr_large_cap",
  "blackrock large cap": "jbr_large_cap",
  # ... one block per scheme
  ```

  **4b. Extend `_PPFAS_PATTERN` to also match Jio BlackRock** so confidence gets boosted to 1.0:
  ```python
  _AMC_PATTERN = re.compile(
      r"\b(ppfas|parag\s+parikh|jio\s+blackrock|blackrock|jbr)\b",
      re.IGNORECASE
  )
  ```
  Rename the variable from `_PPFAS_PATTERN` → `_AMC_PATTERN` and update its one usage in
  `_resolve_scheme()`.

---

## Step 5 — Bump top_k_dense
- File: `src/api/app.py` line 150
- Change: `Retriever(top_k_dense=10, top_k_final=3)`
- To:     `Retriever(top_k_dense=20, top_k_final=3)`

**Why:** Corpus goes from 86 → ~300 chunks. With `top_k_dense=10` you'd retrieve only ~3%
of the corpus per query. Raising to 20 keeps recall healthy without impacting latency.

---

## Step 6 — Run the ingestion pipeline
```bash
.venv/bin/python3 -m src.ingestion.run_pipeline
```
- Scrapes all 21 URLs (7 existing + 14 new)
- Existing PPFAS chunks will re-hash → skipped if unchanged / updated if content changed
- New Jio BlackRock chunks will be embedded and upserted to ChromaDB
- Verify the final chunk count in the pipeline summary log

---

## Step 7 — Smoke test (3 queries minimum)
Run these directly via curl or the chat UI:

1. `"What is the expense ratio of Jio BlackRock <scheme name>?"` → must return factual answer with Jio BlackRock URL
2. `"What is the minimum SIP for Jio BlackRock <scheme name>?"` → same
3. `"What is the NAV of Jio BlackRock <scheme name>?"` → same

Check for:
- [ ] Response contains correct data (not fallback text)
- [ ] `Source:` URL is a Jio BlackRock URL (not a PPFAS URL)
- [ ] `Last updated from sources:` date is present

---

## Step 8 — Update example questions in the UI (optional)
- File: `frontend/src/components/ChatInterface.tsx`
- The `QUESTIONS` array currently has 4 PPFAS-only examples
- Consider adding 1–2 Jio BlackRock example questions so users discover the new AMC

---

## File change summary

| File | Change | Required |
|---|---|---|
| `src/ingestion/url_registry.py` | Add 14 Jio BlackRock entries | ✅ Yes |
| `src/generation/prompt_builder.py` | Add 14 URLs to allowlist | ✅ Yes |
| `src/retrieval/query_preprocessor.py` | Add aliases + extend AMC pattern | ✅ Yes |
| `src/api/app.py` | Bump `top_k_dense` 10 → 20 | ✅ Yes |
| `src/ingestion/chunker.py` | New chunker (only if non-Groww URLs) | ⚠️ Conditional |
| `frontend/src/components/ChatInterface.tsx` | Add example questions | Optional |

**No changes needed to:** `orchestrator.py`, `intent_router.py`, `pii_detector.py`,
`retriever.py`, `generator.py`, `validator.py`, `thread_store.py`, `app.py` endpoints.

---

## Risk flags
- **Scheme name collision:** If Jio BlackRock has a "Large Cap" fund AND PPFAS has a "Large Cap"
  fund, a query like "what is the exit load of large cap fund?" will hit whichever scheme's alias
  is listed first in `SCHEME_ALIASES`. Make Jio BlackRock aliases always include "jio" or
  "blackrock" as a qualifier. The PPFAS aliases can stay as-is since they use "parag parikh"/"ppfas".

- **Missing allowlist entry:** The most common mistake — forgetting Step 3 causes the silent
  fallback error seen with the Dynamic AA fund. Do Step 3 before Step 6.

- **top_k_final=3 is tight for multi-scheme queries:** If a user asks a broad question without
  naming a scheme, the reranker picks 3 chunks from ~300. This is fine for single-scheme factual
  queries but may produce thin context for broad questions. No action needed now — revisit if
  users report incomplete answers.
