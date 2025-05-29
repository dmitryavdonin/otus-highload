from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class WebSocketMessageType(str, Enum):
    """Типы WebSocket сообщений"""
    POST_CREATED = "post_created"
    CONNECTION_ACK = "connection_ack"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    SYSTEM = "system"


class WebSocketMessage(BaseModel):
    """Базовая модель WebSocket сообщения"""
    type: WebSocketMessageType = Field(..., description="Тип сообщения")
    data: Optional[Dict[str, Any]] = Field(None, description="Данные сообщения")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время создания сообщения")


class PostCreatedEvent(BaseModel):
    """Событие создания нового поста"""
    post_id: str = Field(..., description="Идентификатор поста")
    post_text: str = Field(..., description="Текст поста")
    author_user_id: str = Field(..., description="Идентификатор автора поста")
    created_at: datetime = Field(..., description="Время создания поста")


class PostCreatedWebSocketMessage(BaseModel):
    """WebSocket сообщение о создании поста"""
    type: WebSocketMessageType = Field(default=WebSocketMessageType.POST_CREATED)
    data: PostCreatedEvent = Field(..., description="Данные о созданном посте")
    timestamp: datetime = Field(default_factory=datetime.now)


class ConnectionAckMessage(BaseModel):
    """Сообщение подтверждения подключения"""
    type: WebSocketMessageType = Field(default=WebSocketMessageType.CONNECTION_ACK)
    data: Dict[str, str] = Field(default_factory=lambda: {"status": "connected"})
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorMessage(BaseModel):
    """Сообщение об ошибке"""
    type: WebSocketMessageType = Field(default=WebSocketMessageType.ERROR)
    data: Dict[str, str] = Field(..., description="Информация об ошибке")
    timestamp: datetime = Field(default_factory=datetime.now)


class QueueEventType(str, Enum):
    """Типы событий в очереди"""
    POST_CREATED = "post_created"
    USER_REGISTERED = "user_registered"
    FRIENDSHIP_CREATED = "friendship_created"


class QueueEvent(BaseModel):
    """Базовое событие для очереди"""
    event_type: QueueEventType = Field(..., description="Тип события")
    user_id: str = Field(..., description="ID пользователя, инициировавшего событие")
    data: Dict[str, Any] = Field(..., description="Данные события")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время события")
    routing_key: str = Field(..., description="Ключ маршрутизации для RabbitMQ")


class PostCreatedQueueEvent(QueueEvent):
    """Событие создания поста для очереди"""
    event_type: QueueEventType = Field(default=QueueEventType.POST_CREATED)
    
    @classmethod
    def create(cls, post_id: str, post_text: str, author_user_id: str, created_at: datetime):
        """Создать событие создания поста"""
        return cls(
            user_id=author_user_id,
            data={
                "post_id": post_id,
                "post_text": post_text,
                "author_user_id": author_user_id,
                "created_at": created_at.isoformat()
            },
            routing_key=f"user.{author_user_id}.post.created"
        )


class WebSocketConnectionInfo(BaseModel):
    """Информация о WebSocket подключении"""
    user_id: str = Field(..., description="ID пользователя")
    connected_at: datetime = Field(default_factory=datetime.now, description="Время подключения")
    last_ping: Optional[datetime] = Field(None, description="Время последнего ping") 