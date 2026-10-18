"""Persistent sources and keyword/cache tables, plus a shared Qdrant Local client."""

from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import time

from qdrant_client import QdrantClient, models


STOP_WORDS = frozenset("a an the is are was were be been and or to of in on for with at by from as it this that what how why when where who which do does did you your i my me tell about have has had can could would should please".split())


class KnowledgeStore:
    def __init__(self, data_dir):
        self.directory = Path(data_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "sources.sqlite3"
        self.vector_path = self.directory / "vectors"
        self._vectors = None
        with self.connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    owner TEXT NOT NULL, document_id TEXT NOT NULL, version TEXT NOT NULL,
                    version_key TEXT NOT NULL, text TEXT NOT NULL, title TEXT NOT NULL,
                    source_type TEXT NOT NULL, metadata TEXT NOT NULL, updated_at REAL NOT NULL,
                    PRIMARY KEY(owner, document_id));
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, document_id TEXT NOT NULL,
                    version_key TEXT NOT NULL, text TEXT NOT NULL, title TEXT NOT NULL,
                    source TEXT NOT NULL, embedding_text TEXT NOT NULL, content_hash TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS chunks_owner ON chunks(owner, document_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED, owner UNINDEXED, title, text);
                CREATE TABLE IF NOT EXISTS owner_profiles (owner TEXT PRIMARY KEY, profile_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profiles (profile_id TEXT PRIMARY KEY, dimension INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    owner TEXT NOT NULL, profile_id TEXT NOT NULL, content_hash TEXT NOT NULL,
                    vector TEXT NOT NULL, PRIMARY KEY(owner, profile_id, content_hash));
                CREATE TABLE IF NOT EXISTS maintenance (owner TEXT PRIMARY KEY, warning TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.database, timeout=20)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @property
    def vectors(self):
        if self._vectors is None:
            self._vectors = QdrantClient(path=str(self.vector_path))
        return self._vectors

    def close(self):
        if self._vectors is not None:
            self._vectors.close()
            self._vectors = None

    def documents(self, owner):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM documents WHERE owner=? ORDER BY document_id", (owner,)).fetchall()
        return [dict(row) | {"metadata": json.loads(row["metadata"])} for row in rows]

    def chunks(self, owner):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM chunks WHERE owner=?", (owner,)).fetchall()
        return {row["id"]: dict(row) | {"source": json.loads(row["source"])} for row in rows}

    def owner_profile(self, owner):
        with self.connect() as conn:
            row = conn.execute("SELECT profile_id FROM owner_profiles WHERE owner=?", (owner,)).fetchone()
        return row[0] if row else None

    def dimension(self, profile_id):
        with self.connect() as conn:
            row = conn.execute("SELECT dimension FROM profiles WHERE profile_id=?", (profile_id,)).fetchone()
        return row[0] if row else None

    def cached(self, owner, profile_id, hashes):
        # Read owner-scoped rows once; avoid SQLite's parameter limit for large imports.
        with self.connect() as conn:
            rows = conn.execute("SELECT content_hash, vector FROM embedding_cache WHERE owner=? AND profile_id=?",
                                (owner, profile_id)).fetchall()
        wanted = set(hashes)
        return {row[0]: json.loads(row[1]) for row in rows if row[0] in wanted}

    def cache(self, owner, profile_id, vectors):
        with self.connect() as conn:
            conn.executemany("INSERT OR REPLACE INTO embedding_cache VALUES (?,?,?,?)",
                             [(owner, profile_id, key, json.dumps(vector)) for key, vector in vectors.items()])

    def publish(self, owner, documents, profile_id):
        """Publish all supplied document versions and the profile in one SQLite transaction."""
        with self.connect() as conn:
            for doc in documents:
                previous = conn.execute("SELECT id FROM chunks WHERE owner=? AND document_id=?",
                                        (owner, doc["document_id"])).fetchall()
                conn.executemany("DELETE FROM chunks_fts WHERE chunk_id=?", [(row[0],) for row in previous])
                conn.execute("DELETE FROM chunks WHERE owner=? AND document_id=?", (owner, doc["document_id"]))
                conn.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?)", (
                    owner, doc["document_id"], doc["version"], doc["version_key"], doc["text"], doc["title"],
                    doc["source_type"], json.dumps(doc["metadata"], ensure_ascii=False), time.time()))
                for chunk in doc["chunks"]:
                    conn.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?)", (
                        chunk["id"], owner, doc["document_id"], doc["version_key"], chunk["text"], doc["title"],
                        json.dumps(chunk["source"], ensure_ascii=False), chunk["embedding_text"], chunk["content_hash"]))
                    conn.execute("INSERT INTO chunks_fts VALUES (?,?,?,?)", (
                        chunk["id"], owner, chunk["source"]["section"], chunk["text"]))
            conn.execute("INSERT OR REPLACE INTO owner_profiles VALUES (?,?)", (owner, profile_id))

    def prune_cache(self, owner):
        with self.connect() as conn:
            conn.execute("DELETE FROM embedding_cache WHERE owner=? AND content_hash NOT IN "
                         "(SELECT content_hash FROM chunks WHERE owner=?)", (owner, owner))

    def delete_document(self, owner, document_id):
        with self.connect() as conn:
            found = conn.execute("SELECT 1 FROM documents WHERE owner=? AND document_id=?", (owner, document_id)).fetchone()
            if not found:
                return False
            ids = conn.execute("SELECT id FROM chunks WHERE owner=? AND document_id=?", (owner, document_id)).fetchall()
            conn.executemany("DELETE FROM chunks_fts WHERE chunk_id=?", [(row[0],) for row in ids])
            conn.execute("DELETE FROM chunks WHERE owner=? AND document_id=?", (owner, document_id))
            conn.execute("DELETE FROM documents WHERE owner=? AND document_id=?", (owner, document_id))
        return True

    def cleanup_warning(self, owner, warning=None, write=False):
        with self.connect() as conn:
            if write:
                if warning:
                    conn.execute("INSERT OR REPLACE INTO maintenance VALUES (?,?)", (owner, warning))
                else:
                    conn.execute("DELETE FROM maintenance WHERE owner=?", (owner,))
            row = conn.execute("SELECT warning FROM maintenance WHERE owner=?", (owner,)).fetchone()
        return row[0] if row else None

    def lexical(self, owner, query, limit):
        terms = list(dict.fromkeys(term.lower() for term in re.findall(r"\w+", query)
                                   if term.lower() not in STOP_WORDS))[:32]
        if not terms:
            return []
        expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        with self.connect() as conn:
            rows = conn.execute("SELECT chunk_id, bm25(chunks_fts) AS score FROM chunks_fts "
                                "WHERE chunks_fts MATCH ? AND owner=? ORDER BY score LIMIT ?",
                                (expression, owner, limit)).fetchall()
        return [(row[0], row[1]) for row in rows]

    @staticmethod
    def collection_name(profile_id):
        return "knowledge_" + profile_id

    def write_vectors(self, owner, profile_id, chunks, vectors, dimension):
        name = self.collection_name(profile_id)
        if not self.vectors.collection_exists(name):
            self.vectors.create_collection(name, vectors_config=models.VectorParams(
                size=dimension, distance=models.Distance.COSINE))
        else:
            config = self.vectors.get_collection(name).config.params.vectors
            if config.size != dimension:
                raise ValueError("Stored vector dimensions do not match the configured model.")
        with self.connect() as conn:
            previous = conn.execute("SELECT dimension FROM profiles WHERE profile_id=?", (profile_id,)).fetchone()
            if previous and previous[0] != dimension:
                raise ValueError("Embedding dimensions changed within the same profile.")
            conn.execute("INSERT OR IGNORE INTO profiles VALUES (?,?)", (profile_id, dimension))
        points = [models.PointStruct(id=chunk["id"], vector=vectors[chunk["content_hash"]], payload={
            "owner": owner, "version_key": chunk["version_key"], "document_id": chunk["document_id"],
        }) for chunk in chunks]
        for start in range(0, len(points), 128):
            self.vectors.upsert(name, points=points[start:start + 128], wait=True)

    def dense(self, owner, profile_id, vector, version_keys, limit, min_score):
        name = self.collection_name(profile_id)
        if not version_keys or not self.vectors.collection_exists(name):
            return []
        query_filter = models.Filter(must=[
            models.FieldCondition(key="owner", match=models.MatchValue(value=owner)),
            models.FieldCondition(key="version_key", match=models.MatchAny(any=list(version_keys))),
        ])
        hits = self.vectors.query_points(name, query=vector, query_filter=query_filter, limit=limit,
                                         score_threshold=min_score, with_payload=False).points
        return [(str(hit.id), float(hit.score)) for hit in hits]

    def prune_vectors(self, owner, profile_id, valid_ids):
        if self._vectors is None and not self.vector_path.exists():
            return
        for collection in self.vectors.get_collections().collections:
            if not collection.name.startswith("knowledge_"):
                continue
            selector = models.Filter(must=[models.FieldCondition(key="owner", match=models.MatchValue(value=owner))])
            if profile_id and collection.name == self.collection_name(profile_id) and valid_ids:
                selector.must_not = [models.HasIdCondition(has_id=list(valid_ids))]
            self.vectors.delete(collection.name, points_selector=models.FilterSelector(filter=selector), wait=True)

    def vector_count(self, owner):
        if self._vectors is None and not self.vector_path.exists():
            return 0
        selector = models.Filter(must=[models.FieldCondition(key="owner", match=models.MatchValue(value=owner))])
        return sum(self.vectors.count(item.name, count_filter=selector, exact=True).count
                   for item in self.vectors.get_collections().collections if item.name.startswith("knowledge_"))
