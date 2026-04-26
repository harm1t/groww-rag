# Edge Cases — Mutual Fund FAQ Assistant

> **Purpose:** Comprehensive edge case catalog for testing and evaluation of the Mutual Fund FAQ Assistant. Use this document to guide test planning, regression testing, and quality assurance.

---

## Table of Contents

1. [Ingestion Pipeline Edge Cases](#1-ingestion-pipeline-edge-cases)
2. [Retrieval Layer Edge Cases](#2-retrieval-layer-edge-cases)
3. [Generation Layer Edge Cases](#3-generation-layer-edge-cases)
4. [Safety Layer Edge Cases](#4-safety-layer-edge-cases)
5. [Multi-Thread Chat Edge Cases](#5-multi-thread-chat-edge-cases)
6. [API Layer Edge Cases](#6-api-layer-edge-cases)
7. [General & Cross-Component Edge Cases](#7-general--cross-component-edge-cases)
8. [Performance & Scalability Edge Cases](#8-performance--scalability-edge-cases)
9. [Security & Privacy Edge Cases](#9-security--privacy-edge-cases)
10. [Data Quality Edge Cases](#10-data-quality-edge-cases)

---

## 1. Ingestion Pipeline Edge Cases

### 1.1 Scraping Service

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| I-001 | **HTTP 404 Not Found** | Source URL returns 404 | Log error, skip re-indexing, alert via monitoring |
| I-002 | **HTTP 500 Internal Server Error** | Source URL returns 500 | Retry with exponential backoff, log error, alert if all retries fail |
| I-003 | **Timeout** | HTTP request exceeds timeout (30s) | Retry with backoff, skip after max retries |
| I-004 | **Rate Limiting** | Source returns 429 Too Many Requests | Respect Retry-After header, delay accordingly |
| I-005 | **Empty Response** | HTTP 200 but response body is empty | Skip re-indexing, log warning |
| I-006 | **Malformed HTML** | Response is not valid HTML | Attempt to parse with lenient parser, log warning, skip if unparseable |
| I-007 | **JavaScript-Rendered Content** | Content requires client-side JS rendering | Document limitation, log warning, skip or use headless browser if configured |
| I-008 | **Blocked by Bot Detection** | Source blocks scraping (403, CAPTCHA) | Log error, alert, skip URL |
| I-009 | **SSL Certificate Error** | Source has invalid/expired SSL cert | Log error, skip URL (security measure) |
| I-010 | **Redirect Loop** | Source redirects infinitely | Detect loop (max redirects), log error, skip URL |
| I-011 | **Content Type Mismatch** | URL returns non-HTML (PDF, image, video) | Skip (HTML-only corpus), log warning |
| I-012 | **Encoding Issues** | Response has non-UTF-8 encoding | Attempt to detect encoding, fallback to common encodings, log warning |
| I-013 | **Large File** | HTML response exceeds size limit (e.g., 10MB) | Skip or truncate, log warning |
| I-014 | **Slow Response** | Response takes >30s but completes | Log warning, proceed with parsing |
| I-015 | **Network Partition** | No network connectivity | Fail gracefully, log error, alert |
| I-016 | **DNS Resolution Failure** | Cannot resolve hostname | Log error, skip URL |
| I-017 | **Content Hash Collision** | Different content produces same SHA-256 hash | Extremely rare, verify with secondary hash if needed |
| I-018 | **Hash Store Corruption** | Hash store file is corrupted or unreadable | Fail gracefully, reinitialize hash store, log error |
| I-019 | **Concurrent Scrape** | Multiple ingestion runs triggered simultaneously | Use file lock or database lock to prevent race conditions |
| I-020 | **Partial Content Update** | Only section of page changed (e.g., NAV updated) | Re-index entire page (current behavior), optimize for partial updates in future |

### 1.2 Chunking

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| I-021 | **Empty Content** | After stripping boilerplate, content is empty | Skip chunking, log warning |
| I-022 | **Content Too Short** | Content < 50 tokens | Skip or merge with adjacent content, log warning |
| I-023 | **Content Too Long** | Single section > 2000 tokens | Split into multiple chunks at logical boundaries |
| I-024 | **Table with Many Rows** | Table with 100+ rows | Preserve table as single unit or row-groups, maintain integrity |
| I-025 | **Nested Tables** | Tables within tables | Flatten or preserve structure based on chunking rules |
| I-026 | **Missing Table Headers** | Table without clear headers | Infer headers or log warning |
| I-027 | **Empty Tables** | Table with no data | Skip table, log warning |
| I-028 | **Duplicate Sections** | Same content appears multiple times | De-duplicate based on content hash |
| I-029 | **Special Characters** | Content with emojis, symbols, unicode | Preserve in chunks, handle encoding correctly |
| I-030 | **Code Blocks** | Content with code or JSON blocks | Preserve as-is, don't strip |
| I-031 | **Lists with Many Items** | UL/OL with 50+ items | Preserve as single chunk or split at logical boundaries |
| I-032 | **Headings Without Content** | H1-H6 tags with no following content | Skip or merge with next section |
| I-033 | **Inconsistent Heading Levels** | H1 followed by H3 (skipping H2) | Preserve as-is, log warning |
| I-034 | **Whitespace Issues** | Excessive whitespace or line breaks | Normalize whitespace in chunks |
| I-035 | **Metadata Extraction Failure** | Cannot extract scheme_id, scheme_name from content | Use default values from URL registry, log warning |
| I-036 | **Date Parsing Failure** | Cannot parse fetched_at date | Use current date, log warning |
| I-037 | **Chunk ID Collision** | Deterministic chunk ID collides with existing | Upsert behavior (update existing) |
| I-038 | **Chunk Size Variance** | Chunks vary widely in size (50-1000 tokens) | Accept within range, log extreme outliers |

### 1.3 Embedding

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| I-039 | **Model Download Failure** | Cannot download BGE model from Hugging Face | Fail gracefully, log error, alert |
| I-040 | **Model Load Timeout** | Model loading takes >5 minutes | Fail gracefully, log error, alert |
| I-041 | **CUDA/MPS Not Available** | GPU acceleration not available | Fall back to CPU, log warning |
| I-042 | **Out of Memory** | Embedding batch causes OOM | Reduce batch size, retry, or process individually |
| I-043 | **Empty Chunk List** | No chunks to embed | Skip embedding, log info |
| I-044 | **Chunk with No Text** | Chunk has empty or whitespace-only content | Skip embedding, log warning |
| I-045 | **Chunk Too Long for Model** | Chunk > 512 tokens (BGE limit) | Truncate or split, log warning |
| I-046 | **Embedding Dimension Mismatch** | Generated embedding not 384-dim | Fail validation, log error |
| I-047 | **Batch Processing Failure** | Batch embedding fails mid-batch | Retry individual chunks, log errors |
| I-048 | **Embedding Timeout** | Single chunk embedding takes >10s | Log warning, continue |
| I-049 | **Model Version Change** | BGE model version differs from previous | Re-embed all chunks (requires manual trigger) |
| I-050 | **Corrupted Model Cache** | Cached model file is corrupted | Redownload model, log warning |

### 1.4 Vector Store (Chroma Cloud)

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| I-051 | **Authentication Failure** | Invalid CHROMA_API_KEY | Fail gracefully, log error, alert |
| I-052 | **Connection Timeout** | Cannot connect to Chroma Cloud | Retry with backoff, fail after max retries |
| I-053 | **Collection Not Found** | Specified collection doesn't exist | Create new collection via get_or_create_collection |
| I-054 | **Collection Access Denied** | No permission to access collection | Fail gracefully, log error, alert |
| I-055 | **Upsert Rate Limit** | Chroma Cloud rate limits upserts | Retry with exponential backoff |
| I-056 | **Query Rate Limit** | Chroma Cloud rate limits queries | Retry with exponential backoff |
| I-057 | **Dimension Mismatch** | Collection expects different embedding dimension | Fail validation, require full re-index |
| I-058 | **Upsert Failure** | Single chunk upsert fails | Log error, continue with remaining chunks |
| I-059 | **Delete Failure** | Delete by source_url fails | Log error, stale chunks may remain |
| I-060 | **Empty Query Results** | Query returns no chunks | Return empty result, log warning |
| I-061 | **Large Result Set** | Query returns >1000 chunks | Apply limit, log warning |
| I-062 | **Corrupted Collection** | Collection data corrupted | Fail gracefully, alert, require manual intervention |
| I-063 | **Tenant/Database Not Found** | Specified tenant/database doesn't exist | Fail gracefully, log error, alert |
| I-064 | **Network Partition** | Cannot reach Chroma Cloud during query | Fail gracefully, return error to user |
| I-065 | **Index Corruption** | HNSW index corrupted | Rebuild index (manual), log error |

---

## 2. Retrieval Layer Edge Cases

### 2.1 Query Preprocessing

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| R-001 | **Empty Query** | User sends empty string | Return error or prompt for input |
| R-002 | **Whitespace-Only Query** | Query is only spaces/tabs | Treat as empty, return error |
| R-003 | **Very Long Query** | Query > 500 characters | Truncate or reject, log warning |
| R-004 | **Special Characters** | Query contains emojis, unicode | Preserve, handle encoding correctly |
| R-005 | **Mixed Case** | Query with inconsistent capitalization | Normalize to lowercase for matching |
| R-006 | **Typos in Scheme Name** | "Parag Parik Flexi Cap" instead of "Parag Parikh" | Attempt fuzzy matching, proceed with broad retrieval |
| R-007 | **Abbreviations** | "PPFAS" instead of "Parag Parikh Financial Advisory Services" | Expand if known, proceed with retrieval |
| R-008 | **Ambiguous Scheme Name** | "Large Cap" could match multiple schemes | Retrieve broadly, re-rank by relevance |
| R-009 | **No Scheme Mentioned** | Query doesn't mention any scheme | Retrieve from all schemes |
| R-010 | **Multiple Schemes Mentioned** | Query mentions "Flexi Cap and Large Cap" | Retrieve from both, merge results |
| R-011 | **Non-English Characters** | Query contains Hindi or other scripts | Handle encoding, proceed with retrieval |
| R-012 | **SQL Injection Attempt** | Query contains SQL patterns | Sanitize, log security warning |
| R-013 | **XSS Attempt** | Query contains script tags | Sanitize, log security warning |
| R-014 | **Query with URLs** | Query contains embedded URLs | Extract or strip, log warning |
| R-015 | **Query with Numbers** | Query with numeric values (e.g., "5000 SIP") | Preserve for matching |
| R-016 | **Question Mark Variants** | Multiple question marks or mixed punctuation | Normalize to single question mark |
| R-017 | **Follow-up Query** | "What about its NAV?" (refers to previous context) | Use context window for expansion |
| R-018 | **Pronoun References** | "it", "that", "this" without context | Use context window for expansion |

### 2.2 Embedding & Search

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| R-019 | **Embedding Model Not Loaded** | Model not initialized on first query | Lazy-load, handle delay |
| R-020 | **Embedding Timeout** | Query embedding takes >10s | Log warning, proceed or timeout |
| R-021 | **Embedding Failure** | Query embedding fails completely | Return error to user, log error |
| R-022 | **Zero Results** | Vector search returns no chunks | Return empty result, suggest browsing scheme page |
| R-023 | **Single Result** | Vector search returns 1 chunk | Use it, may be insufficient context |
| R-024 | **Many Low-Score Results** | All results have low cosine similarity (<0.5) | Log warning, return best results or suggest browsing |
| R-025 | **All Same Source** | All chunks from same source_url | Merge, single citation |
| R-026 | **Multiple Sources with Same Score** | Chunks from different sources with identical scores | Use tie-breaker (newer fetched_at) |
| R-027 | **Metadata Filter Too Restrictive** | Filter by scheme_id returns no results | Remove filter, retrieve broadly |
| R-028 | **Metadata Filter Invalid** | Filter with non-existent scheme_id | Return no results, log warning |
| R-029 | **Chroma Cloud Down** | Chroma Cloud unavailable during query | Return error to user, log error |
| R-030 | **Slow Query** | Vector search takes >5s | Log warning, continue |
| R-031 | **Query Embedding Dimension Mismatch** | Generated embedding not 384-dim | Fail validation, return error |
| R-032 | **Top-K Too Large** | Requested top_k exceeds available chunks | Return all available chunks |
| R-033 | **Top-K Too Small** | Requested top-k = 0 | Return empty result or use default |

### 2.3 Re-ranking

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| R-034 | **Rerank Model Not Loaded** | Cross-encoder not initialized | Skip reranking, use dense scores only |
| R-035 | **Rerank Timeout** | Reranking takes >10s | Log warning, skip or use partial results |
| R-036 | **Rerank Failure** | Reranking fails completely | Use dense scores, log error |
| R-037 | **Empty Chunk List** | No chunks to rerank | Return empty result |
| R-038 | **Single Chunk** | Only 1 chunk to rerank | Return as-is |
| R-039 | **Rerank Reverses Order** | Reranked order differs significantly from dense | Accept reranked order (intended behavior) |
| R-040 | **Scores Tied** | Multiple chunks have identical rerank scores | Use original order or tie-breaker |
| R-041 | **Negative Scores** | Rerank produces negative scores | Accept, normalize if needed |
| R-042 | **Score Explosion** | Rerank produces very high scores (>100) | Accept, log warning |

### 2.4 Merging & Source Selection

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| R-043 | **No Chunks to Merge** | Empty chunk list | Return empty result |
| R-044 | **All Chunks Same Source** | Single source_url | Merge into one MergedSource |
| R-045 | **Chunks from Different Sources** | Multiple source_urls | Merge by source_url, keep one citation |
| R-046 | **Conflicting Information** | Chunks disagree on a fact | Prefer newer fetched_at, or cite scheme page |
| R-047 | **Missing source_url** | Chunk metadata lacks source_url | Skip chunk, log warning |
| R-048 | **Invalid source_url** | source_url is not a valid HTTP(S) URL | Skip chunk, log warning |
| R-049 | **source_url Not on Allowlist** | source_url not in URL registry | Skip chunk or log warning (depending on policy) |
| R-050 | **Empty Context After Merge** | Merged chunks produce empty context_text | Return empty result |
| R-051 | **Context Too Long** | Merged context exceeds LLM input limit | Truncate or select top sources |
| R-052 | **No Primary Citation** | Cannot select single citation | Use highest-score source or scheme page URL |
| R-053 | **Citation URL Dead** | Selected citation URL returns 404 | Log warning, still use as citation (trust indexed data) |
| R-054 | **Fetched_at Missing** | Chunk lacks fetched_at timestamp | Use scrape run timestamp, log warning |

---

## 3. Generation Layer Edge Cases

### 3.1 LLM Generation

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| G-001 | **Empty Context** | No retrieved chunks for LLM | Return "Cannot find information, browse scheme page" |
| G-002 | **Insufficient Context** | Context doesn't answer the query | Return "Cannot find specific information, browse scheme page" |
| G-003 | **GEMINI_API_KEY Missing** | API key not configured | Return placeholder error, log error |
| G-004 | **GEMINI_API_KEY Invalid** | API key is invalid/expired | Return error, log error, alert |
| G-005 | **GEMINI Rate Limit** | Hit Gemini API rate limit | Retry with backoff, return error if exhausted |
| G-006 | **GEMINI Quota Exceeded** | Exceeded free tier quota | Return error, alert, upgrade quota |
| G-007 | **GEMINI Timeout** | LLM generation takes >30s | Timeout, return error |
| G-008 | **GEMINI Service Down** | Gemini API unavailable | Return error, log error, alert |
| G-009 | **Context Too Long** | Context exceeds model input limit | Truncate, log warning |
| G-010 | **Prompt Injection** | User tries to inject malicious prompt | Reject, log security warning |
| G-011 | **Model Hallucination** | LLM generates facts not in context | Post-validation should catch, retry |
| G-012 | **Model Refusal** | LLM refuses to answer (safety filter) | Return refusal or use fallback |
| G-013 | **Empty Response** | LLM returns empty string | Retry or use fallback |
| G-014 | **Non-English Response** | LLM responds in different language | Retry with English-only prompt |
| G-015 | **Malformed Response** | Response is not parseable text | Retry or use fallback |
| G-016 | **Temperature Not Respected** | Model ignores low temperature setting | Accept, log warning |
| G-017 | **Model Version Change** | Gemini API version changes | Test compatibility, update if needed |

### 3.2 Response Formatting

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| G-018 | **Response > 3 Sentences** | LLM generates 4+ sentences | Post-validation fails, retry |
| G-019 | **Response < 1 Sentence** | LLM generates no sentences | Retry or use fallback |
| G-020 | **No Citation** | Response lacks citation URL | Post-validation fails, retry |
| G-021 | **Multiple Citations** | Response has multiple URLs | Post-validation fails, retry |
| G-022 | **Invalid Citation** | Citation is not a valid URL | Post-validation fails, retry |
| G-023 | **Citation Not on Allowlist** | Citation URL not in URL registry | Post-validation fails, retry |
| G-024 | **Missing Footer** | Response lacks "Last updated" footer | Add footer automatically |
| G-025 | **Footer Date Missing** | Footer has no date | Use fetched_at from source |
| G-026 | **Footer Date Invalid** | Footer date is not parseable | Use current date, log warning |
| G-027 | **Response Contains Advice** | Response has "you should invest" | Post-validation fails, retry |
| G-028 | **Response Contains Comparison** | Response compares funds | Post-validation fails, retry |
| G-029 | **Response Contains Guarantee** | Response has "guaranteed returns" | Post-validation fails, retry |
| G-030 | **Response Has Emojis** | Response contains emojis | Remove or accept (per policy) |
| G-031 | **Response Has Markdown** | Response has markdown formatting | Strip or preserve (per policy) |
| G-032 | **Response Has Code** | Response has code blocks | Strip or preserve (per policy) |
| G-033 | **Response Has HTML** | Response has HTML tags | Strip, log warning |
| G-034 | **Response Has Profanity** | Response contains inappropriate language | Retry with stricter prompt |
| G-035 | **Response Too Short** | Response < 20 characters | Retry or use fallback |
| G-036 | **Response Too Long** | Response > 500 characters | Retry with shorter constraint |
| G-037 | **Response Has Numbers Without Context** | "45.67" without context | Retry with context requirement |
| G-038 | **Response Has Percentages** | "2.5%" without explanation | Accept for factual data |
| G-039 | **Response Has Currency** | "₹5000" without context | Accept for factual data |
| G-040 | **Max Retries Exceeded** | Validation fails after 3 retries | Use fallback safe response |

### 3.3 Post-Generation Validation

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| G-041 | **Sentence Count Detection Failure** | Cannot count sentences reliably | Use heuristic (periods, question marks) |
| G-042 | **URL Detection Failure** | Cannot detect URLs in response | Use regex, log warning |
| G-043 | **Forbidden Pattern False Positive** | Legitimate phrase flagged as forbidden | Add to allowlist, log warning |
| G-044 | **Forbidden Pattern False Negative** | Forbidden phrase not detected | Add to pattern list, log warning |
| G-045 | **Validation Timeout** | Validation takes >5s | Log warning, continue |
| G-046 | **Validation Logic Error** | Validation code crashes | Fail gracefully, use fallback |

---

## 4. Safety Layer Edge Cases

### 4.1 PII Detection

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| S-001 | **PAN Number** | Query contains "ABCDE1234F" | Detect, reject with PII refusal |
| S-002 | **PAN with Spaces** | "ABCDE 1234 F" | Detect, reject |
| S-003 | **PAN in Sentence** | "My PAN is ABCDE1234F" | Detect, reject |
| S-004 | **Aadhaar Number** | Query contains 12-digit Aadhaar | Detect, reject |
| S-005 | **Aadhaar with Dashes** | "1234-5678-9012" | Detect, reject |
| S-006 | **Account Number** | Query contains bank account number | Detect, reject |
| S-007 | **OTP** | Query contains "OTP is 123456" | Detect, reject |
| S-008 | **OTP with Context** | "My verification code is 123456" | Detect, reject |
| S-009 | **Email Address** | Query contains email | Detect, reject |
| S-010 | **Email with Context** | "Contact me at user@example.com" | Detect, reject |
| S-011 | **Phone Number** | Query contains phone number | Detect, reject |
| S-012 | **Phone with Country Code** | "+91 9876543210" | Detect, reject |
| S-013 | **Credit Card Number** | Query contains 16-digit card number | Detect, reject |
| S-014 | **False Positive - PAN-like** | "ABCDE" (not a PAN) | Should not trigger |
| S-015 | **False Positive - Numbers** | "12345" (not Aadhaar) | Should not trigger |
| S-016 | **False Positive - Dates** | "01-01-2025" (looks like PAN format) | Should not trigger |
| S-017 | **Obfuscated PII** | "PAN: A****1234" | Detect pattern, reject |
| S-018 | **PII in Response** | LLM generates PII in response | Post-validation should catch, retry |
| S-019 | **PII in Logs** | Logs contain PII | Redact or omit from logs |

### 4.2 Intent Routing

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| S-020 | **Advisory Query** | "Should I invest in this fund?" | Detect, refuse with educational link |
| S-021 | **Comparison Query** | "Which is better, Flexi Cap or Large Cap?" | Detect, refuse with educational link |
| S-022 | **Recommendation Query** | "Recommend a fund for me" | Detect, refuse with educational link |
| S-023 | **Performance Query** | "What are the returns?" | Detect, refuse with link to factsheet |
| S-024 | **Best Fund Query** | "What's the best PPFAS fund?" | Detect, refuse with educational link |
| S-025 | **Personal Situation** | "I am 45, should I invest?" | Detect, refuse with educational link |
| S-026 | **Tax Advice** | "How can I save tax?" | Detect, refuse with educational link |
| S-027 | **Out-of-Scope Query** | "What's the weather?" | Detect, refuse politely |
| S-028 | **False Positive - Factual** | "What is the expense ratio?" (looks like factual) | Should not refuse |
| S-029 | **False Positive - "Should"** | "What should I know before investing?" (factual) | Should not refuse |
| S-030 | **False Positive - "Better"** | "Is direct plan better?" (factual comparison) | Should not refuse |
| S-031 | **Ambiguous Query** | "Is it good?" | Refuse or ask for clarification |
| S-032 | **Mixed Intent** | "What is the NAV and should I buy?" | Refuse (advisory component) |
| S-033 | **Indirect Advisory** | "Would this fund suit my goals?" | Detect, refuse |
| S-034 | **Leading Question** | "Don't you think this is the best?" | Detect, refuse |
| S-035 | **Hypothetical** | "If I invest ₹10,000..." | Detect, refuse |
| S-036 | **False Negative - Advisory** | Advisory query not detected | Add pattern, log warning |

### 4.3 Refusal Handling

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| S-037 | **Refusal Too Long** | Refusal response > 3 sentences | Truncate to 3 sentences |
| S-038 | **Refusal Too Short** | Refusal response < 1 sentence | Expand to be more helpful |
| S-039 | **Refusal Rude** | Refusal sounds dismissive | Use polite template |
| S-040 | **Refusal Missing Educational Link** | No AMFI/SEBI link | Add default link |
| S-041 | **Refusal Invalid Link** | Educational link is broken | Use fallback link |
| S-042 | **Refusal No Context** | Refusal doesn't explain why | Add explanation |
| S-043 | **Refusal for Factual Query** | Factual query wrongly refused | False positive, fix routing |
| S-044 | **Refusal Template Missing** | Template file not found | Use hardcoded fallback |

---

## 5. Multi-Thread Chat Edge Cases

### 5.1 Thread Management

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| T-001 | **Thread ID Collision** | UUID collision (extremely rare) | Accept, SQLite will handle |
| T-002 | **Thread Not Found** | Query for non-existent thread_id | Return 404 |
| T-003 | **Empty Thread List** | No threads in database | Return empty list |
| T-004 | **Thread Limit Exceeded** | User tries to create 1000 threads | Accept or enforce limit (per policy) |
| T-005 | **Thread Deletion** | Delete thread with messages | Cascade delete messages |
| T-006 | **Thread Deletion Failure** | Delete fails partway | Rollback or mark for cleanup |
| T-007 | **Thread Creation Failure** | Cannot create thread (DB error) | Return error, log |
| T-008 | **Concurrent Thread Creation** | Multiple requests create threads simultaneously | WAL mode handles, ensure uniqueness |
| T-009 | **Thread Metadata Missing** | Thread lacks updated_at or created_at | Use current timestamp |
| T-010 | **Thread Message Count Wrong** | message_count doesn't match actual | Recalculate on query |

### 5.2 Message Management

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| T-011 | **Message to Non-Existent Thread** | Add message to thread_id that doesn't exist | Return 404 |
| T-012 | **Empty Message** | User sends empty message content | Reject or prompt for input |
| T-013 | **Message Too Long** | Message > 10,000 characters | Reject or truncate |
| T-014 | **Message with Special Chars** | Message with unicode, emojis | Preserve, handle encoding |
| T-015 | **Message Role Invalid** | Message role not "user" or "assistant" | Reject, log warning |
| T-016 | **Message Timestamp Missing** | Message lacks timestamp | Use current timestamp |
| T-017 | **Message ID Collision** | UUID collision (extremely rare) | Accept, SQLite will handle |
| T-018 | **Concurrent Message Add** | Multiple users add to same thread simultaneously | WAL mode handles |
| T-019 | **Message Retrieval Failure** | Cannot retrieve messages | Return error, log |
| T-020 | **Message Limit Too Small** | Request limit = 0 | Return empty or use default |
| T-021 | **Message Limit Too Large** | Request limit = 10000 | Cap at reasonable max |
| T-022 | **Messages Out of Order** | Messages not chronological by timestamp | Sort by timestamp before returning |

### 5.3 Context Window

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| T-023 | **Empty Context** | Thread has no messages | Return empty context |
| T-024 | **Single Message** | Thread has only 1 message | Return it as context |
| T-025 | **Context Window Too Small** | max_turns = 0 | Return empty or use default |
| T-026 | **Context Window Too Large** | max_turns = 100 | Cap at reasonable max |
| T-027 | **Incomplete Turn** | User message without assistant response | Include in context |
| T-028 | **Only Assistant Messages** | Thread has only assistant responses | Include in context |
| T-029 | **Only User Messages** | Thread has only user messages | Include in context |
| T-030 | **Context Expansion Failure** | Query expansion fails | Use original query |
| T-031 | **Context Expansion Adds PII** | Expanded context contains PII | PII detector should catch |

### 5.4 Concurrency

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| T-032 | **Simultaneous Thread Access** | Multiple users access same thread | WAL mode handles, no conflicts |
| T-033 | **Database Lock Timeout** | SQLite lock timeout exceeded | Return error, log |
| T-034 | **Database Corruption** | SQLite database corrupted | Fail gracefully, alert |
| T-035 | **WAL Mode Failure** | WAL mode not supported | Fall back to default journal mode |
| T-036 | **Connection Pool Exhaustion** | Too many concurrent connections | Queue or return error |
| T-037 | **Thread Isolation Failure** | Thread A sees Thread B's messages | Should not happen, investigate |
| T-038 | **Memory Leak** | Thread store grows unbounded | Monitor, implement cleanup |

---

## 6. API Layer Edge Cases

### 6.1 Endpoints

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| A-001 | **Health Check** | GET /health | Return 200 with status |
| A-002 | **Health Check Failure** | System unhealthy | Return 503 |
| A-003 | **Create Thread** | POST /threads | Return 201 with thread_id |
| A-004 | **Create Thread Failure** | Database error | Return 500 |
| A-005 | **List Threads** | GET /threads | Return 200 with thread list |
| A-006 | **List Threads with Limit** | GET /threads?limit=10 | Return 10 threads |
| A-007 | **List Threads Invalid Limit** | GET /threads?limit=-1 | Use default or return 400 |
| A-008 | **Get Messages** | GET /threads/{id}/messages | Return 200 with messages |
| A-009 | **Get Messages Invalid ID** | GET /threads/invalid-id/messages | Return 404 |
| A-010 | **Post Message** | POST /threads/{id}/messages | Return 200 with response |
| A-011 | **Post Message Invalid Thread** | POST /threads/invalid-id/messages | Return 404 |
| A-012 | **Post Message Empty Body** | POST without JSON body | Return 400 |
| A-013 | **Post Message Invalid JSON** | POST with malformed JSON | Return 400 |
| A-014 | **Post Message Missing Field** | POST without "content" field | Return 400 |
| A-015 | **Admin Reindex** | POST /admin/reindex | Return 200 if secret valid |
| A-016 | **Admin Reindex No Secret** | POST /admin/reindex without secret | Return 401 |
| A-017 | **Admin Reindex Invalid Secret** | POST /admin/reindex with wrong secret | Return 401 |
| A-018 | **Admin Reindex Not Configured** | ADMIN_REINDEX_SECRET not set | Return 503 |
| A-019 | **Root Endpoint** | GET / | Return HTML UI or JSON |
| A-020 | **Static File Not Found** | GET /static/nonexistent.html | Return 404 |

### 6.2 Request/Response

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| A-021 | **Missing Content-Type** | POST without Content-Type header | Assume JSON, or return 400 |
| A-022 | **Wrong Content-Type** | POST with text/plain instead of JSON | Return 400 |
| A-023 | **Large Payload** | POST with >1MB payload | Reject or limit |
| A-024 | **Malformed JSON** | JSON with syntax errors | Return 400 |
| A-025 | **Unexpected Fields** | JSON with extra fields | Ignore extras or return 400 |
| A-026 | **Null Values** | JSON with null for required fields | Return 400 |
| A-027 | **Wrong Data Types** | String where number expected | Return 400 |
| A-028 | **Response Timeout** | Request takes >60s | Timeout, return 504 |
| A-029 | **Response Too Large** | Response >10MB | Truncate or error |
| A-030 | **Debug Mode Disabled** | RUNTIME_API_DEBUG=0 | No debug field in response |
| A-031 | **Debug Mode Enabled** | RUNTIME_API_DEBUG=1 | Include debug field |
| A-032 | **CORS Error** | Cross-origin request blocked | Configure CORS headers |

### 6.3 Authentication & Authorization

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| A-033 | **No Auth Required** | API is public (current design) | Accept all requests |
| A-034 | **Rate Limiting** | Too many requests from one IP | Return 429 (if implemented) |
| A-035 | **IP Blocklist** | Blocked IP tries to access | Return 403 (if implemented) |
| A-036 | **Admin Secret Leaked** | ADMIN_REINDEX_SECRET exposed | Rotate secret, audit logs |

---

## 7. General & Cross-Component Edge Cases

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| G-001 | **First Run** | System started with empty database | Initialize with defaults |
| G-002 | **Configuration Missing** | .env file missing | Use defaults, log warnings |
| G-003 | **Configuration Invalid** | .env has invalid values | Fail gracefully, use defaults |
| G-004 | **Environment Variable Not Set** | Required env var not set | Fail gracefully with clear error |
| G-005 | **File Permissions** | Cannot write to data directory | Fail gracefully, log error |
| G-006 | **Disk Full** | Cannot write to disk | Fail gracefully, alert |
| G-007 | **Memory Exhausted** | OOM during operation | Fail gracefully, alert |
| G-008 | **CPU Exhausted** | High CPU usage | Log warning, continue |
| G-009 | **Dependency Version Mismatch** | Wrong version of a library | Fail or warn |
| G-010 | **Dependency Missing** | Required library not installed | Fail with clear error |
| G-011 | **Python Version Mismatch** | Wrong Python version | Fail with clear error |
| G-012 | **System Clock Drift** | Server time is incorrect | Use UTC, log warning |
| G-013 | **Timezone Issues** | Timezone handling errors | Use UTC everywhere |
| G-014 | **Locale Issues** | Locale-specific parsing errors | Use locale-independent parsing |
| G-015 | **Graceful Shutdown** | SIGTERM/SIGINT received | Complete in-flight requests, exit cleanly |
| G-016 | **Startup Failure** | Cannot start server | Fail with clear error |
| G-017 | **Hot Reload Error** | Code reload fails | Log error, continue with old code |
| G-018 | **Log Rotation Failure** | Cannot rotate logs | Continue with old log file |
| G-019 | **Log Disk Full** | Cannot write logs | Drop logs, alert |

---

## 8. Performance & Scalability Edge Cases

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| P-001 | **High Concurrent Users** | 1000 simultaneous users | System should handle gracefully |
| P-002 | **Spike in Requests** | Sudden 10x traffic spike | Queue or return 503 |
| P-003 | **Slow Query** | Retrieval takes >5s | Log warning, timeout after 30s |
| P-004 | **Slow Generation** | LLM generation takes >30s | Timeout, return error |
| P-005 | **Slow Scraping** | Scrape takes >60s | Timeout, skip URL |
| P-006 | **Large Database** | 1M chunks in vector store | Query performance should remain acceptable |
| P-007 | **Large Thread Count** | 10,000 threads in database | List threads should remain fast |
| P-008 | **Long Thread History** | Thread with 1000 messages | Context window should limit |
| P-009 | **Memory Bloat** | Process memory grows unbounded | Monitor, restart if needed |
| P-010 | **Connection Pool Exhaustion** | All DB connections in use | Queue or return error |
| P-011 | **Chroma Cloud Slow** | Chroma query latency spikes | Retry, return error if persistent |
| P-012 | **Gemini Slow** | Gemini API latency spikes | Retry, return error if persistent |
| P-013 | **Network Latency** | High network latency | Timeout appropriately |
| P-014 | **Cold Start** | First request after restart | May be slower, acceptable |
| P-015 | **Cache Miss** | No cached embeddings | Generate on-demand, acceptable latency |

---

## 9. Security & Privacy Edge Cases

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| SEC-001 | **SQL Injection** | Malicious input in thread_id | Parameterized queries prevent |
| SEC-002 | **XSS** | Malicious input in message content | Sanitize on output |
| SEC-003 | **CSRF** | Cross-site request forgery | Implement CSRF tokens (if auth added) |
| SEC-004 | **Secrets in Logs** | API keys logged | Redact or omit from logs |
| SEC-005 | **Secrets in Error Messages** | Error reveals secrets | Generic error messages |
| SEC-006 | **PII in Logs** | User PII logged | Redact or omit |
| SEC-007 | **Unencrypted Storage** | Sensitive data stored plaintext | Encrypt at rest (if applicable) |
| SEC-008 | **Unencrypted Transmission** | HTTP instead of HTTPS | Enforce HTTPS |
| SEC-009 | **Weak Authentication** | Weak password (if auth added) | Enforce strong passwords |
| SEC-010 | **Session Hijacking** | Session token stolen (if auth added) | Use secure cookies, HTTPS |
| SEC-011 | **DoS Attack** | Flood of requests | Rate limiting, IP blocking |
| SEC-012 | **Path Traversal** | Malicious file paths | Validate paths |
| SEC-013 | **Command Injection** | Malicious input in system calls | Use parameterized calls |
| SEC-014 | **Dependency Vulnerability** | Vulnerable library version | Update dependencies |
| SEC-015 | **Outdated SSL/TLS** | Weak cipher suites | Use modern TLS |

---

## 10. Data Quality Edge Cases

| ID | Edge Case | Description | Expected Behavior |
|---|---|---|---|
| DQ-001 | **Stale Data** | Data not refreshed in 7 days | Alert, manual refresh |
| DQ-002 | **Inconsistent Data** | NAV differs across sources | Log warning, use newest |
| DQ-003 | **Missing Critical Field** | Expense ratio not found | Return "Not available" |
| DQ-004 | **Corrupted Data** | Chunk has garbled text | Skip chunk, log warning |
| DQ-005 | **Duplicate Data** | Same chunk indexed twice | De-duplication should prevent |
| DQ-006 | **Outdated Scheme** | Scheme discontinued | Mark as inactive, skip |
| DQ-007 | **Scheme Name Changed** | Scheme renamed | Update URL registry |
| DQ-008 | **URL Changed** | Source URL moved | Update URL registry |
| DQ-009 | **Data Format Changed** | Source website redesign | Update scraper |
| DQ-010 | **No Data for Scheme** | Scheme page has no facts | Log warning, still index |
| DQ-011 | **Fetched_at in Future** | Timestamp is future date | Use current date, log warning |
| DQ-012 | **Fetched_at Too Old** | Data from years ago | Still valid if not changed |
| DQ-013 | **Hash Collision** | Different content same hash | Rare, verify with secondary hash |
| DQ-014 | **Metadata Inconsistent** | scheme_id doesn't match scheme_name | Use URL registry as source of truth |
| DQ-015 | **Source URL Dead** | Citation URL 404 | Log warning, still use (trust indexed data) |

---

## Testing Priority Matrix

| Priority | Edge Case Categories | Rationale |
|---|---|---|
| **P0** (Critical) | PII detection, Intent routing, Authentication, Secrets management | Security and compliance failures |
| **P1** (High) | Retrieval failures, Generation failures, API errors, Data quality | Core functionality |
| **P2** (Medium) | Performance, Concurrency, Edge formatting, Edge content types | User experience |
| **P3** (Low) | Log formatting, Minor UI issues, Non-critical warnings | Nice to have |

---

## Summary

This document catalogs **200+ edge cases** across all components of the Mutual Fund FAQ Assistant:

- **Ingestion Pipeline:** 65 cases (scraping, chunking, embedding, vector store)
- **Retrieval Layer:** 35 cases (preprocessing, search, reranking, merging)
- **Generation Layer:** 46 cases (LLM, formatting, validation)
- **Safety Layer:** 44 cases (PII detection, intent routing, refusal)
- **Multi-Thread Chat:** 38 cases (thread management, messages, context, concurrency)
- **API Layer:** 36 cases (endpoints, request/response, auth)
- **General:** 19 cases (configuration, system, logging)
- **Performance:** 15 cases (scalability, latency, resources)
- **Security:** 15 cases (injection, secrets, encryption)
- **Data Quality:** 15 cases (staleness, inconsistency, corruption)

**Total:** 328 edge cases

Use this catalog to:
- Plan comprehensive test suites
- Prioritize regression testing
- Guide quality assurance efforts
- Identify areas for improvement
- Evaluate system robustness
