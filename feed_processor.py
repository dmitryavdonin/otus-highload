import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, func
from models import Friendship
from db import get_slave_session
from rabbitmq_client import rabbitmq_client
from websocket_manager import websocket_manager
from message_queue import message_queue
from websocket_models import QueueEventType

logger = logging.getLogger(__name__)


class FeedProcessor:
    """Процессор для обработки событий ленты новостей"""
    
    def __init__(self):
        self.is_running = False
        self.processing_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить процессор"""
        if self.is_running:
            logger.warning("Feed processor is already running")
            return
        
        try:
            await rabbitmq_client.connect()
            self.is_running = True
            
            # Запускаем задачу обработки сообщений
            self.processing_task = asyncio.create_task(
                rabbitmq_client.consume_messages(
                    queue_name="feed_updates",
                    callback=self.handle_queue_message
                )
            )
            
            logger.info("Feed processor started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start feed processor: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Остановить процессор"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        await rabbitmq_client.disconnect()
        logger.info("Feed processor stopped")
    
    async def handle_queue_message(self, message: Dict[str, Any]):
        """
        Обработать сообщение из очереди
        
        Args:
            message: Сообщение из RabbitMQ
        """
        try:
            event_type = message.get("event_type")
            
            if event_type == "post_created":
                await self.handle_post_created_event(message)
            else:
                logger.warning(f"Unknown event type: {event_type}")
                
        except Exception as e:
            logger.error(f"Error handling queue message: {e}")
    
    async def handle_post_created_event(self, message: Dict[str, Any]):
        """
        Обработать событие создания поста
        
        Args:
            message: Сообщение о создании поста
        """
        try:
            # Извлекаем данные из сообщения
            post_id = message.get("post_id")
            post_text = message.get("post_text", "")
            author_user_id = message.get("author_user_id")
            created_at_str = message.get("created_at")
            
            if not all([post_id, author_user_id, created_at_str]):
                logger.error("Missing required fields in post_created event")
                return
            
            # Парсим дату
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            
            logger.info(f"Processing post created event: {post_id} by {author_user_id}")
            
            # Используем обработчик знаменитостей для обработки поста
            from celebrity_handler import celebrity_handler
            
            result = await celebrity_handler.handle_celebrity_post(
                post_id=post_id,
                post_text=post_text,
                author_user_id=author_user_id,
                created_at=created_at
            )
            
            # Логируем результат
            if result["success"]:
                logger.info(
                    f"Post {post_id} processed successfully: "
                    f"notified {result['friends_notified']}/{result['total_friends']} friends "
                    f"({'celebrity' if result['is_celebrity'] else 'regular'} user, "
                    f"{result['processing_method']} method)"
                )
            else:
                logger.error(f"Failed to process post {post_id}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error handling post created event: {e}")
    
    async def get_user_friends(self, user_id: str) -> List[str]:
        """
        Получить список друзей пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список ID друзей
        """
        try:
            async with get_slave_session() as session:
                query = select(Friendship.friend_id).where(Friendship.user_id == user_id)
                result = await session.execute(query)
                friend_ids = [str(row[0]) for row in result.fetchall()]
                return friend_ids
                
        except Exception as e:
            logger.error(f"Error getting user friends for {user_id}: {e}")
            return []
    
    async def get_user_friends_with_celebrity_check(self, user_id: str, 
                                                   celebrity_threshold: int = 1000) -> Dict[str, Any]:
        """
        Получить друзей пользователя с проверкой на статус знаменитости
        
        Args:
            user_id: ID пользователя
            celebrity_threshold: Порог для статуса знаменитости
            
        Returns:
            Словарь с информацией о друзьях и статусе знаменитости
        """
        try:
            async with get_slave_session() as session:
                # Получаем друзей и их количество одним запросом
                query = select(Friendship.friend_id).where(Friendship.user_id == user_id)
                result = await session.execute(query)
                friend_ids = [str(row[0]) for row in result.fetchall()]
                
                friends_count = len(friend_ids)
                is_celebrity = friends_count >= celebrity_threshold
                
                return {
                    "friend_ids": friend_ids,
                    "friends_count": friends_count,
                    "is_celebrity": is_celebrity,
                    "celebrity_threshold": celebrity_threshold
                }
                
        except Exception as e:
            logger.error(f"Error getting user friends with celebrity check for {user_id}: {e}")
            return {
                "friend_ids": [],
                "friends_count": 0,
                "is_celebrity": False,
                "celebrity_threshold": celebrity_threshold
            }
    
    async def process_celebrity_post(self, post_id: str, post_text: str, 
                                   author_user_id: str, created_at: datetime,
                                   friend_ids: List[str], batch_size: int = 100,
                                   batch_delay: float = 0.1) -> Dict[str, Any]:
        """
        Обработать пост знаменитости с батчевой отправкой
        
        Args:
            post_id: ID поста
            post_text: Текст поста
            author_user_id: ID автора
            created_at: Время создания
            friend_ids: Список ID друзей
            batch_size: Размер батча
            batch_delay: Задержка между батчами
            
        Returns:
            Статистика обработки
        """
        try:
            total_friends = len(friend_ids)
            total_sent = 0
            batches_processed = 0
            
            logger.info(
                f"Processing celebrity post {post_id}: "
                f"{total_friends} friends, batch size: {batch_size}"
            )
            
            # Разбиваем друзей на батчи
            for i in range(0, total_friends, batch_size):
                batch_friends = friend_ids[i:i + batch_size]
                
                # Фильтруем только подключенных друзей
                connected_friends = [
                    friend_id for friend_id in batch_friends
                    if websocket_manager.is_user_connected(friend_id)
                ]
                
                if connected_friends:
                    # Отправляем уведомления батчу
                    sent_count = await websocket_manager.send_post_created_notification(
                        user_ids=connected_friends,
                        post_id=post_id,
                        post_text=post_text,
                        author_user_id=author_user_id,
                        created_at=created_at
                    )
                    
                    total_sent += sent_count
                
                batches_processed += 1
                
                # Задержка между батчами
                if i + batch_size < total_friends:
                    await asyncio.sleep(batch_delay)
            
            logger.info(
                f"Celebrity post {post_id} processed: "
                f"sent to {total_sent} friends in {batches_processed} batches"
            )
            
            return {
                "success": True,
                "friends_notified": total_sent,
                "total_friends": total_friends,
                "batches_processed": batches_processed
            }
            
        except Exception as e:
            logger.error(f"Error processing celebrity post: {e}")
            return {
                "success": False,
                "error": str(e),
                "friends_notified": 0,
                "total_friends": len(friend_ids)
            }
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """
        Получить статистику обработки
        
        Returns:
            Статистика процессора
        """
        return {
            "is_running": self.is_running,
            "has_processing_task": self.processing_task is not None,
            "task_done": self.processing_task.done() if self.processing_task else None,
            "rabbitmq_connected": rabbitmq_client.is_connected(),
            "websocket_connections": websocket_manager.get_connection_count()
        }


# Глобальный экземпляр процессора
feed_processor = FeedProcessor() 