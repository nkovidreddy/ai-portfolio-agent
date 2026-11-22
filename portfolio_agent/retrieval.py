"""Small local vector retrieval service; no web/API or credentials required.

The MVP uses TF-IDF sparse vectors + cosine similarity. This is vector retrieval,
not dense neural embeddings. Production can replace the backend with a dense
embedding provider + managed vector store without changing ResearchAgent.
"""
from __future__ import annotations
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent

class LocalKnowledgeBase:
    def __init__(self, dataset: Path | None = None, include_new_report: bool = True):
        self.dataset = dataset or ROOT / "data" / "documents.json"
        source = json.loads(self.dataset.read_text(encoding="utf-8"))
        self.documents = [d for d in source if include_new_report or not (d["ticker"] == "NVDA" and d["version"] == 2)]
        self._rebuild()

    def _rebuild(self):
        self._dense_cache = {}
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform([d["title"] + " " + d["text"] for d in self.documents]) if self.documents else None

    def retrieve(self, ticker: str, query: str, top_k: int = 3) -> list[dict]:
        indices = [i for i, doc in enumerate(self.documents) if doc["ticker"] == ticker.upper()]
        if not indices or self.matrix is None: return []
        q_vec = self.vectorizer.transform([query])
        sim = cosine_similarity(q_vec, self.matrix[indices]).ravel()
        ranked = sorted(zip(indices, sim), key=lambda x: (x[1], self.documents[x[0]]["date"]), reverse=True)
        return [{**self.documents[i], "retrieval_score": round(float(score), 3)} for i, score in ranked[:top_k]]

    def latest_report(self, ticker: str) -> dict | None:
        docs = [d for d in self.documents if d["ticker"] == ticker.upper() and d["kind"] == "earnings summary"]
        return max(docs, key=lambda d: d["date"]) if docs else None

    def ingest(self, doc: dict) -> None:
        """Demo on-demand knowledge-base update, deduplicated by document ID."""
        self.documents = [d for d in self.documents if d["id"] != doc["id"]] + [doc]
        self._rebuild()

    def ingest_newer_nvda_report(self) -> dict:
        source = json.loads(self.dataset.read_text(encoding="utf-8"))
        updates = [d for d in source if d["ticker"] == "NVDA" and d["version"] == 2]
        for doc in updates: self.ingest(doc)
        return next(d for d in updates if d["kind"] == "earnings summary")
