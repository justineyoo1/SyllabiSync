from __future__ import annotations

from datetime import datetime
from typing import List

import dateparser
from sqlalchemy.orm import Session

from apps.worker.worker import celery_app
from apps.api.db.session import SessionLocal
from apps.api.db.models import Page, Event


@celery_app.task(name="events.extract_events")
def extract_events(document_version_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        pages: List[Page] = (
            db.query(Page).filter(Page.document_version_id == document_version_id).order_by(Page.page_number).all()
        )
        created = 0
        for page in pages:
            # naive heuristic: lines with 'Exam' or 'Due' + a date-like token
            for line in page.text.splitlines():
                if "exam" in line.lower() or "due" in line.lower():
                    dt = dateparser.parse(line, settings={"RETURN_AS_TIMEZONE_AWARE": True})
                    if dt:
                        db.add(
                            Event(
                                document_version_id=document_version_id,
                                title=line.strip()[:200],
                                due_at=dt,
                                page_number=page.page_number,
                                source_start_offset=None,
                                source_end_offset=None,
                            )
                        )
                        created += 1
        db.commit()
        return {"ok": True, "events": created}
    finally:
        db.close()


