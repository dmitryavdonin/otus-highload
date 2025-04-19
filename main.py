from fastapi import FastAPI, HTTPException, Depends, status, Query, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
import hashlib
import uuid
import os
from dotenv import load_dotenv
from sqlalchemy import select
from models import User, AuthToken
from db import get_master_session, get_slave_session, get_user_by_id, get_user_by_token, create_auth_token

load_dotenv()

app = FastAPI(
    title="Social Network API",
    description="A simple social network API",
    version="0.2.0"
)

security = HTTPBearer()

class LoginRequest(BaseModel):
    id: str
    password: str

class LoginResponse(BaseModel):
    token: str

class UserCreate(BaseModel):
    first_name: str
    second_name: str
    birthdate: datetime
    biography: Optional[str] = None
    city: str
    password: str

class UserResponse(BaseModel):
    id: str
    first_name: str
    second_name: str
    birthdate: datetime
    biography: Optional[str] = None
    city: str

def get_password_hash(password: str) -> str:
    """
    Generate a hash for the given password
    """
    return hashlib.sha256(password.encode()).hexdigest()

async def verify_token(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]
    user_id = await get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return str(user_id)

@app.post("/user/login", response_model=LoginResponse, tags=["Authentication"])
async def login(login_data: LoginRequest):
    """
    Authenticate a user and return a token
    """
    user = await get_user_by_id(login_data.id)
    if not user or user.password != get_password_hash(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    token = await create_auth_token(user.id)
    return LoginResponse(token=token)

@app.post("/user/register", response_model=UserResponse, tags=["Users"])
async def register_user(user: UserCreate):
    """
    Register a new user
    """
    user_id = str(uuid.uuid4())
    new_user = User(
        id=user_id,
        first_name=user.first_name,
        second_name=user.second_name,
        birthdate=user.birthdate,
        biography=user.biography,
        city=user.city,
        password=get_password_hash(user.password)
    )
    
    async with get_master_session() as session:
        session.add(new_user)
        await session.commit()
    
    return UserResponse(
        id=user_id,
        first_name=user.first_name,
        second_name=user.second_name,
        birthdate=user.birthdate,
        biography=user.biography,
        city=user.city
    )

@app.get("/user/get/{id}", response_model=UserResponse, tags=["Users"])
async def get_user(id: str, user_id: str = Depends(verify_token)):
    """
    Get a user by ID
    """
    if id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user = await get_user_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=str(user.id),
        first_name=user.first_name,
        second_name=user.second_name,
        birthdate=user.birthdate,
        biography=user.biography,
        city=user.city
    )

@app.get("/user/search", response_model=List[UserResponse], tags=["Users"])
async def search_users(
    first_name: Optional[str] = None,
    second_name: Optional[str] = None,
    user_id: str = Depends(verify_token)
):
    """
    Search for users by first name and/or second name
    """
    if not first_name and not second_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one search parameter must be provided"
        )
    
    query = select(User)
    if first_name:
        query = query.where(User.first_name.ilike(f"%{first_name}%"))
    if second_name:
        query = query.where(User.second_name.ilike(f"%{second_name}%"))
    
    async with get_slave_session() as session:
        result = await session.execute(query)
        users = result.scalars().all()
    
    return [
        UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            second_name=user.second_name,
            birthdate=user.birthdate,
            biography=user.biography,
            city=user.city
        )
        for user in users
    ]