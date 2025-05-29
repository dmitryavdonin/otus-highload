import asyncio
import json
import logging
import os
from typing import Dict, Any, Callable, Optional
from datetime import datetime
import aio_pika
from aio_pika import Message, ExchangeType, DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractExchange, AbstractQueue
from dotenv import load_dotenv
from websocket_models import QueueEvent, PostCreatedQueueEvent

load_dotenv()

logger = logging.getLogger(__name__)

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "admin123")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "social_network")

# Exchange and queue names
POSTS_EXCHANGE = "posts_exchange"
FEED_QUEUE = "feed_processing_queue"


class MessageQueue:
    """Класс для работы с RabbitMQ очередями"""
    
    def __init__(self):
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.posts_exchange: Optional[AbstractExchange] = None
        self.feed_queue: Optional[AbstractQueue] = None
        self._is_connected = False
    
    async def connect(self) -> bool:
        """
        Подключиться к RabbitMQ
        
        Returns:
            True если подключение успешно, False иначе
        """
        try:
            # Создаем подключение
            self.connection = await aio_pika.connect_robust(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                login=RABBITMQ_USER,
                password=RABBITMQ_PASSWORD,
                virtualhost=RABBITMQ_VHOST,
                heartbeat=60,
                blocked_connection_timeout=300,
            )
            
            # Создаем канал
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            
            # Создаем exchange для постов
            self.posts_exchange = await self.channel.declare_exchange(
                POSTS_EXCHANGE,
                ExchangeType.TOPIC,
                durable=True
            )
            
            # Создаем очередь для обработки ленты
            self.feed_queue = await self.channel.declare_queue(
                FEED_QUEUE,
                durable=True,
                arguments={
                    "x-message-ttl": 3600000,  # TTL 1 час
                    "x-max-length": 10000,     # Максимум 10k сообщений
                }
            )
            
            # Привязываем очередь к exchange
            await self.feed_queue.bind(
                self.posts_exchange,
                routing_key="user.*.post.created"
            )
            
            self._is_connected = True
            logger.info("Successfully connected to RabbitMQ")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            self._is_connected = False
            return False
    
    async def disconnect(self):
        """Отключиться от RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
            self._is_connected = False
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    async def publish_post_created_event(self, post_id: str, post_text: str, 
                                       author_user_id: str, created_at: datetime) -> bool:
        """
        Опубликовать событие создания поста
        
        Args:
            post_id: ID поста
            post_text: Текст поста
            author_user_id: ID автора
            created_at: Время создания
            
        Returns:
            True если событие опубликовано, False иначе
        """
        if not self._is_connected or not self.posts_exchange:
            logger.error("Not connected to RabbitMQ")
            return False
        
        try:
            # Создаем событие
            event = PostCreatedQueueEvent.create(
                post_id=post_id,
                post_text=post_text,
                author_user_id=author_user_id,
                created_at=created_at
            )
            
            # Сериализуем в JSON
            message_body = event.model_dump_json()
            
            # Создаем сообщение
            message = Message(
                message_body.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={
                    "event_type": event.event_type,
                    "user_id": event.user_id,
                    "timestamp": event.timestamp.isoformat()
                }
            )
            
            # Публикуем сообщение
            await self.posts_exchange.publish(
                message,
                routing_key=event.routing_key
            )
            
            logger.info(f"Published post created event: {post_id} by user {author_user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing post created event: {e}")
            return False
    
    async def publish_event(self, event: QueueEvent) -> bool:
        """
        Опубликовать произвольное событие
        
        Args:
            event: Событие для публикации
            
        Returns:
            True если событие опубликовано, False иначе
        """
        if not self._is_connected or not self.posts_exchange:
            logger.error("Not connected to RabbitMQ")
            return False
        
        try:
            # Сериализуем в JSON
            message_body = event.model_dump_json()
            
            # Создаем сообщение
            message = Message(
                message_body.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={
                    "event_type": event.event_type,
                    "user_id": event.user_id,
                    "timestamp": event.timestamp.isoformat()
                }
            )
            
            # Публикуем сообщение
            await self.posts_exchange.publish(
                message,
                routing_key=event.routing_key
            )
            
            logger.info(f"Published event: {event.event_type} for user {event.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            return False
    
    async def start_consuming(self, message_handler: Callable[[Dict[str, Any]], None]):
        """
        Начать обработку сообщений из очереди
        
        Args:
            message_handler: Функция для обработки сообщений
        """
        if not self._is_connected or not self.feed_queue:
            logger.error("Not connected to RabbitMQ")
            return
        
        async def process_message(message: aio_pika.IncomingMessage):
            """Обработать входящее сообщение"""
            try:
                async with message.process():
                    # Декодируем сообщение
                    body = message.body.decode()
                    data = json.loads(body)
                    
                    logger.debug(f"Processing message: {data.get('event_type', 'unknown')}")
                    
                    # Вызываем обработчик
                    await message_handler(data)
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Сообщение будет отклонено и может быть повторно обработано
                raise
        
        # Начинаем потребление сообщений
        await self.feed_queue.consume(process_message)
        logger.info("Started consuming messages from feed queue")
    
    async def create_user_specific_queue(self, user_id: str) -> Optional[AbstractQueue]:
        """
        Создать очередь для конкретного пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Очередь или None при ошибке
        """
        if not self._is_connected or not self.channel:
            logger.error("Not connected to RabbitMQ")
            return None
        
        try:
            queue_name = f"user_{user_id}_feed"
            
            # Создаем очередь для пользователя
            user_queue = await self.channel.declare_queue(
                queue_name,
                durable=False,  # Временная очередь
                auto_delete=True,  # Удаляется при отключении
                arguments={
                    "x-message-ttl": 300000,  # TTL 5 минут
                    "x-max-length": 100,      # Максимум 100 сообщений
                }
            )
            
            # Привязываем к exchange с routing key для друзей этого пользователя
            await user_queue.bind(
                self.posts_exchange,
                routing_key=f"user.*.post.created"
            )
            
            logger.info(f"Created user-specific queue: {queue_name}")
            return user_queue
            
        except Exception as e:
            logger.error(f"Error creating user queue for {user_id}: {e}")
            return None
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Получить статистику очередей
        
        Returns:
            Словарь со статистикой
        """
        stats = {
            "connected": self._is_connected,
            "feed_queue_messages": 0,
            "connection_status": "disconnected"
        }
        
        if self._is_connected and self.feed_queue:
            try:
                # Получаем информацию об очереди
                queue_info = await self.feed_queue.channel.queue_declare(
                    FEED_QUEUE, 
                    passive=True
                )
                stats["feed_queue_messages"] = queue_info.method.message_count
                stats["connection_status"] = "connected"
                
            except Exception as e:
                logger.error(f"Error getting queue stats: {e}")
        
        return stats
    
    def is_connected(self) -> bool:
        """Проверить, подключены ли мы к RabbitMQ"""
        return self._is_connected and self.connection and not self.connection.is_closed


# Глобальный экземпляр очереди сообщений
message_queue = MessageQueue() 