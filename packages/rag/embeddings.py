from __future__ import annotations

import hashlib
from typing import List

import requests

from packages.common.config import get_settings


def _hash_embed(text: str, dim: int = 1536) -> list[float]:
    # very cheap deterministic fallback embedding (not for production quality)
    h = hashlib.sha256(text.encode()).digest()
    vals = [b / 255.0 for b in h]
    out: list[float] = []
    while len(out) < dim:
        out.extend(vals)
    return out[:dim]


def embed_texts(texts: List[str]) -> tuple[str, int, List[List[float]]]:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    model = settings.embedding_model
    if provider == "openai" and settings.openai_api_key:
        # Minimal call via OpenAI embeddings API
        resp = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        vectors: List[List[float]] = [item["embedding"] for item in data["data"]]
        dim = len(vectors[0]) if vectors else 0
        return model, dim, vectors
    # fallback deterministic embeddings
    vectors = [_hash_embed(t) for t in texts]
    return model, len(vectors[0]) if vectors else 0, vectors


