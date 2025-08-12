from fastapi import FastAPI, HTTPException, Header, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from packages.common.models import DialogMessageRequest, DialogMessageResponse
from packages.common.db import get_user_by_token
from packages.common.database import get_master_session
from .dialog_service import dialog_service
from .worker import start_background_publisher, stop_background_publisher


app = FastAPI(title="Dialog Service", version="0.1.0")


@app.on_event("startup")
async def on_startup():
    await dialog_service.init()
    await start_background_publisher()


@app.on_event("shutdown")
async def on_shutdown():
    await stop_background_publisher()
    await dialog_service.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


async def verify_token(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split(" ")[1]
    user_id = await get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return str(user_id)


class SendMessageRequest(BaseModel):
    from_user_id: str
    to_user_id: str
    text: str


@app.post("/api/v1/dialogs/send")
async def send_message(body: SendMessageRequest, current_user_id: str = Depends(verify_token)):
    if str(body.from_user_id) != str(current_user_id):
        raise HTTPException(status_code=403, detail="Forbidden: from_user_id mismatch")
    msg_id = await dialog_service.save_dialog_message(body.from_user_id, body.to_user_id, body.text)
    return {"id": msg_id}


@app.get("/api/v1/dialogs/{user_id}/messages", response_model=List[DialogMessageResponse])
async def get_messages(user_id: str, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0), current_user_id: str = Depends(verify_token)):
    messages = await dialog_service.get_dialog_messages(current_user_id, user_id)
    # simple slicing for offset/limit when backend is postgres
    return messages[offset:offset+limit]


@app.get("/api/v1/dialogs/{user_id}/recent", response_model=List[DialogMessageResponse])
async def get_recent(user_id: str, limit: int = Query(50, ge=1, le=100), current_user_id: str = Depends(verify_token)):
    messages = await dialog_service.get_dialog_messages(current_user_id, user_id)
    return messages[-limit:]


@app.get("/api/v1/dialogs/stats")
async def stats(_: str = Depends(verify_token)):
    return await dialog_service.get_dialog_stats()


