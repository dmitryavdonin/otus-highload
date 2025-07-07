from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


# Pydantic модели для API
class DialogMessageRequest(BaseModel):
    text: str = Field(..., description="Текст сообщения")


class DialogMessageResponse(BaseModel):
    from_user_id: str = Field(..., description="Идентификатор отправителя")
    to_user_id: str = Field(..., description="Идентификатор получателя")
    text: str = Field(..., description="Текст сообщения")
    created_at: datetime = Field(..., description="Время создания сообщения")


class DialogStatsResponse(BaseModel):
    backend: str = Field(..., description="Используемый бэкенд")
    total_dialogs: Optional[int] = Field(None, description="Общее количество диалогов")
    total_messages: Optional[int] = Field(None, description="Общее количество сообщений")
    avg_messages_per_dialog: Optional[float] = Field(None, description="Среднее количество сообщений на диалог")


class SendMessageRequest(BaseModel):
    to_user_id: str = Field(..., description="Идентификатор получателя")
    text: str = Field(..., description="Текст сообщения")


class SendMessageResponse(BaseModel):
    status: str = Field(..., description="Статус отправки")
    message_id: Optional[str] = Field(None, description="Идентификатор сообщения")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Статус сервиса")
    version: str = Field(..., description="Версия сервиса")
    backend: str = Field(..., description="Используемый бэкенд")


# SQLAlchemy модель для БД
class DialogMessage(Base):
    __tablename__ = "dialog_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_user_id = Column(UUID(as_uuid=True), nullable=False)
    to_user_id = Column(UUID(as_uuid=True), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False) 