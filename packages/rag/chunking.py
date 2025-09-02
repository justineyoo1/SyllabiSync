from __future__ import annotations

from typing import Iterable, List, Tuple


def split_text_into_chunks(text: str, max_len: int = 800, overlap: int = 100) -> List[Tuple[int, int, str]]:
    """Simple recursive-like chunker using fixed windows with overlap.

    Returns list of (start_offset, end_offset, chunk_text).
    """
    if max_len <= 0:
        return [(0, len(text), text)]
    chunks: List[Tuple[int, int, str]] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_len)
        chunk = text[start:end]
        chunks.append((start, end, chunk))
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


