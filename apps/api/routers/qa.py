from __future__ import annotations

from typing import List, Optional

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

        # Build SQL over user's documents
        sql = text(
            """
            WITH q AS (SELECT :embedding :: vector AS v)
            SELECT c.id as chunk_id, c.page_number, c.text, dv.id as document_version_id, d.id as document_id,
                   1 - (e.vector <=> (SELECT v FROM q)) as score
            FROM chunks c
            JOIN embeddings e ON e.chunk_id = c.id
            JOIN document_versions dv ON dv.id = c.document_version_id
            JOIN documents d ON d.id = dv.document_id
            WHERE d.user_id = :user_id
              AND (:use_ids = 0 OR d.id = ANY(:ids))
            ORDER BY e.vector <=> (SELECT v FROM q)
            LIMIT :k
            """
        )
        ids = body.ids or []
        use_ids = 1 if ids else 0
        rows = db.execute(
            sql,
            {"embedding": v, "user_id": default_user.id, "k": body.k, "use_ids": use_ids, "ids": ids},
        ).mappings().all()

    top_chunks = [
        {
            "chunk_id": r["chunk_id"],
            "page": r["page_number"],
            "text": r["text"],
            "document_id": r["document_id"],
            "document_version_id": r["document_version_id"],
            "score": r["score"],
        }
        for r in rows
    ]

    # Synthesize with context and short history
    settings = get_settings()
    answer = None
    citations = [
        {"document_id": c["document_id"], "page": c["page"], "snippet": c["text"][:200]}
        for c in top_chunks
    ]

    if settings.llm_provider.lower() == "openai" and settings.openai_api_key:
        import requests

        context = "\n---\n".join([c["text"] for c in top_chunks])
        prompt_user = f"Question: {q}\n\nUse the context below and include citations like [page].\n\nContext:\n{context}"
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


