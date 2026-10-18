"""Deterministic vectors for storage/ranking tests, never used by the app."""


class ConceptEmbeddings:
    dimension = 3

    def __init__(self):
        self.stats = {"calls": 0, "input_tokens": 0, "tokens_reported": False}
        self.fail = False

    def vector(self, text):
        if self.fail:
            from knowledge.embeddings import ProviderError
            raise ProviderError("Synthetic API outage")
        lower = text.lower()
        if any(word in lower for word in ("housing", "apartment", "accommodation", "deposit", "rent")):
            return [1.0, 0.0, 0.0]
        if any(word in lower for word in ("interview", "career", "hiring", "engineering")):
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts):
        self.stats["calls"] += 1
        return [self.vector(text) for text in texts]

    def embed_query(self, text):
        self.stats["calls"] += 1
        return self.vector(text)
