import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets
import uuid
from typing import List
from database import get_slave_session, get_master_session

# Import models after database is initialized to avoid circular imports
from models import User, AuthToken, Friendship

async def get_user_by_id(user_id: str) -> User:
    async with get_slave_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

async def get_user_by_token(token: str) -> uuid.UUID:
    print(f"DEBUG: get_user_by_token called with token: {token}")
    
    try:
        async with get_slave_session() as session:
            # First, check if the token exists regardless of expiration
            token_query = select(AuthToken).where(AuthToken.token == token)
            token_result = await session.execute(token_query)
            auth_token = token_result.scalar_one_or_none()
            
            if not auth_token:
                print(f"DEBUG: Token not found in database")
                return None
            
            # Token exists, now check if it's expired
            current_time = datetime.now()
            print(f"DEBUG: Token found. Expires at: {auth_token.expires_at}, Current time: {current_time}")
            
            # Force comparison without timezone info
            if auth_token.expires_at.replace(tzinfo=None) > current_time.replace(tzinfo=None):
                print(f"DEBUG: Token is valid")
                return auth_token.user_id
            else:
                print(f"DEBUG: Token is expired")
                return None
    except Exception as e:
        print(f"ERROR: Exception in get_user_by_token: {str(e)}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        raise

async def create_auth_token(user_id: uuid.UUID) -> str:
    async with get_master_session() as session:
        token = secrets.token_hex(32)
        expires_at = datetime.now() + timedelta(days=1)
        auth_token = AuthToken(token=token, user_id=user_id, expires_at=expires_at)
        session.add(auth_token)
        await session.commit()
        return token


async def get_user_friends(user_id: str) -> List[str]:
    """
    Get a list of friend IDs for a user
    
    Args:
        user_id: The ID of the user whose friends to retrieve
        
    Returns:
        A list of friend IDs
    """
    async with get_slave_session() as session:
        result = await session.execute(
            select(Friendship.friend_id).where(Friendship.user_id == user_id)
        )
        friend_ids = [str(row[0]) for row in result.all()]
        return friend_ids

async def get_user_by_id(user_id: str) -> User:
    async with get_slave_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

async def get_user_by_token(token: str) -> uuid.UUID:
    print(f"DEBUG: get_user_by_token called with token: {token}")
    
    try:
        async with get_slave_session() as session:
            # First, check if the token exists regardless of expiration
            token_query = select(AuthToken).where(AuthToken.token == token)
            token_result = await session.execute(token_query)
            auth_token = token_result.scalar_one_or_none()
            
            if not auth_token:
                print(f"DEBUG: Token not found in database")
                return None
            
            # Token exists, now check if it's expired
            current_time = datetime.now()
            print(f"DEBUG: Token found. Expires at: {auth_token.expires_at}, Current time: {current_time}")
            
            # Force comparison without timezone info
            if auth_token.expires_at.replace(tzinfo=None) > current_time.replace(tzinfo=None):
                print(f"DEBUG: Token is valid")
                return auth_token.user_id
            else:
                print(f"DEBUG: Token is expired")
                return None
    except Exception as e:
        print(f"ERROR: Exception in get_user_by_token: {str(e)}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        raise

async def create_auth_token(user_id: uuid.UUID) -> str:
    async with get_master_session() as session:
        token = secrets.token_hex(32)
        expires_at = datetime.now() + timedelta(days=1)
        auth_token = AuthToken(token=token, user_id=user_id, expires_at=expires_at)
        session.add(auth_token)
        await session.commit()
        return token


async def get_user_friends(user_id: str) -> List[str]:
    """
    Get a list of friend IDs for a user
    
    Args:
        user_id: The ID of the user whose friends to retrieve
        
    Returns:
        A list of friend IDs
    """
    from models import Friendship
    
    async with get_slave_session() as session:
        result = await session.execute(
            select(Friendship.friend_id).where(Friendship.user_id == user_id)
        )
        friend_ids = [str(row[0]) for row in result.all()]
        return friend_ids