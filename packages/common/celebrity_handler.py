import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from feed_processor import FeedProcessor
from websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class CelebrityHandler:
    """Обработчик для популярных пользователей (эффект Леди Гаги)"""
    
    def __init__(self, celebrity_threshold: int = 1000, batch_size: int = 100, 
                 batch_delay: float = 0.1):
        """
        Инициализация обработчика знаменитостей
        
        Args:
            celebrity_threshold: Порог количества друзей для статуса знаменитости
            batch_size: Размер батча для обработки друзей
            batch_delay: Задержка между батчами в секундах
        """
        self.celebrity_threshold = celebrity_threshold
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.feed_processor = FeedProcessor()
    
    async def handle_celebrity_post(self, post_id: str, post_text: str, 
                                  author_user_id: str, created_at: datetime) -> Dict[str, Any]:
        """
        Обработать пост от знаменитости
        
        Args:
            post_id: ID поста
            post_text: Текст поста
            author_user_id: ID автора
            created_at: Время создания поста
            
        Returns:
            Статистика обработки
        """
        try:
            # Получаем информацию о друзьях с проверкой на знаменитость
            friends_info = await self.feed_processor.get_user_friends_with_celebrity_check(
                author_user_id, self.celebrity_threshold
            )
            
            friend_ids = friends_info["friend_ids"]
            is_celebrity = friends_info["is_celebrity"]
            friends_count = friends_info["friends_count"]
            
            logger.info(
                f"Processing post from {'celebrity' if is_celebrity else 'regular user'} "
                f"{author_user_id}: {friends_count} friends"
            )
            
            if not is_celebrity:
                # Обычный пользователь - стандартная обработка
                return await self._handle_regular_user_post(
                    post_id, post_text, author_user_id, created_at, friend_ids
                )
            else:
                # Знаменитость - батчевая обработка
                return await self._handle_celebrity_post_batched(
                    post_id, post_text, author_user_id, created_at, friend_ids
                )
                
        except Exception as e:
            logger.error(f"Error handling celebrity post: {e}")
            return {
                "success": False,
                "error": str(e),
                "friends_notified": 0,
                "total_friends": 0,
                "is_celebrity": False
            }
    
    async def _handle_regular_user_post(self, post_id: str, post_text: str, 
                                      author_user_id: str, created_at: datetime,
                                      friend_ids: List[str]) -> Dict[str, Any]:
        """
        Обработать пост обычного пользователя
        
        Args:
            post_id: ID поста
            post_text: Текст поста
            author_user_id: ID автора
            created_at: Время создания
            friend_ids: Список ID друзей
            
        Returns:
            Статистика обработки
        """
        try:
            # Фильтруем только подключенных друзей
            connected_friends = [
                friend_id for friend_id in friend_ids
                if websocket_manager.is_user_connected(friend_id)
            ]
            
            # Отправляем уведомления всем сразу
            sent_count = 0
            if connected_friends:
                sent_count = await websocket_manager.send_post_created_notification(
                    user_ids=connected_friends,
                    post_id=post_id,
                    post_text=post_text,
                    author_user_id=author_user_id,
                    created_at=created_at
                )
            
            logger.info(
                f"Regular user post processed: sent to {sent_count}/{len(connected_friends)} "
                f"connected friends out of {len(friend_ids)} total friends"
            )
            
            return {
                "success": True,
                "friends_notified": sent_count,
                "connected_friends": len(connected_friends),
                "total_friends": len(friend_ids),
                "is_celebrity": False,
                "processing_method": "standard"
            }
            
        except Exception as e:
            logger.error(f"Error handling regular user post: {e}")
            raise
    
    async def _handle_celebrity_post_batched(self, post_id: str, post_text: str, 
                                           author_user_id: str, created_at: datetime,
                                           friend_ids: List[str]) -> Dict[str, Any]:
        """
        Обработать пост знаменитости с батчевой отправкой
        
        Args:
            post_id: ID поста
            post_text: Текст поста
            author_user_id: ID автора
            created_at: Время создания
            friend_ids: Список ID друзей
            
        Returns:
            Статистика обработки
        """
        try:
            total_friends = len(friend_ids)
            total_sent = 0
            total_connected = 0
            batches_processed = 0
            
            logger.info(
                f"Starting batched processing for celebrity {author_user_id}: "
                f"{total_friends} friends, batch size: {self.batch_size}"
            )
            
            # Разбиваем друзей на батчи
            for i in range(0, total_friends, self.batch_size):
                batch_friends = friend_ids[i:i + self.batch_size]
                batch_number = i // self.batch_size + 1
                
                # Фильтруем только подключенных друзей в этом батче
                connected_batch = [
                    friend_id for friend_id in batch_friends
                    if websocket_manager.is_user_connected(friend_id)
                ]
                
                total_connected += len(connected_batch)
                
                if connected_batch:
                    # Отправляем уведомления батчу
                    sent_count = await websocket_manager.send_post_created_notification(
                        user_ids=connected_batch,
                        post_id=post_id,
                        post_text=post_text,
                        author_user_id=author_user_id,
                        created_at=created_at
                    )
                    
                    total_sent += sent_count
                    
                    logger.debug(
                        f"Celebrity batch {batch_number}: "
                        f"sent to {sent_count}/{len(connected_batch)} users"
                    )
                
                batches_processed += 1
                
                # Задержка между батчами для снижения нагрузки
                if i + self.batch_size < total_friends:
                    await asyncio.sleep(self.batch_delay)
            
            logger.info(
                f"Celebrity post processing completed: "
                f"sent to {total_sent}/{total_connected} connected friends "
                f"out of {total_friends} total friends in {batches_processed} batches"
            )
            
            return {
                "success": True,
                "friends_notified": total_sent,
                "connected_friends": total_connected,
                "total_friends": total_friends,
                "is_celebrity": True,
                "processing_method": "batched",
                "batches_processed": batches_processed,
                "batch_size": self.batch_size,
                "batch_delay": self.batch_delay
            }
            
        except Exception as e:
            logger.error(f"Error handling celebrity post batched: {e}")
            raise
    
    async def get_celebrity_stats(self) -> Dict[str, Any]:
        """
        Получить статистику по знаменитостям
        
        Returns:
            Статистика знаменитостей
        """
        try:
            from sqlalchemy import select, func
            from models import Friendship
            from db import get_slave_session
            
            async with get_slave_session() as session:
                # Запрос для получения пользователей с количеством друзей
                query = (
                    select(
                        Friendship.user_id,
                        func.count(Friendship.friend_id).label('friends_count')
                    )
                    .group_by(Friendship.user_id)
                    .having(func.count(Friendship.friend_id) >= self.celebrity_threshold)
                    .order_by(func.count(Friendship.friend_id).desc())
                )
                
                result = await session.execute(query)
                celebrities = result.fetchall()
                
                # Статистика
                total_celebrities = len(celebrities)
                max_friends = celebrities[0].friends_count if celebrities else 0
                avg_friends = sum(c.friends_count for c in celebrities) / total_celebrities if celebrities else 0
                
                return {
                    "celebrity_threshold": self.celebrity_threshold,
                    "total_celebrities": total_celebrities,
                    "max_friends": max_friends,
                    "avg_celebrity_friends": round(avg_friends, 2),
                    "batch_size": self.batch_size,
                    "batch_delay": self.batch_delay,
                    "celebrities": [
                        {
                            "user_id": str(c.user_id),
                            "friends_count": c.friends_count
                        }
                        for c in celebrities[:10]  # Топ 10
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error getting celebrity stats: {e}")
            return {
                "error": str(e),
                "celebrity_threshold": self.celebrity_threshold
            }
    
    def update_settings(self, celebrity_threshold: int = None, 
                       batch_size: int = None, batch_delay: float = None):
        """
        Обновить настройки обработчика
        
        Args:
            celebrity_threshold: Новый порог знаменитости
            batch_size: Новый размер батча
            batch_delay: Новая задержка между батчами
        """
        if celebrity_threshold is not None:
            self.celebrity_threshold = celebrity_threshold
            logger.info(f"Updated celebrity threshold to {celebrity_threshold}")
        
        if batch_size is not None:
            self.batch_size = batch_size
            logger.info(f"Updated batch size to {batch_size}")
        
        if batch_delay is not None:
            self.batch_delay = batch_delay
            logger.info(f"Updated batch delay to {batch_delay}")
    
    async def is_user_celebrity(self, user_id: str) -> bool:
        """
        Проверить, является ли пользователь знаменитостью
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь знаменитость, False иначе
        """
        try:
            friends_info = await self.feed_processor.get_user_friends_with_celebrity_check(
                user_id, self.celebrity_threshold
            )
            return friends_info["is_celebrity"]
        except Exception as e:
            logger.error(f"Error checking celebrity status for user {user_id}: {e}")
            return False


# Глобальный экземпляр обработчика знаменитостей
celebrity_handler = CelebrityHandler() 