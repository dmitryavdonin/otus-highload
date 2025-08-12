from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from sqlalchemy import Column, String, Date, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from database import Base

Base = declarative_base()


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