import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..database.connection import get_db_session
from ..models.dialog import DialogMessage, DialogMessageResponse, DialogStatsResponse
from ..middleware.request_id import get_request_id

logger = logging.getLogger(__name__)


class DialogService:
    """
    Сервис для работы с диалогами
    Поддерживает PostgreSQL и Redis backend
    """
    
    def __init__(self):
        self._redis_adapter = None
    
    async def init(self):
        """Инициализация сервиса"""
        if settings.is_redis_backend():
            from .redis_adapter import RedisDialogAdapter
            self._redis_adapter = RedisDialogAdapter(settings.redis_url)
            await self._redis_adapter.connect()
            logger.info(f"Dialog service initialized with Redis backend: {settings.redis_url}")
        else:
            logger.info("Dialog service initialized with PostgreSQL backend")
    
    async def close(self):
        """Закрытие соединений"""
        if self._redis_adapter:
            await self._redis_adapter.disconnect()
    
    async def save_dialog_message(self, from_user_id: str, to_user_id: str, text: str) -> str:
        """
        Сохранение сообщения диалога
        
        Args:
            from_user_id: ID отправителя
            to_user_id: ID получателя
            text: Текст сообщения
            
        Returns:
            ID созданного сообщения
        """
        request_id = get_request_id()
        logger.info(
            f"Saving dialog message from {from_user_id} to {to_user_id}",
            extra={"request_id": request_id}
        )
        
        if settings.is_redis_backend():
            return await self._redis_adapter.save_dialog_message(from_user_id, to_user_id, text)
        else:
            return await self._save_message_postgresql(from_user_id, to_user_id, text)
    
    async def get_dialog_messages(self, user_id1: str, user_id2: str, limit: int = None, 
                                offset: int = 0) -> List[DialogMessageResponse]:
        """
        Получение сообщений диалога
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            limit: Максимальное количество сообщений
            offset: Смещение для пагинации
            
        Returns:
            Список сообщений диалога
        """
        if limit is None:
            limit = settings.DIALOG_MESSAGES_LIMIT
            
        request_id = get_request_id()
        logger.info(
            f"Getting dialog messages between {user_id1} and {user_id2}",
            extra={"request_id": request_id, "limit": limit, "offset": offset}
        )
        
        if settings.is_redis_backend():
            return await self._redis_adapter.get_dialog_messages(user_id1, user_id2, limit, offset)
        else:
            return await self._get_messages_postgresql(user_id1, user_id2, limit, offset)
    
    async def get_recent_dialog_messages(self, user_id1: str, user_id2: str, 
                                       limit: int = 50) -> List[DialogMessageResponse]:
        """
        Получение последних сообщений диалога
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            limit: Количество последних сообщений
            
        Returns:
            Список последних сообщений
        """
        request_id = get_request_id()
        logger.info(
            f"Getting recent dialog messages between {user_id1} and {user_id2}",
            extra={"request_id": request_id, "limit": limit}
        )
        
        if settings.is_redis_backend():
            return await self._redis_adapter.get_recent_dialog_messages(user_id1, user_id2, limit)
        else:
            # Для PostgreSQL получаем последние сообщения через обычный метод
            messages = await self._get_messages_postgresql(user_id1, user_id2, limit, 0)
            return messages[-limit:] if len(messages) > limit else messages
    
    async def get_dialog_stats(self) -> DialogStatsResponse:
        """
        Получение статистики по диалогам
        
        Returns:
            Статистика диалогов
        """
        request_id = get_request_id()
        logger.info("Getting dialog statistics", extra={"request_id": request_id})
        
        if settings.is_redis_backend():
            stats = await self._redis_adapter.get_dialog_stats()
            return DialogStatsResponse(
                backend="Redis",
                total_dialogs=stats.get("total_dialogs"),
                total_messages=stats.get("total_messages"),
                avg_messages_per_dialog=stats.get("avg_messages_per_dialog")
            )
        else:
            return await self._get_stats_postgresql()
    
    # PostgreSQL методы
    async def _save_message_postgresql(self, from_user_id: str, to_user_id: str, text: str) -> str:
        """Сохранение сообщения в PostgreSQL"""
        message_id = str(uuid.uuid4())
        
        try:
            async with get_db_session() as session:
                new_message = DialogMessage(
                    id=message_id,
                    from_user_id=from_user_id,
                    to_user_id=to_user_id,
                    text=text,
                    created_at=datetime.utcnow()
                )
                session.add(new_message)
                await session.commit()
                
                logger.info(f"Message saved to PostgreSQL with ID: {message_id}")
                return message_id
                
        except SQLAlchemyError as e:
            logger.error(f"Error saving message to PostgreSQL: {e}")
            raise
    
    async def _get_messages_postgresql(self, user_id1: str, user_id2: str, 
                                     limit: int, offset: int) -> List[DialogMessageResponse]:
        """Получение сообщений из PostgreSQL"""
        try:
            async with get_db_session() as session:
                # Получаем сообщения между двумя пользователями
                query = select(DialogMessage).where(
                    ((DialogMessage.from_user_id == user_id1) & 
                     (DialogMessage.to_user_id == user_id2)) |
                    ((DialogMessage.from_user_id == user_id2) & 
                     (DialogMessage.to_user_id == user_id1))
                ).order_by(DialogMessage.created_at.asc()).offset(offset).limit(limit)
                
                result = await session.execute(query)
                messages = result.scalars().all()
                
                # Преобразуем в формат ответа API
                response_messages = []
                for msg in messages:
                    response_messages.append(
                        DialogMessageResponse(
                            from_user_id=str(msg.from_user_id),
                            to_user_id=str(msg.to_user_id),
                            text=msg.text,
                            created_at=msg.created_at
                        )
                    )
                
                logger.info(f"Retrieved {len(response_messages)} messages from PostgreSQL")
                return response_messages
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting messages from PostgreSQL: {e}")
            raise
    
    async def _get_stats_postgresql(self) -> DialogStatsResponse:
        """Получение статистики из PostgreSQL"""
        try:
            async with get_db_session() as session:
                # Общее количество сообщений
                total_messages_query = select(func.count(DialogMessage.id))
                total_messages_result = await session.execute(total_messages_query)
                total_messages = total_messages_result.scalar() or 0
                
                # Количество уникальных диалогов
                dialogs_query = select(func.count(func.distinct(
                    func.least(DialogMessage.from_user_id, DialogMessage.to_user_id).concat(
                        func.greatest(DialogMessage.from_user_id, DialogMessage.to_user_id)
                    )
                )))
                dialogs_result = await session.execute(dialogs_query)
                total_dialogs = dialogs_result.scalar() or 0
                
                # Среднее количество сообщений на диалог
                avg_messages = total_messages / total_dialogs if total_dialogs > 0 else 0
                
                return DialogStatsResponse(
                    backend="PostgreSQL",
                    total_dialogs=total_dialogs,
                    total_messages=total_messages,
                    avg_messages_per_dialog=round(avg_messages, 2)
                )
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting stats from PostgreSQL: {e}")
            raise


# Глобальный экземпляр сервиса
dialog_service = DialogService() 