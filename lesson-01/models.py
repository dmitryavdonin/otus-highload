from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


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