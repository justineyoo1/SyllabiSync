from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Response
from sqlalchemy.orm import Session

from apps.api.db.session import db_session
from apps.api.db.models import Event


router = APIRouter(prefix="/calendar", tags=["calendar"]) 


def _ics_escape(text: str) -> str:
    return text.replace(",", "\, ").replace(";", "\; ")


@router.get("/ics")
def get_ics(document_version_id: int) -> Response:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SyllabusSync//EN",
    ]
    with db_session() as db:
        events = (
            db.query(Event)
            .filter(Event.document_version_id == document_version_id)
            .order_by(Event.due_at)
            .all()
        )
        for ev in events:
            dt = ev.due_at.strftime("%Y%m%dT%H%M%SZ")
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:ev-{ev.id}@syllabussync",
                    f"DTSTAMP:{dt}",
                    f"DTSTART:{dt}",
                    f"SUMMARY:{_ics_escape(ev.title)}",
                    "END:VEVENT",
                ]
            )
    lines.append("END:VCALENDAR")
    ics = "\r\n".join(lines)
    return Response(content=ics, media_type="text/calendar")


