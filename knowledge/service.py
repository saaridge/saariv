"""Index once, search many times; provider and answering model remain independent."""

import hashlib
import json
import logging
import threading
import time
import uuid

from .chunking import chunk_document
from .embeddings import ProviderError, create_provider, validate_vectors
from .store import KnowledgeStore


class ReindexRequired(RuntimeError):
    pass


class KnowledgeService:
    def __init__(self, settings, provider=None):
        self.settings = settings
        self.provider = provider if provider is not None else create_provider(settings)
        self.store = KnowledgeStore(settings.data_dir)
        self.lock = threading.RLock()
        self.metrics = {"cache_hits": 0, "embedded_chunks": 0, "searches": 0}
        if self.provider:
            stored_dimension = self.store.dimension(settings.profile_id)
            if stored_dimension:
                self.provider.dimension = stored_dimension

    def close(self):
        with self.lock:
            self.store.close()

    def _prepare(self, owner, document_id, text, title, source_type, metadata):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Please provide document text.")
        if not isinstance(document_id, str) or not document_id or len(document_id) > 160:
            raise ValueError("Document ID must contain 1 to 160 characters.")
        if len(text) > 2_000_000:
            raise ValueError("A document may contain at most 2 million characters.")
        title = str(title or "Experience story")[:300]
        metadata = dict(metadata or {})
        digest = json.dumps([text, title, source_type, metadata], ensure_ascii=False, sort_keys=True)
        version = hashlib.sha256(digest.encode()).hexdigest()[:24]
        version_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{owner}:{document_id}:{version}"))
        doc = dict(document_id=document_id, text=text, title=title, source_type=source_type,
                   metadata=metadata, version=version, version_key=version_key)
        chunks = chunk_document(text, title, metadata, self.settings.chunk_size, self.settings.chunk_overlap)
        if not chunks:
            raise ValueError("Please include document paragraphs, not just headings.")
        for chunk in chunks:
            chunk["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL,
                f"{version_key}:{chunk['start']}:{chunk['end']}:{chunk['section']}"))
            chunk["document_id"] = document_id
            chunk["version_key"] = version_key
            chunk["source"] = {key: chunk[key] for key in ("start", "end", "section", "page_start", "page_end")}
            chunk["source"].update(title=title, source_type=source_type, filename=metadata.get("filename"))
            chunk["embedding_text"] = f"{title}\n{chunk['section']}\n{chunk['text']}"
            chunk["content_hash"] = hashlib.sha256(chunk["embedding_text"].encode()).hexdigest()
        doc["chunks"] = chunks
        return doc

    def _embed(self, owner, chunks):
        hashes = [chunk["content_hash"] for chunk in chunks]
        vectors = self.store.cached(owner, self.settings.profile_id, hashes)
        pending = {chunk["content_hash"]: chunk["embedding_text"] for chunk in chunks
                   if chunk["content_hash"] not in vectors}
        self.metrics["cache_hits"] += len(hashes) - len(pending)
        keys = list(pending)
        for start in range(0, len(keys), self.settings.batch_size):
            batch = keys[start:start + self.settings.batch_size]
            try:
                result = self.provider.embed_documents([pending[key] for key in batch])
                dimension = validate_vectors(result, len(batch), self.provider.dimension)
                self.provider.dimension = dimension
                values = dict(zip(batch, result))
                self.store.cache(owner, self.settings.profile_id, values)
                vectors.update(values)
                self.metrics["embedded_chunks"] += len(result)
            except ProviderError as e:
                logging.getLogger(__name__).warning(f"Embedding failed for batch {start//self.settings.batch_size}: {e}")
                # Continue without embeddings for this batch - search will fall back to lexical
                raise
        dimension = validate_vectors(list(vectors.values()), len(vectors), self.provider.dimension) if vectors else None
        return vectors, dimension

    def _needs_reindex(self, owner):
        return bool(self.provider and self.store.documents(owner)
                    and self.store.owner_profile(owner) != self.settings.profile_id)

    def _check_profile(self, owner):
        # No longer raise ReindexRequired - auto-clear is handled in ingest_many
        pass

    def _publish(self, owner, documents):
        chunks = [chunk for doc in documents for chunk in doc["chunks"]]
        profile_id = self.settings.profile_id if self.provider else "none"
        try:
            if self.provider:
                try:
                    vectors, dimension = self._embed(owner, chunks)
                    self.store.write_vectors(owner, profile_id, chunks, vectors, dimension)
                except ProviderError as e:
                    logging.getLogger(__name__).warning(f"Embedding failed, falling back to lexical-only mode: {e}")
                    # Fall back to lexical-only mode (no embeddings)
                    profile_id = "none"
                    self.store.publish(owner, documents, profile_id)
                    self._cleanup(owner)
                    # Add warning to indicate fallback
                    warning = "Semantic search unavailable. Using keyword search only. Check your OpenAI API key and try reindexing."
                    self.store.cleanup_warning(owner, warning, write=True)
                    return
            self.store.publish(owner, documents, profile_id)
        except Exception:
            # Remove staged points; previously committed chunks stay authoritative.
            self._cleanup(owner)
            raise
        # Publication is committed. Cleanup failures must not turn a successful save
        # into an error or prevent the compatibility exports from being refreshed.
        self._cleanup(owner)

    def _cleanup(self, owner):
        try:
            profile = self.store.owner_profile(owner)
            self.store.prune_vectors(owner, profile if profile != "none" else None, self.store.chunks(owner))
            self.store.prune_cache(owner)
        except Exception:
            warning = "Saved sources are available; obsolete index cleanup is pending. Rebuild the index to retry cleanup."
            self.store.cleanup_warning(owner, warning, write=True)
            logging.getLogger(__name__).warning("Index cleanup deferred; active source versions remain authoritative.")
        else:
            self.store.cleanup_warning(owner, write=True)

    def ingest(self, owner, document_id, text, title="Experience story", source_type="story", metadata=None):
        return self.ingest_many(owner, [dict(document_id=document_id, text=text, title=title,
                                            source_type=source_type, metadata=metadata or {})])[0]

    def ingest_many(self, owner, documents):
        with self.lock:
            # Auto-clear old index if configuration changed instead of raising ReindexRequired
            try:
                if self._needs_reindex(owner):
                    logging.getLogger(__name__).warning("Configuration changed, auto-clearing old index...")
                    try:
                        for doc in list(self.store.documents(owner)):
                            try:
                                self.store.delete_document(owner, doc["document_id"])
                            except Exception as e:
                                logging.getLogger(__name__).warning(f"Failed to delete old document {doc['document_id']}: {e}")
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Failed to clear old index: {e}")
            except Exception as e:
                logging.getLogger(__name__).error(f"Error checking reindex status: {e}")
            
            prepared = [self._prepare(owner, doc["document_id"], doc["text"], doc.get("title", "Experience story"),
                                      doc.get("source_type", "story"), doc.get("metadata", {})) for doc in documents]
            if not prepared:
                return []
            if len({doc["document_id"] for doc in prepared}) != len(prepared):
                raise ValueError("Document IDs must be distinct within an import.")
            self._publish(owner, prepared)
            return [{"document_id": doc["document_id"], "version": doc["version"],
                     "chunks_count": len(doc["chunks"]), "mode": "hybrid" if self.provider else "lexical",
                     "warnings": [self.store.cleanup_warning(owner)] if self.store.cleanup_warning(owner) else []}
                    for doc in prepared]

    def reindex(self, owner):
        with self.lock:
            docs = self.store.documents(owner)
            if docs:
                prepared = [self._prepare(owner, doc["document_id"], doc["text"], doc["title"],
                                          doc["source_type"], doc["metadata"]) for doc in docs]
                self._publish(owner, prepared)
            else:
                self._cleanup(owner)
            return self.status(owner)

    def documents(self, owner):
        with self.lock:
            chunks = self.store.chunks(owner)
            return [{key: value for key, value in doc.items() if key not in {"owner", "text", "version_key"}}
                    | {"chunks_count": sum(chunk["document_id"] == doc["document_id"] for chunk in chunks.values())}
                    for doc in self.store.documents(owner)]

    def delete_document(self, owner, document_id):
        with self.lock:
            deleted = self.store.delete_document(owner, document_id)
            if deleted:
                self._cleanup(owner)
            return deleted

    def status(self, owner):
        with self.lock:
            warning = self.store.cleanup_warning(owner)
            return {"documents_count": len(self.store.documents(owner)), "chunks_count": len(self.store.chunks(owner)),
                    "vector_count": self.store.vector_count(owner), "embedding_enabled": bool(self.provider),
                    "embedding_provider": self.settings.embedding_provider, "embedding_model": self.settings.embedding_model,
                    "configured_profile_id": self.settings.profile_id if self.provider else None,
                    "index_profile_id": self.store.owner_profile(owner), "needs_reindex": self._needs_reindex(owner),
                    "maintenance_pending": bool(warning), "warnings": [warning] if warning else [],
                    "metrics": dict(self.metrics) | (dict(self.provider.stats) if self.provider else {})}

    def search(self, owner, query, limit=5, mode="auto"):
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            raise ValueError("Please provide a question containing 1 to 4,000 characters.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("Search limit must be between 1 and 10.")
        if mode not in {"auto", "lexical", "dense", "hybrid"}:
            raise ValueError("Search mode must be auto, lexical, dense, or hybrid.")
        with self.lock:
            started = time.perf_counter()
            mode = ("hybrid" if self.provider else "lexical") if mode == "auto" else mode
            if mode != "lexical" and not self.provider:
                raise ProviderError("No embedding provider is configured. Configure one or use lexical search.")
            if mode != "lexical":
                self._check_profile(owner)
            self.metrics["searches"] += 1
            timings = {}
            chunks = self.store.chunks(owner)
            rankings = {}
            if mode in {"dense", "hybrid"} and chunks:
                mark = time.perf_counter()
                vector = self.provider.embed_query(query.strip())
                validate_vectors([vector], 1, self.store.dimension(self.settings.profile_id))
                timings["query_embedding"] = (time.perf_counter() - mark) * 1000
                mark = time.perf_counter()
                rankings["dense"] = self.store.dense(owner, self.settings.profile_id, vector,
                    {chunk["version_key"] for chunk in chunks.values()}, 20, self.settings.min_score)
                timings["vector_search"] = (time.perf_counter() - mark) * 1000
            if mode in {"lexical", "hybrid"}:
                mark = time.perf_counter()
                rankings["lexical"] = self.store.lexical(owner, query, 20)
                timings["keyword_search"] = (time.perf_counter() - mark) * 1000

            # Chunks with genuine semantic support: store.dense already applies the
            # min_score threshold, so these are the ones actually related to the query.
            dense_supported = {chunk_id for chunk_id, _ in rankings.get("dense", [])}
            # Only gate on semantics when this avatar was indexed with embeddings.
            # Lexical-only avatars (indexed without a provider) keep keyword behaviour.
            index_profile = self.store.owner_profile(owner)
            semantic_active = (mode in {"dense", "hybrid"} and self.provider is not None
                               and index_profile not in (None, "none"))

            combined = {}
            scores = {}
            for method, ranking in rankings.items():
                for rank, (chunk_id, score) in enumerate(ranking, 1):
                    if chunk_id not in chunks:
                        continue
                    combined[chunk_id] = combined.get(chunk_id, 0) + 1 / (60 + rank)
                    scores.setdefault(chunk_id, {})[method] = score
            selected = []
            for chunk_id in sorted(combined, key=lambda key: (-combined[key], key)):
                # With semantic search active, a result must be semantically relevant.
                # This stops a weak keyword overlap from surfacing an unrelated story.
                if semantic_active and chunk_id not in dense_supported:
                    continue
                chunk = chunks[chunk_id]
                if any(self._overlaps(chunk, hit) for hit in selected):
                    continue
                selected.append(chunk)
                if len(selected) >= limit:
                    break
            results = [{"chunk_id": chunk["id"], "citation_id": f"S{index}",
                        "document_id": chunk["document_id"], "document_version": chunk["version_key"],
                        "text": chunk["text"], "source": chunk["source"],
                        "score": combined[chunk["id"]], "scores": scores[chunk["id"]]}
                       for index, chunk in enumerate(selected, 1)]
            timings["total"] = (time.perf_counter() - started) * 1000
            warnings = [] if self.provider else ["Embeddings are not configured; using keyword search only."]
            cleanup_warning = self.store.cleanup_warning(owner)
            if cleanup_warning:
                warnings.append(cleanup_warning)
            return {"results": results, "mode": mode, "embedding_profile_id": self.settings.profile_id if self.provider else None,
                    "score_type": "reciprocal_rank_fusion", "timings_ms": {key: round(value, 3) for key, value in timings.items()},
                    "warnings": warnings}

    @staticmethod
    def _overlaps(chunk, previous):
        if chunk["document_id"] != previous["document_id"]:
            return False
        left, right = chunk["source"], previous["source"]
        intersection = max(0, min(left["end"], right["end"]) - max(left["start"], right["start"]))
        return intersection > 0.5 * min(left["end"] - left["start"], right["end"] - right["start"])
