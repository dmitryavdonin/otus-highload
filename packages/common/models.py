from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from sqlalchemy import Column, String, Date, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from packages.common.database import Base


class UserRegisterRequest(BaseModel):
    first_name: str = Field(..., description="Имя пользователя")
    second_name: str = Field(..., description="Фамилия пользователя")
    birthdate: date = Field(..., description="Дата рождения пользователя")
    biography: Optional[str] = Field(None, description="Хобби, интересы и т.п.")
    city: str = Field(..., description="Город пользователя")
    password: str = Field(..., description="Пароль пользователя", min_length=6)


class UserResponse(BaseModel):
    id: str = Field(..., description="Идентификатор пользователя")
    first_name: str = Field(..., description="Имя пользователя")
    second_name: str = Field(..., description="Фамилия пользователя")
    birthdate: date = Field(..., description="Дата рождения пользователя")
    biography: Optional[str] = Field(None, description="Хобби, интересы и т.п.")
    city: str = Field(..., description="Город пользователя")


class LoginRequest(BaseModel):
    id: str = Field(..., description="Идентификатор пользователя")
    password: str = Field(..., description="Пароль пользователя")


class LoginResponse(BaseModel):
    token: str = Field(..., description="Токен аутентификации")


class UserIdResponse(BaseModel):
    user_id: str = Field(..., description="Идентификатор пользователя")


class VersionResponse(BaseModel):
    version: str = Field(..., description="Версия приложения")


class PostCreateRequest(BaseModel):
    text: str = Field(..., description="Текст поста")


class PostUpdateRequest(BaseModel):
    id: str = Field(..., description="Идентификатор поста")
    text: str = Field(..., description="Текст поста")


class PostIdResponse(BaseModel):
    id: str = Field(..., description="Идентификатор поста")


class PostResponse(BaseModel):
    id: str = Field(..., description="Идентификатор поста")
    text: str = Field(..., description="Текст поста")
    author_user_id: str = Field(..., description="Идентификатор автора поста")


class DialogMessageRequest(BaseModel):
    text: str = Field(..., description="Текст сообщения")


class DialogMessageResponse(BaseModel):
    from_user_id: str = Field(..., description="Идентификатор отправителя")
    to_user_id: str = Field(..., description="Идентификатор получателя")
    text: str = Field(..., description="Текст сообщения")
    created_at: datetime = Field(..., description="Время создания сообщения")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True)
    first_name = Column(String, nullable=False)
    second_name = Column(String, nullable=False)
    birthdate = Column(Date, nullable=False)
    biography = Column(String)
    city = Column(String)
    password = Column(String, nullable=False)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token = Column(String(64), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class Friendship(Base):
    __tablename__ = "friends"
    
    # A composite primary key (user_id, friend_id) ensures that a user cannot add the same friend twice
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    friend_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Explicit uniqueness constraint
    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="_user_friend_uc"),)


class Post(Base):
    __tablename__ = "posts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(String, nullable=False)
    author_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DialogMessage(Base):
    __tablename__ = "dialog_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)