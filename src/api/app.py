"""
FastAPI Application — Phase 9

REST API for the Mutual Fund FAQ Assistant.
Per §9.1: Endpoints for health, threads, messages, and admin reindex.
"""

import os
import threading
import time
from typing import TYPE_CHECKING, Any, Optional

# Load environment variables BEFORE any imports that might need them
from dotenv import load_dotenv
load_dotenv('.env')

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.threads import ContextManager, Message, MessageRole, Thread, ThreadStore

if TYPE_CHECKING:
    from src.safety.orchestrator import SafetyOrchestrator


# ── Pydantic Models ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str = "1.0.0"


class ThreadCreateResponse(BaseModel):
    """Response for thread creation."""
    id: str
    created_at: str
    updated_at: str
    message_count: int


class ThreadListResponse(BaseModel):
    """Response for thread list."""
    threads: list[ThreadCreateResponse]


class MessageResponse(BaseModel):
    """Response for a single message."""
    id: str
    thread_id: str
    role: str
    content: str
    timestamp: str
    retrieval_debug_id: Optional[str] = None


class MessagesListResponse(BaseModel):
    """Response for messages list."""
    messages: list[MessageResponse]


class UserMessageRequest(BaseModel):
    """Request for posting a user message."""
    content: str


class AssistantMessageResponse(BaseModel):
    """Response for assistant message (§9.2)."""
    assistant_message: str
    debug: Optional[dict] = None


class ReindexRequest(BaseModel):
    """Request for admin reindex."""
    secret: str


class ReindexResponse(BaseModel):
    """Response for admin reindex."""
    status: str
    message: str


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Mutual Fund FAQ Assistant API",
    description="Facts-only RAG assistant for PPFAS Mutual Fund information",
    version="1.0.0",
)

# Configure CORS — read extra origins from CORS_ORIGINS env var (comma-separated)
_cors_env = os.getenv("CORS_ORIGINS", "")
_allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
_allowed_origins += [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://groww-rag.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global State ───────────────────────────────────────────────────────────────

thread_store: Optional[ThreadStore] = None
context_manager: Optional[ContextManager] = None
retriever: Optional[Any] = None
generator: Optional[Any] = None
safety_orchestrator: Optional[Any] = None

_rag_ready = threading.Event()   # set when RAG init completes (success or failure)
_rag_init_started = False

# Debug mode flag (from env var) - read dynamically
def get_debug_mode() -> bool:
    return os.getenv("RUNTIME_API_DEBUG", "0") == "1"


# ── RAG background initializer ─────────────────────────────────────────────────

def _bg_init_rag() -> None:
    """Load the embedding model and connect to Chroma in a background thread.

    Starts immediately at app startup so the model is warm before the first
    user message arrives — avoiding the 90-second download on first request.
    Health check (/health) returns 200 instantly regardless.
    """
    import logging
    import traceback
    global retriever, generator, safety_orchestrator

    try:
        from src.retrieval.retriever import Retriever
        from src.generation.generator import Generator
        from src.safety.orchestrator import SafetyOrchestrator

        if not (os.getenv("CHROMA_API_KEY") and os.getenv("CHROMA_TENANT") and os.getenv("CHROMA_DATABASE")):
            logging.warning("[RAG] ChromaDB credentials not set — RAG disabled.")
            return

        logging.info("[RAG] Background init: loading embedding model + connecting to Chroma…")
        retriever = Retriever(top_k_dense=20, top_k_final=5)
        generator = Generator()
        safety_orchestrator = SafetyOrchestrator(retriever=retriever, generator=generator)
        logging.info("[RAG] Background init complete — ready to answer questions.")
    except Exception as e:
        logging.error(f"[RAG] Background init failed: {e}\n{traceback.format_exc()}")
        retriever = None
        generator = None
        safety_orchestrator = None
    finally:
        _rag_ready.set()


# ── Startup Event ───────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize thread store and kick off RAG loading in a background thread."""
    global thread_store, context_manager, _rag_init_started
    db_path = os.getenv("THREAD_DB_PATH", "data/threads.db")
    thread_store = ThreadStore(db_path)
    context_manager = ContextManager(thread_store)

    if not _rag_init_started:
        _rag_init_started = True
        t = threading.Thread(target=_bg_init_rag, daemon=True, name="rag-init")
        t.start()


def _ensure_rag_initialized() -> None:
    """Block until background RAG init finishes (max 3 min), then return."""
    if safety_orchestrator is not None:
        return
    import logging
    logging.info("[RAG] Waiting for background init to complete…")
    _rag_ready.wait(timeout=180)   # 3-minute ceiling; Cloudflare cuts at ~100 s anyway


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness check endpoint (§9.1)."""
    return HealthResponse(
        status="healthy",
        version="1.0.0"
    )


@app.post("/threads", response_model=ThreadCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_thread():
    """Create a new thread (§9.1)."""
    if not thread_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Thread store not initialized"
        )

    thread = thread_store.create_thread()
    return ThreadCreateResponse(
        id=thread.id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=thread.message_count
    )


@app.get("/threads", response_model=ThreadListResponse)
async def list_threads(limit: int = 50):
    """List all threads, most recently updated first (§9.1)."""
    if not thread_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Thread store not initialized"
        )

    threads = thread_store.list_threads(limit=limit)
    return ThreadListResponse(
        threads=[
            ThreadCreateResponse(
                id=t.id,
                created_at=t.created_at,
                updated_at=t.updated_at,
                message_count=t.message_count
            )
            for t in threads
        ]
    )


@app.get("/threads/{thread_id}/messages", response_model=MessagesListResponse)
async def get_messages(thread_id: str, limit: Optional[int] = None):
    """List messages in a thread (§9.1)."""
    if not thread_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Thread store not initialized"
        )

    # Verify thread exists
    thread = thread_store.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )

    messages = thread_store.get_messages(thread_id, limit=limit)
    return MessagesListResponse(
        messages=[
            MessageResponse(
                id=m.id,
                thread_id=m.thread_id,
                role=m.role.value,
                content=m.content,
                timestamp=m.timestamp,
                retrieval_debug_id=m.retrieval_debug_id
            )
            for m in messages
        ]
    )


@app.post("/threads/{thread_id}/messages", response_model=AssistantMessageResponse)
def post_message(thread_id: str, request: UserMessageRequest):
    """Post a user message and get assistant response (§9.1).

    Pipeline: User message → Safety Orchestrator (Phase 7) → Assistant message
    """
    try:
        return _post_message_impl(thread_id, request)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error in post_message: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


def _post_message_impl(thread_id: str, request: UserMessageRequest):
    _ensure_rag_initialized()

    if not thread_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Thread store not initialized"
        )

    # Verify thread exists
    thread = thread_store.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )

    # Store user message
    user_message = thread_store.add_message(
        thread_id=thread_id,
        role=MessageRole.USER,
        content=request.content
    )

    # Track latency for debug info
    start_time = time.time()

    # If safety orchestrator is not initialized, return a placeholder response
    if not safety_orchestrator:
        placeholder_response = (
            "The assistant is not fully configured. "
            "Please ensure the retriever and generator are properly initialized."
        )
        assistant_message = thread_store.add_message(
            thread_id=thread_id,
            role=MessageRole.ASSISTANT,
            content=placeholder_response
        )
        response_data = AssistantMessageResponse(assistant_message=placeholder_response)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Add debug info if enabled (§9.2)
        if get_debug_mode():
            response_data.debug = {
                "latency_ms": latency_ms,
                "was_refused": False,
                "refusal_reason": None,
                "orchestrator_initialized": False,
            }
        return response_data

    # Process through safety orchestrator
    # Fetch conversation history for context (last 8 messages = 4 turns)
    # Only fetch history if this is not the first message in the thread
    messages = thread_store.get_messages(thread_id, limit=8)
    
    # Only pass conversation history if there are previous messages (not the first message)
    if len(messages) > 1:
        conversation_history = [msg.content for msg in messages[:-1]]
        safety_result = safety_orchestrator.answer(request.content, conversation_history=conversation_history)
    else:
        safety_result = safety_orchestrator.answer(request.content)
    
    latency_ms = int((time.time() - start_time) * 1000)

    # Store assistant message
    assistant_message = thread_store.add_message(
        thread_id=thread_id,
        role=MessageRole.ASSISTANT,
        content=safety_result.response,
        retrieval_debug_id=f"latency_{latency_ms}ms" if get_debug_mode() else None
    )

    # Build response
    response_data = AssistantMessageResponse(assistant_message=safety_result.response)

    # Add debug info if enabled (§9.2)
    if get_debug_mode():
        debug_info = {
            "latency_ms": latency_ms,
            "was_refused": safety_result.was_refused,
            "refusal_reason": safety_result.refusal_reason if safety_result.was_refused else None,
        }
        if safety_result.generation_result:
            debug_info["validated"] = safety_result.generation_result.validation.passed
            debug_info["retries"] = safety_result.generation_result.retry_used
        response_data.debug = debug_info

    return response_data


@app.post("/admin/reindex", response_model=ReindexResponse)
async def admin_reindex(request: ReindexRequest):
    """Trigger re-ingestion pipeline (protected, §9.1).

    Requires ADMIN_REINDEX_SECRET to match environment variable.
    """
    expected_secret = os.getenv("ADMIN_REINDEX_SECRET")

    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin reindex not configured (no secret set)"
        )

    if request.secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret"
        )

    # In a real implementation, this would trigger the ingestion pipeline
    # For now, return a success response
    return ReindexResponse(
        status="success",
        message="Re-index triggered (placeholder - implement actual pipeline trigger)"
    )


_TICKER_FUNDS = {
    "ppfas_flexi_cap": "PPFAS Flexi Cap",
    "ppfas_large_cap": "PPFAS Large Cap",
    "ppfas_elss": "PPFAS ELSS",
    "ppfas_conservative_hybrid": "PPFAS Conservative Hybrid",
    "ppfas_arbitrage": "PPFAS Arbitrage",
    "ppfas_liquid": "PPFAS Liquid",
    "ppfas_dynamic_aa": "PPFAS Dynamic AA",
    "jbr_flexi_cap": "JBR Flexi Cap",
    "jbr_nifty_50": "JBR Nifty 50",
    "jbr_nifty_midcap_150": "JBR Nifty Midcap 150",
    "jbr_nifty_smallcap_250": "JBR Nifty Smallcap 250",
    "jbr_nifty_next_50": "JBR Nifty Next 50",
    "jbr_large_cap": "JBR Large Cap",
    "jbr_liquid": "JBR Liquid",
    "jbr_money_market": "JBR Money Market",
    "jbr_overnight": "JBR Overnight",
    "jbr_arbitrage": "JBR Arbitrage",
    "jbr_nifty_gsec_8_13": "JBR G-Sec 8-13Y",
    "jbr_short_duration": "JBR Short Duration",
    "jbr_low_duration": "JBR Low Duration",
    "jbr_sector_rotation": "JBR Sector Rotation",
}


@app.get("/ticker")
async def get_ticker():
    """Return NAV, AUM, expense ratio and min SIP for all funds (ticker tape)."""
    import json as _json
    import re as _re

    scraped_dir = "data/scraped"
    if not os.path.exists(scraped_dir):
        return {"items": []}

    batches = sorted(
        d for d in os.listdir(scraped_dir)
        if os.path.isdir(os.path.join(scraped_dir, d))
    )
    fund_data: dict = {}

    for batch in reversed(batches):
        batch_path = os.path.join(scraped_dir, batch)
        for fund_id, display_name in _TICKER_FUNDS.items():
            if fund_id in fund_data:
                continue
            file_path = os.path.join(batch_path, f"{fund_id}.json")
            if not os.path.exists(file_path):
                continue
            with open(file_path) as f:
                data = _json.load(f)
            content = data.get("content", "")

            nav_m    = _re.search(r'NAV:[^\n]*\n₹([\d,]+\.[\d]+)', content)
            change_m = _re.search(r'([+-][\d.]+)\n%\n1D', content)
            aum_m    = _re.search(r'Fund size \(AUM\)\n₹([\d,]+\.[\d]+ Cr)', content)
            exp_m    = _re.search(r'Expense ratio\n([\d.]+%)', content)
            sip_m    = _re.search(r'Min\. for SIP\n₹([\d,]+)', content)

            fund_data[fund_id] = {
                "name":          display_name,
                "nav":           f"₹{nav_m.group(1)}"    if nav_m    else None,
                "change":        change_m.group(1)        if change_m else None,
                "aum":           f"₹{aum_m.group(1)}"    if aum_m    else None,
                "expense_ratio": exp_m.group(1)           if exp_m    else None,
                "min_sip":       f"₹{sip_m.group(1)}"    if sip_m    else None,
            }

        if len(fund_data) == len(_TICKER_FUNDS):
            break

    # Build flat interleaved list: NAV → AUM → Expense Ratio → Min SIP per fund
    items = []
    for fund_id in _TICKER_FUNDS:
        if fund_id not in fund_data:
            continue
        fd = fund_data[fund_id]
        name = fd["name"]
        if fd["nav"]:
            items.append({"label": name, "metric": "NAV",
                          "value": fd["nav"], "change": fd["change"]})
        if fd["aum"]:
            items.append({"label": name, "metric": "AUM",
                          "value": fd["aum"], "change": None})
        if fd["expense_ratio"]:
            items.append({"label": name, "metric": "Expense Ratio",
                          "value": fd["expense_ratio"], "change": None})
        if fd["min_sip"]:
            items.append({"label": name, "metric": "Min SIP",
                          "value": fd["min_sip"], "change": None})

    return {"items": items}


@app.get("/")
async def root():
    """API information endpoint."""
    return {
        "name": "Mutual Fund FAQ Assistant API",
        "version": "1.0.0",
        "frontend": "Next.js UI (see /frontend directory)",
        "health": "/health",
        "ticker": "/ticker",
        "endpoints": {
            "threads": "/threads",
            "messages": "/threads/{id}/messages",
            "admin": "/admin/reindex",
            "ticker": "/ticker"
        }
    }
