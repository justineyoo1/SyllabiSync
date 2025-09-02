from __future__ import annotations

from typing import List, Optional, Dict

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.db.session import db_session
from apps.api.db.models import Document, User
from packages.common.config import get_settings


router = APIRouter(prefix="/qa", tags=["qa"]) 


@router.get("/ask")
def ask(document_version_id: int, q: str, k: int = 5) -> dict:
    # Dense-only retrieval via pgvector cosine distance
    sql = text(
        """
        WITH q AS (
            SELECT :embedding :: vector AS v
        )
        SELECT c.id as chunk_id, c.page_number, c.text,
               1 - (e.vector <=> (SELECT v FROM q)) as score
        FROM chunks c
        JOIN embeddings e ON e.chunk_id = c.id
        WHERE c.document_version_id = :dvid
        ORDER BY e.vector <=> (SELECT v FROM q)
        LIMIT :k
        """
    )
    # naive embedding of query using same path as fallback (client-side or deterministic)
    from packages.rag.embeddings import embed_texts

    _, dim, [v] = embed_texts([q])
    db: Session
    with db_session() as db:
        rows = db.execute(sql, {"embedding": v, "dvid": document_version_id, "k": k}).mappings().all()
    top_chunks = [
        {"chunk_id": r["chunk_id"], "page": r["page_number"], "text": r["text"], "score": r["score"]}
        for r in rows
    ]

    # simple synthesis: concatenate top chunks
    settings = get_settings()
    answer = None
    if settings.llm_provider.lower() == "openai" and settings.openai_api_key:
        import requests
        prompt = (
            "Answer the question concisely using the provided context. Include citations [page].\n\n"
            f"Question: {q}\n\nContext:\n" + "\n---\n".join([c["text"] for c in top_chunks])
        )
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            answer = data["choices"][0]["message"]["content"].strip()
    if answer is None:
        answer = (top_chunks[0]["text"] if top_chunks else "No relevant context found.")

    return {"question": q, "answer": answer, "top_chunks": top_chunks}


# Chat-style endpoint across user scope
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    scope: str = Field(default="all", description="all|recent|ids")
    ids: Optional[List[int]] = None
    k: int = 5
    version_ids: Optional[List[int]] = None


@router.post("/chat")
def chat(body: ChatRequest) -> dict:
    if not body.messages:
        return {"answer": "", "top_chunks": []}
    # Use last user message as the query
    user_msgs = [m for m in body.messages if m.role == "user"]
    q = user_msgs[-1].content if user_msgs else body.messages[-1].content

    # Embed query
    from packages.rag.embeddings import embed_texts

    _, dim, [v] = embed_texts([q])

    # Determine user scope (MVP: default dev user)
    with db_session() as db:
        default_user = db.query(User).filter(User.email == "dev@local").one_or_none()
        if default_user is None:
            # no documents
            return {"question": q, "answer": "No documents found.", "top_chunks": []}

        # Optional: infer course tokens from query to restrict scope
        import re
        tokens = set(re.findall(r"\b([A-Z]{2,}\s?\d{3})\b", q.upper()))
        inferred_ids: List[int] = []
        if tokens:
            like_patterns = [f"%{t.replace(' ', '')}%" for t in tokens]
            # Try to match titles containing the token (ignoring spaces)
            all_docs = db.query(Document).filter(Document.user_id == default_user.id).all()
            for d in all_docs:
                title_norm = d.title.upper().replace(" ", "")
                if any(p.strip('%') in title_norm for p in like_patterns):
                    inferred_ids.append(d.id)

        # fetch more candidates, then rebalance per document
        fetch_limit = max(20, body.k * 4)
        # Optional exam-only filter if query implies exam-related
        exam_query = False
        q_lower = q.lower()
        if any(term in q_lower for term in ["exam", "midterm", "final"]):
            exam_query = True

        if body.version_ids:
            # Strict scope: only specified document versions (minimal context per upload)
            sql = text(
                """
                WITH q AS (SELECT :embedding :: vector AS v)
                SELECT c.id as chunk_id, c.page_number, c.text, dv.id as document_version_id, d.id as document_id, d.title as document_title,
                       1 - (e.vector <=> (SELECT v FROM q)) as score
                FROM chunks c
                JOIN embeddings e ON e.chunk_id = c.id
                JOIN document_versions dv ON dv.id = c.document_version_id
                JOIN documents d ON d.id = dv.document_id
                WHERE dv.id = ANY(:version_ids)
                ORDER BY e.vector <=> (SELECT v FROM q)
                LIMIT :limit
                """
            )
            rows = db.execute(
                sql,
                {"embedding": v, "version_ids": body.version_ids, "limit": fetch_limit},
            ).mappings().all()
        else:
            # User-scope: optional doc ids and latest version per document
            sql = text(
                """
                WITH q AS (SELECT :embedding :: vector AS v)
                SELECT c.id as chunk_id, c.page_number, c.text, dv.id as document_version_id, d.id as document_id, d.title as document_title,
                       1 - (e.vector <=> (SELECT v FROM q)) as score
                FROM chunks c
                JOIN embeddings e ON e.chunk_id = c.id
                JOIN document_versions dv ON dv.id = c.document_version_id
                JOIN documents d ON d.id = dv.document_id
                WHERE d.user_id = :user_id
                  AND (:use_ids = 0 OR d.id = ANY(:ids))
                  AND dv.id = (
                    SELECT max(dv2.id) FROM document_versions dv2 WHERE dv2.document_id = d.id
                  )
                ORDER BY e.vector <=> (SELECT v FROM q)
                LIMIT :limit
                """
            )
            # decide ids: explicit ids > inferred tokens
            ids = body.ids or (inferred_ids if inferred_ids else [])
            use_ids = 1 if ids else 0
            rows = db.execute(
                sql,
                {"embedding": v, "user_id": default_user.id, "limit": fetch_limit, "use_ids": use_ids, "ids": ids},
            ).mappings().all()

    # Basic exam-term prefilter: retain rows whose text mentions exam terms when relevant
    if exam_query:
        filtered_rows = []
        for r in rows:
            tl = (r["text"] or "").lower()
            if ("exam" in tl) or ("midterm" in tl) or ("final" in tl):
                filtered_rows.append(r)
        if filtered_rows:
            rows = filtered_rows

    # Rebalance and de-duplicate: cap per document and remove near-duplicates
    def norm_text(t: str) -> str:
        import re
        t = t.lower().strip()
        t = re.sub(r"https?://\S+", " ", t)
        t = re.sub(r"\s+", " ", t)
        return t

    def sim(a: str, b: str) -> float:
        aset, bset = set(a.split()), set(b.split())
        if not aset or not bset:
            return 0.0
        inter = len(aset & bset)
        denom = max(1, min(len(aset), len(bset)))
        return inter / denom

    per_doc_cap = max(2, body.k // 2) if body.k > 2 else 1
    lambda_div = 0.7
    selected: List[Dict] = []
    selected_norms: List[str] = []
    per_doc_counts: Dict[int, int] = {}
    # MMR-like selection
    for r in rows:
        doc_id = r["document_id"]
        if per_doc_counts.get(doc_id, 0) >= per_doc_cap:
            continue
        cand_norm = norm_text(r["text"] or "")
        if any(sim(cand_norm, s) > 0.9 for s in selected_norms):  # drop near-duplicates
            continue
        mmr_penalty = 0.0
        if selected_norms:
            mmr_penalty = max(sim(cand_norm, s) for s in selected_norms)
        mmr_score = float(r["score"]) - lambda_div * mmr_penalty
        # Greedy accept (since rows are already roughly sorted by score)
        selected.append({
            "chunk_id": r["chunk_id"],
            "page": r["page_number"],
            "text": r["text"],
            "document_id": doc_id,
            "document_version_id": r["document_version_id"],
            "document_title": r["document_title"],
            "score": mmr_score,
        })
        selected_norms.append(cand_norm)
        per_doc_counts[doc_id] = per_doc_counts.get(doc_id, 0) + 1
        if len(selected) >= body.k:
            break
    top_chunks = selected

    # Synthesize with context and short history
    settings = get_settings()
    answer = None
    # citations: only page numbers
    citations = [c["page"] for c in top_chunks]

    if settings.llm_provider.lower() == "openai" and settings.openai_api_key:
        import requests

        context = "\n---\n".join([f"[doc: {c['document_title']}]\n{c['text']}" for c in top_chunks])
        course_hint = ", focusing ONLY on the requested course(s) if specified" if tokens else ""
        prompt_user = (
            f"Question: {q}\n\nUse the context below and include citations like [page]{course_hint}.\n"
            f"Do not mix information from different courses unless explicitly asked.\n\nContext:\n{context}"
        )
        messages = [{"role": "system", "content": "You are a helpful assistant for course syllabi."}]
        # include short history (up to last 3 user/assistant turns, excluding the final user which we add fresh)
        hist = body.messages[-6:]
        for m in hist:
            if m.role in ("user", "assistant"):
                messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": prompt_user})

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={"model": settings.llm_model, "messages": messages, "temperature": 0.2},
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            answer = data["choices"][0]["message"]["content"].strip()

    if answer is None:
        answer = (top_chunks[0]["text"] if top_chunks else "No relevant context found.")

    return {"question": q, "answer": answer, "top_chunks": top_chunks, "citations": citations}


