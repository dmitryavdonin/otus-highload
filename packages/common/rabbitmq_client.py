import asyncio
import json
import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from packages.common.message_queue import message_queue

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """Клиент для работы с RabbitMQ (обертка над message_queue)"""
    
    def __init__(self):
        self.message_queue = message_queue
        self._consumers = {}
    
    async def connect(self) -> bool:
        """
        Подключиться к RabbitMQ
        
        Returns:
            True если подключение успешно, False иначе
        """
        try:
            success = await self.message_queue.connect()
            if success:
                logger.info("RabbitMQ client connected successfully")
            else:
                logger.error("Failed to connect RabbitMQ client")
            return success
        except Exception as e:
            logger.error(f"Error connecting RabbitMQ client: {e}")
            return False
    
    async def disconnect(self):
        """Отключиться от RabbitMQ"""
        try:
            await self.message_queue.disconnect()
            logger.info("RabbitMQ client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting RabbitMQ client: {e}")
    
    async def publish_event(self, queue_name: str, event_data: Dict[str, Any]) -> bool:
        """
        Опубликовать событие в очередь
        
        Args:
            queue_name: Имя очереди
            event_data: Данные события
            
        Returns:
            True если событие опубликовано, False иначе
        """
        try:
            # Определяем тип события
            event_type = event_data.get("event_type")
            
            if event_type == "post_created":
                # Используем специальный метод для постов
                success = await self.message_queue.publish_post_created_event(
                    post_id=event_data.get("post_id"),
                    post_text=event_data.get("post_text", ""),
                    author_user_id=event_data.get("author_user_id"),
                    created_at=datetime.fromisoformat(
                        event_data.get("created_at", datetime.now().isoformat())
                    )
                )
            else:
                # Для других типов событий используем общий метод
                from websocket_models import QueueEvent
                
                event = QueueEvent(
                    event_type=event_type,
                    user_id=event_data.get("user_id", event_data.get("author_user_id", "")),
                    data=event_data,
                    routing_key=f"user.{event_data.get('author_user_id', 'unknown')}.{event_type}"
                )
                
                success = await self.message_queue.publish_event(event)
            
            if success:
                logger.info(f"Published event to {queue_name}: {event_type}")
            else:
                logger.error(f"Failed to publish event to {queue_name}: {event_type}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error publishing event to {queue_name}: {e}")
            return False
    
    async def consume_messages(self, queue_name: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Начать потребление сообщений из очереди
        
        Args:
            queue_name: Имя очереди
            callback: Функция обратного вызова для обработки сообщений
        """
        try:
            logger.info(f"Starting to consume messages from {queue_name}")
            
            # Сохраняем callback для этой очереди
            self._consumers[queue_name] = callback
            
            # Запускаем потребление через message_queue
            await self.message_queue.start_consuming(callback)
            
        except Exception as e:
            logger.error(f"Error consuming messages from {queue_name}: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Проверить, подключены ли мы к RabbitMQ"""
        return self.message_queue.is_connected()
    
    async def create_queue(self, queue_name: str, durable: bool = True) -> bool:
        """
        Создать очередь
        
        Args:
            queue_name: Имя очереди
            durable: Устойчивость очереди
            
        Returns:
            True если очередь создана, False иначе
        """
        try:
            # В нашей реализации очереди создаются автоматически
            logger.info(f"Queue {queue_name} will be created automatically")
            return True
        except Exception as e:
            logger.error(f"Error creating queue {queue_name}: {e}")
            return False
    
    async def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """
        Получить информацию об очереди
        
        Args:
            queue_name: Имя очереди
            
        Returns:
            Информация об очереди
        """
        try:
            stats = await self.message_queue.get_queue_stats()
            return {
                "queue_name": queue_name,
                "connected": stats.get("connected", False),
                "messages": stats.get("feed_queue_messages", 0),
                "status": stats.get("connection_status", "unknown")
            }
        except Exception as e:
            logger.error(f"Error getting queue info for {queue_name}: {e}")
            return {
                "queue_name": queue_name,
                "error": str(e)
            }


# Глобальный экземпляр клиента
rabbitmq_client = RabbitMQClient() 