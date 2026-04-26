"""
Tests for Phase 4 — Chunking & Embedding.

Covers §9 (Chunk Validation & Quality Rules) from
docs/chunking-embedding-architecture.md:

  TestGrowwPageChunker  — section extraction from real-ish Groww text
  TestRecursiveChunker  — token-limit, overlap, separator hierarchy
  TestChunker           — routing, deterministic IDs, deduplication
  TestEmbedder          — BGE model, asymmetric prefixes, dim/norm checks
  TestVectorStore       — Chroma collection, upsert, query, delete
"""

import math
import os
import tempfile

import pytest

from src.ingestion.chunker import (
    MAX_TOKENS,
    MIN_TOKENS,
    Chunker,
    GrowwPageChunker,
    RecursiveChunker,
)


# ── Shared fixture ───────────────────────────────────────────────────────

BASE_METADATA = {
    "source_url": "https://groww.in/mutual-funds/parag-parikh-long-term-value-fund-direct-growth",
    "scheme_name": "Parag Parikh Flexi Cap Fund",
    "scheme_id": "ppfas_flexi_cap",
    "amc": "PPFAS Mutual Fund",
    "source_type": "groww_scheme_page",
    "last_scraped": "2026-04-25",
}

# Real-density Groww page text — each section has ≥50 words to pass MIN_TOKENS filter
GROWW_SAMPLE = """\
+18.51
%
3Y annualised
-0.44
%
1D 1M 6M 1Y 3Y 5Y All
NAV: 23 Apr '26
₹91.08
Min. for SIP
₹1,000
Fund size (AUM)
₹1,28,966.48 Cr
Expense ratio
0.79%
Rating
5
Expense ratio
A fee payable to a mutual fund house for managing your mutual fund investments.
It is the total percentage of a company's fund assets used for administrative,
management, advertising, and all other operational expenses of the fund.
Direct Plan Expense Ratio: 0.79% | Regular Plan Expense Ratio: 1.68%
Exit load
A fee payable to a mutual fund house for exiting a fund before completion of
a specified period from the date of investment. For units above 10% of the
investment, exit load of 2% if redeemed within 365 days and 1% if redeemed
after 365 days but on or before 730 days from allotment.
Stamp duty on investment:
0.005% from July 1st 2020. This is applicable on purchase of mutual fund units.
Tax implication
Returns are taxed at 20% if you redeem before one year. After 1 year, you are
required to pay LTCG tax of 12.5% on returns of Rs 1.25 lakh or more in a financial year.
Holdings (121)
Name Sector Instruments Assets
HDFC Bank Ltd. Financial Equity 7.96%
Power Grid Corporation Of India Ltd. Energy Equity 7.16%
Coal India Ltd. Energy Equity 6.11%
ICICI Bank Ltd. Financial Equity 5.03%
ITC Ltd. Consumer Staples Equity 5.00%
Bajaj Holdings Investment Ltd. Financial Equity 4.09%
Kotak Mahindra Bank Ltd. Financial Equity 4.02%
Alphabet Inc Class A Services Forgn. Eq 3.99%
Minimum investments
Min. for 1st investment ₹1,000
Min. for 2nd investment ₹1,000
Min. for SIP ₹1,000
Returns and rankings
Annualised returns Absolute returns
Name 3Y 5Y 10Y All
Fund returns +18.5% +17.4% +18.0% +18.6%
Category average Equity Flexi Cap +16.0% +15.6% +13.5%
Rank Equity Flexi Cap 25 12 1 --
Fund management
Rajeev Thakkar - May 2013 to Present
Mr. Thakkar is a Chartered Accountant, Cost Accountant, CFA, and CFP.
He has been associated with PPFAS AMC since 2013 and manages the Flexi Cap Fund.
Raunak Onkar - May 2013 to Present
Mr. Onkar is an MMS Finance from the University of Mumbai and serves as Associate Fund Manager.
Raj Mehta - Jan 2016 to Present
Mr. Mehta is a Fellow Member of ICAI and CFA Charter Holder.
Fund benchmark
NIFTY 500 Total Return Index
Investment Objective
The scheme aims to achieve long-term capital appreciation by investing primarily
in equity and equity related instruments across market capitalisation.
Fund house
PPFAS Mutual Fund
Rank total assets #23 in India
Total AUM ₹1,47,954.94 Cr
Date of Incorporation 10 Oct 2012
"""


# ═══════════════════════════════════════════════════════════════════════
#  GrowwPageChunker
# ═══════════════════════════════════════════════════════════════════════

class TestGrowwPageChunker:

    def setup_method(self):
        self.chunker = GrowwPageChunker()

    def test_produces_chunks(self):
        chunks = self.chunker.chunk(GROWW_SAMPLE, BASE_METADATA)
        assert len(chunks) >= 1

    def test_all_chunks_have_required_keys(self):
        chunks = self.chunker.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert "content" in c, "Missing 'content' key"
            assert "metadata" in c, "Missing 'metadata' key"
            assert "chunk_type" in c, "Missing 'chunk_type' key"

    def test_chunk_type_is_structured_or_recursive(self):
        chunks = self.chunker.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert c["chunk_type"] in ("structured", "recursive"), (
                f"Unexpected chunk_type: {c['chunk_type']}"
            )

    def test_section_key_is_set_in_metadata(self):
        chunks = self.chunker.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert "section" in c["metadata"], "Missing 'section' in chunk metadata"
            assert isinstance(c["metadata"]["section"], str)

    def test_source_url_propagated(self):
        chunks = self.chunker.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert c["metadata"]["source_url"] == BASE_METADATA["source_url"]

    def test_no_chunk_below_min_tokens(self):
        chunks = self.chunker.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert len(c["content"].split()) >= MIN_TOKENS, (
                f"Chunk below MIN_TOKENS ({MIN_TOKENS}): {c['content'][:80]}"
            )

    def test_very_short_content_yields_no_chunks(self):
        chunks = self.chunker.chunk("Too short", BASE_METADATA)
        assert chunks == []

    def test_oversized_section_is_re_split(self):
        # Generate a section that exceeds MAX_TOKENS
        huge_section = "expense ratio\n" + " ".join(["word"] * (MAX_TOKENS + 50))
        chunks = self.chunker.chunk(huge_section, BASE_METADATA)
        for c in chunks:
            assert len(c["content"].split()) <= MAX_TOKENS + 5, (
                "Oversized chunk not re-split"
            )


# ═══════════════════════════════════════════════════════════════════════
#  RecursiveChunker
# ═══════════════════════════════════════════════════════════════════════

class TestRecursiveChunker:

    def setup_method(self):
        self.chunker = RecursiveChunker(max_tokens=50, overlap_tokens=10, min_tokens=5)

    def test_short_text_is_one_chunk(self):
        text = " ".join(["word"] * 30)
        chunks = self.chunker.chunk(text, BASE_METADATA)
        assert len(chunks) == 1

    def test_long_text_is_split(self):
        text = " ".join(["word"] * 200)
        chunks = self.chunker.chunk(text, BASE_METADATA)
        assert len(chunks) > 1

    def test_no_chunk_exceeds_max_tokens(self):
        text = " ".join(["word"] * 300)
        chunks = self.chunker.chunk(text, BASE_METADATA)
        for c in chunks:
            assert len(c["content"].split()) <= 55  # small margin for overlap

    def test_chunk_type_is_recursive(self):
        text = " ".join(["word"] * 100)
        chunks = self.chunker.chunk(text, BASE_METADATA)
        for c in chunks:
            assert c["chunk_type"] == "recursive"

    def test_overlap_is_applied(self):
        # Build text with distinct words so overlap is detectable
        words = [f"w{i}" for i in range(120)]
        text = " ".join(words)
        chunks = self.chunker.chunk(text, BASE_METADATA)
        if len(chunks) > 1:
            # Last words of chunk[0] should appear at start of chunk[1]
            end_words = set(chunks[0]["content"].split()[-10:])
            start_words = set(chunks[1]["content"].split()[:10])
            assert end_words & start_words, "Overlap not applied between consecutive chunks"

    def test_chunks_below_min_tokens_are_discarded(self):
        # Very short text — all tokens below min_tokens threshold should be discarded
        text = "a b c d e f g"
        chunks = self.chunker.chunk(text, BASE_METADATA)
        # Either empty (all below min) or every returned chunk respects min_tokens
        for c in chunks:
            assert len(c["content"].split()) >= self.chunker.min_tokens


# ═══════════════════════════════════════════════════════════════════════
#  Chunker (router / orchestrator)
# ═══════════════════════════════════════════════════════════════════════

class TestChunker:

    def setup_method(self):
        self.router = Chunker()

    def test_groww_scheme_page_uses_groww_chunker(self):
        chunks = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        assert len(chunks) >= 1

    def test_unknown_source_type_uses_fallback(self):
        meta = {**BASE_METADATA, "source_type": "unknown_type", "scheme_id": "test"}
        long_text = " ".join(["word"] * 200)
        chunks = self.router.chunk(long_text, meta)
        assert all(c["chunk_type"] == "recursive" for c in chunks)

    def test_each_chunk_has_id(self):
        chunks = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert "id" in c and c["id"], "Chunk missing 'id'"

    def test_id_starts_with_scheme_id(self):
        chunks = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert c["id"].startswith(BASE_METADATA["scheme_id"])

    def test_ids_are_unique_within_run(self):
        chunks = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Duplicate IDs within the same run"

    def test_deterministic_ids_across_runs(self):
        """Same input must produce same IDs — required for idempotent Chroma upserts."""
        chunks1 = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        chunks2 = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        ids1 = [c["id"] for c in chunks1]
        ids2 = [c["id"] for c in chunks2]
        assert ids1 == ids2, "IDs are not deterministic across runs"

    def test_content_hash_is_set(self):
        chunks = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert "content_hash" in c and len(c["content_hash"]) == 16

    def test_deduplication_removes_identical_chunks(self):
        # Duplicate the content — should only produce unique chunks
        doubled = GROWW_SAMPLE + "\n" + GROWW_SAMPLE
        chunks = self.router.chunk(doubled, BASE_METADATA)
        hashes = [c["content_hash"] for c in chunks]
        assert len(hashes) == len(set(hashes)), "Duplicate chunks not removed"

    def test_chunk_index_in_metadata(self):
        chunks = self.router.chunk(GROWW_SAMPLE, BASE_METADATA)
        for c in chunks:
            assert "chunk_index" in c["metadata"]
            assert isinstance(c["metadata"]["chunk_index"], int)


# ═══════════════════════════════════════════════════════════════════════
#  Embedder  (requires sentence-transformers; marked slow)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestEmbedder:
    """Tests that load the BAAI/bge-small-en-v1.5 model (~130 MB)."""

    @pytest.fixture(scope="class")
    def embedder(self):
        from src.ingestion.embedder import Embedder
        return Embedder()

    def test_dimensions_are_384(self, embedder):
        assert embedder.dimensions == 384

    def test_embed_chunks_adds_embedding_key(self, embedder):
        chunks = Chunker().chunk(GROWW_SAMPLE, BASE_METADATA)
        embedded = embedder.embed_chunks(chunks)
        for c in embedded:
            assert "embedding" in c, f"Missing 'embedding' in chunk {c['id']}"

    def test_embedding_length_is_384(self, embedder):
        chunks = Chunker().chunk(GROWW_SAMPLE, BASE_METADATA)
        embedded = embedder.embed_chunks(chunks)
        for c in embedded:
            assert len(c["embedding"]) == 384

    def test_embedding_is_l2_normalized(self, embedder):
        chunks = Chunker().chunk(GROWW_SAMPLE, BASE_METADATA)
        embedded = embedder.embed_chunks(chunks)
        for c in embedded:
            norm = sum(v ** 2 for v in c["embedding"]) ** 0.5
            assert abs(norm - 1.0) < 0.01, f"Embedding not L2-normalized: norm={norm}"

    def test_no_nan_in_embeddings(self, embedder):
        chunks = Chunker().chunk(GROWW_SAMPLE, BASE_METADATA)
        embedded = embedder.embed_chunks(chunks)
        for c in embedded:
            assert not any(math.isnan(v) for v in c["embedding"]), "NaN in embedding"

    def test_embed_query_returns_384_float_list(self, embedder):
        vec = embedder.embed_query("What is the expense ratio?")
        assert isinstance(vec, list)
        assert len(vec) == 384
        assert all(isinstance(v, float) for v in vec)

    def test_query_embedding_is_normalized(self, embedder):
        vec = embedder.embed_query("What is the minimum SIP?")
        norm = sum(v ** 2 for v in vec) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_doc_and_query_prefix_differ(self, embedder):
        assert embedder.DOC_PREFIX != embedder.QUERY_PREFIX

    def test_similar_queries_have_high_cosine(self, embedder):
        v1 = embedder.embed_query("What is the expense ratio?")
        v2 = embedder.embed_query("What is the TER (expense ratio)?")
        sim = embedder.compute_similarity(v1, v2)
        assert sim > 0.85, f"Similar queries have low cosine similarity: {sim:.3f}"

    def test_dissimilar_queries_have_lower_cosine(self, embedder):
        v1 = embedder.embed_query("What is the expense ratio?")
        v2 = embedder.embed_query("Who is the fund manager?")
        sim = embedder.compute_similarity(v1, v2)
        # Should be lower than similar pair — not necessarily < 0
        assert sim < 0.99, "Dissimilar queries have unexpectedly high similarity"



# ═══════════════════════════════════════════════════════════════════════
#  VectorStore  (requires chromadb; uses in-memory EphemeralClient for unit tests)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestVectorStore:
    """Tests Chroma vector store logic using an in-memory EphemeralClient.

    No Chroma Cloud credentials are required \u2014 _build_client() is patched
    to return a local EphemeralClient so the full upsert/query/delete logic
    can be exercised without network access.
    """

    @pytest.fixture(scope="class")
    def store(self):
        """Patch VectorStore to use an EphemeralClient (no credentials needed)."""
        import chromadb
        from unittest.mock import patch
        from src.ingestion.vector_store import VectorStore

        ephemeral = chromadb.EphemeralClient()

        # Patch _build_client so VectorStore.__init__ uses the local client
        with patch("src.ingestion.vector_store._build_client", return_value=ephemeral):
            vs = VectorStore(collection_name="test_collection")
        return vs

    @pytest.fixture(scope="class")
    def embedded_chunks(self):
        from src.ingestion.embedder import Embedder
        chunks = Chunker().chunk(GROWW_SAMPLE, BASE_METADATA)
        return Embedder().embed_chunks(chunks)

    def test_initial_count_is_zero(self, store):
        assert store.count() == 0

    def test_upsert_increases_count(self, store, embedded_chunks):
        n = store.upsert_chunks(embedded_chunks)
        assert n == len(embedded_chunks)
        assert store.count() == len(embedded_chunks)

    def test_upsert_is_idempotent(self, store, embedded_chunks):
        before = store.count()
        store.upsert_chunks(embedded_chunks)
        assert store.count() == before, "Re-upsert should not increase count (idempotent)"

    def test_query_returns_results(self, store, embedded_chunks):
        from src.ingestion.embedder import Embedder
        query_vec = Embedder().embed_query("What is the expense ratio?")
        results = store.query(query_vec, n_results=3)
        assert "documents" in results
        assert len(results["documents"][0]) > 0

    def test_query_returns_distances(self, store, embedded_chunks):
        from src.ingestion.embedder import Embedder
        query_vec = Embedder().embed_query("expense ratio")
        results = store.query(query_vec, n_results=3)
        assert "distances" in results
        assert len(results["distances"][0]) > 0

    def test_query_n_results_capped_at_count(self, store):
        from src.ingestion.embedder import Embedder
        query_vec = Embedder().embed_query("test")
        results = store.query(query_vec, n_results=9999)
        assert len(results["documents"][0]) <= store.count()

    def test_delete_by_source_url(self, store, embedded_chunks):
        store.delete_by_source_url(BASE_METADATA["source_url"])
        assert store.count() == 0, "delete_by_source_url should remove all matching chunks"


# ── Credential validation (fast \u2014 no model load) ──────────────────────────

class TestVectorStoreCredentials:
    """Validates that VectorStore raises EnvironmentError when Chroma Cloud
    credentials are missing \u2014 ensures the CI job fails early with a clear message."""

    def test_missing_all_credentials_raises(self, monkeypatch):
        from src.ingestion.vector_store import _build_client
        monkeypatch.delenv("CHROMA_API_KEY", raising=False)
        monkeypatch.delenv("CHROMA_TENANT", raising=False)
        monkeypatch.delenv("CHROMA_DATABASE", raising=False)
        # Reload module-level constants by calling _build_client directly
        # (we must import after monkeypatching since env vars are read at import time)
        import importlib
        import src.ingestion.vector_store as vs_mod
        importlib.reload(vs_mod)
        with pytest.raises(EnvironmentError, match="CHROMA_API_KEY"):
            vs_mod._build_client()

    def test_partial_credentials_raises(self, monkeypatch):
        monkeypatch.setenv("CHROMA_API_KEY", "fake-key")
        monkeypatch.delenv("CHROMA_TENANT", raising=False)
        monkeypatch.delenv("CHROMA_DATABASE", raising=False)
        import importlib
        import src.ingestion.vector_store as vs_mod
        importlib.reload(vs_mod)
        with pytest.raises(EnvironmentError):
            vs_mod._build_client()
