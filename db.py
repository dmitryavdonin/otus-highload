import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets
import uuid
from typing import List
import os

# Выбираем модуль базы данных в зависимости от переменной окружения
USE_HAPROXY = os.getenv("USE_HAPROXY", "false").lower() == "true"

if USE_HAPROXY:
    # Для урока 9 с HAProxy
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), 'lesson-09'))
    from database_ha import get_slave_session, get_master_session, get_db_info
    print("🔧 Загружен модуль database_ha для работы с HAProxy")
else:
    # Стандартный режим
    from database import get_slave_session, get_master_session
    print("🔧 Загружен стандартный модуль database")
    
    # Заглушка для get_db_info в стандартном режиме
    def get_db_info():
        return {"mode": "standard", "use_haproxy": False}

# Import models after database is initialized to avoid circular imports
from models import User, AuthToken, Friendship, DialogMessage

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

async def save_dialog_message(from_user_id: str, to_user_id: str, text: str) -> str:
    """
    Save a new dialog message
    
    Args:
        from_user_id: ID of the message sender
        to_user_id: ID of the message recipient
        text: Message text
        
    Returns:
        ID of the created message
    """
    message_id = uuid.uuid4()
    async with get_master_session() as session:
        message = DialogMessage(
            id=message_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            text=text
        )
        session.add(message)
        await session.commit()
    
    return str(message_id)

async def get_dialog_messages(user_id1: str, user_id2: str) -> List[DialogMessage]:
    """
    Get all messages between two users
    
    Args:
        user_id1: First user ID
        user_id2: Second user ID
        
    Returns:
        List of dialog messages
    """
    async with get_slave_session() as session:
        # Get messages sent from user1 to user2
        from_1_to_2_query = select(DialogMessage).where(
            (DialogMessage.from_user_id == user_id1) & 
            (DialogMessage.to_user_id == user_id2)
        )
        
        # Get messages sent from user2 to user1
        from_2_to_1_query = select(DialogMessage).where(
            (DialogMessage.from_user_id == user_id2) & 
            (DialogMessage.to_user_id == user_id1)
        )
        
        # Execute both queries
        from_1_to_2_result = await session.execute(from_1_to_2_query)
        from_2_to_1_result = await session.execute(from_2_to_1_query)
        
        # Combine and sort results by created_at
        messages = [*from_1_to_2_result.scalars().all(), *from_2_to_1_result.scalars().all()]
        messages.sort(key=lambda msg: msg.created_at)
        
        return messages