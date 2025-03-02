from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import UserRegisterRequest, UserResponse, LoginRequest, LoginResponse, UserIdResponse
from db import get_db_cursor
from datetime import datetime, timedelta
import secrets
import hashlib
import uuid
from typing import Optional

app = FastAPI(
    title="Social Network API",
    description="A simple social network API",
    version="0.1.0"
)

security = HTTPBearer()


def get_password_hash(password: str) -> str:
    """
    Generate a hash for the given password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verify the authentication token and return the user ID
    """
    token = credentials.credentials
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT user_id FROM auth_tokens WHERE token = %s AND expires_at > %s",
            (token, datetime.now())
        )
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        return result["user_id"]


@app.post("/login", response_model=LoginResponse, tags=["Authentication"])
def login(login_data: LoginRequest):
    """
    Authenticate a user and return a token
    """
    with get_db_cursor() as cursor:
        # Check if user exists and password is correct
        cursor.execute(
            "SELECT id, password FROM users WHERE id = %s",
            (login_data.id,)
        )
        user = cursor.fetchone()
        
        if not user or user["password"] != get_password_hash(login_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Generate a token
        token = secrets.token_hex(16)
        expires_at = datetime.now() + timedelta(days=1)
        
        # Store the token
        cursor.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (%s, %s, %s)",
            (token, user["id"], expires_at)
        )
        
        return LoginResponse(token=token)


@app.post("/user/register", response_model=UserIdResponse, tags=["Users"])
def register_user(user_data: UserRegisterRequest):
    """
    Register a new user
    """
    with get_db_cursor() as cursor:
        # Hash the password
        hashed_password = get_password_hash(user_data.password)
        
        # Generate a UUID for the user
        user_id = str(uuid.uuid4())
        
        # Insert the user
        cursor.execute(
            """
            INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                user_data.first_name,
                user_data.second_name,
                user_data.birthdate,
                user_data.biography,
                user_data.city,
                hashed_password
            )
        )
        
        user_id = cursor.fetchone()["id"]
        return UserIdResponse(user_id=user_id)


@app.get("/user/get/{user_id}", response_model=UserResponse, tags=["Users"])
def get_user(user_id: str):
    """
    Get a user by ID
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, first_name, second_name, birthdate, biography, city
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
        
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        return UserResponse(
            id=user["id"],
            first_name=user["first_name"],
            second_name=user["second_name"],
            birthdate=user["birthdate"],
            biography=user["biography"],
            city=user["city"]
        )