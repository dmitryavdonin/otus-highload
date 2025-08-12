import uuid
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import text
from packages.common.db import get_master_session


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS outbox_messages (
  id UUID PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL,
  last_error TEXT
);
"""


async def ensure_outbox_table():
    async with get_master_session() as session:
        await session.execute(text(CREATE_TABLE_SQL))
        await session.commit()


async def add_outbox_event(event_type: str, payload: Dict[str, Any]) -> str:
    """Add event to outbox within existing transaction boundary (separate call for simplicity)."""
    event_id = str(uuid.uuid4())
    now = datetime.utcnow()
    async with get_master_session() as session:
        await session.execute(
            text("""
            INSERT INTO outbox_messages(id, event_type, payload, status, created_at)
            VALUES (:id, :event_type, CAST(:payload AS JSONB), 'pending', :created_at)
            """),
            {"id": event_id, "event_type": event_type, "payload": json_dumps(payload), "created_at": now}
        )
        await session.commit()
    return event_id


async def fetch_pending_events(limit: int = 100):
    async with get_master_session() as session:
        res = await session.execute(text("SELECT id, event_type, payload FROM outbox_messages WHERE status='pending' ORDER BY created_at LIMIT :lim"), {"lim": limit})
        return res.fetchall()


async def mark_event_done(event_id: str):
    async with get_master_session() as session:
        await session.execute(text("UPDATE outbox_messages SET status='done' WHERE id=:id"), {"id": event_id})
        await session.commit()


async def mark_event_error(event_id: str, error: str):
    async with get_master_session() as session:
        await session.execute(text("UPDATE outbox_messages SET status='error', last_error=:err WHERE id=:id"), {"id": event_id, "err": error[:1000]})
        await session.commit()


def json_dumps(obj: Dict[str, Any]) -> str:
    import json
    return json.dumps(obj)


