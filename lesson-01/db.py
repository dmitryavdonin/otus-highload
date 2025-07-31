import psycopg2
from psycopg2.extras import RealDictCursor
import os
from contextlib import contextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models import User, AuthToken
from datetime import datetime, timedelta
import secrets
import uuid

# Database connection parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_SLAVE1_HOST = os.getenv("DB_SLAVE1_HOST", "localhost")
DB_SLAVE2_HOST = os.getenv("DB_SLAVE2_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "social_network")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Create async engines for master and slaves
master_engine = create_async_engine(
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    echo=False
)

slave1_engine = create_async_engine(
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_SLAVE1_HOST}:{DB_PORT}/{DB_NAME}",
    echo=False
)

slave2_engine = create_async_engine(
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_SLAVE2_HOST}:{DB_PORT}/{DB_NAME}",
    echo=False
)

# Create session factories
master_session_factory = sessionmaker(master_engine, class_=AsyncSession, expire_on_commit=False)
slave1_session_factory = sessionmaker(slave1_engine, class_=AsyncSession, expire_on_commit=False)
slave2_session_factory = sessionmaker(slave2_engine, class_=AsyncSession, expire_on_commit=False)

# Function to get a slave session (round-robin between slaves)
_slave_counter = 0
def get_slave_session():
    global _slave_counter
    _slave_counter = (_slave_counter + 1) % 2
    return slave1_session_factory() if _slave_counter == 0 else slave2_session_factory()

# Function to get a master session
def get_master_session():
    return master_session_factory()

async def get_user_by_id(user_id: str) -> User:
    async with get_slave_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

async def get_user_by_token(token: str) -> uuid.UUID:
    async with get_slave_session() as session:
        result = await session.execute(
            select(AuthToken.user_id).where(
                AuthToken.token == token,
                AuthToken.expires_at > datetime.now()
            )
        )
        return result.scalar_one_or_none()

async def create_auth_token(user_id: uuid.UUID) -> str:
    async with get_master_session() as session:
        token = secrets.token_hex(32)
        expires_at = datetime.now() + timedelta(days=1)
        auth_token = AuthToken(token=token, user_id=user_id, expires_at=expires_at)
        session.add(auth_token)
        await session.commit()
        return token