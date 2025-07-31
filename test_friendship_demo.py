#!/usr/bin/env python3
"""
Демонстрационный скрипт для тестирования взаимодействия пользователей
через WebSocket - добавление в друзья и получение уведомлений о постах.
"""

import asyncio
import json
import logging
import websockets
import aiohttp
import time
from datetime import datetime
from typing import Dict, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
WEBSOCKET_URL = "ws://localhost:8001"
HTTP_URL = "http://localhost:8001"

class User:
    """Класс для представления пользователя"""
    
    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name
        self.websocket = None
        self.connected = False
        self.messages_received = []
        
    async def connect(self):
        """Подключение к WebSocket серверу"""
        try:
            uri = f"{WEBSOCKET_URL}/ws/{self.user_id}?token={self.user_id}:test_signature"
            logger.info(f"👤 {self.name} подключается к WebSocket...")
            
            self.websocket = await websockets.connect(uri)
            self.connected = True
            
            # Получаем приветственное сообщение
            welcome_msg = await self.websocket.recv()
            welcome_data = json.loads(welcome_msg)
            logger.info(f"✅ {self.name} подключен! Приветствие: {welcome_data.get('data', {}).get('message', 'N/A')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения {self.name}: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от WebSocket сервера"""
        if self.websocket and self.connected:
            await self.websocket.close()
            self.connected = False
            logger.info(f"👋 {self.name} отключен от WebSocket")
    
    async def send_message(self, message: Dict[str, Any]):
        """Отправка сообщения через WebSocket"""
        if self.websocket and self.connected:
            await self.websocket.send(json.dumps(message))
    
    async def listen_for_messages(self):
        """Прослушивание входящих сообщений"""
        try:
            while self.connected and self.websocket:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    self.messages_received.append(data)
                    
                    # Обработка разных типов сообщений
                    msg_type = data.get('type')
                    msg_data = data.get('data', {})
                    
                    if msg_type == 'feed_update':
                        post_data = msg_data.get('post', {})
                        author = post_data.get('author_user_id', 'Unknown')
                        text = post_data.get('post_text', 'No text')
                        logger.info(f"📢 {self.name} получил уведомление о посте от {author}: '{text}'")
                        
                    elif msg_type == 'friendship_update':
                        friend_id = msg_data.get('friend_user_id', 'Unknown')
                        action = msg_data.get('action', 'unknown')
                        logger.info(f"👥 {self.name} получил уведомление о дружбе: {action} с {friend_id}")
                        
                    elif msg_type == 'system':
                        message_text = msg_data.get('message', '')
                        if message_text not in ['pong', 'subscribed_to_feed']:
                            logger.info(f"🔧 {self.name} получил системное сообщение: {message_text}")
                    
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"🔌 Соединение {self.name} закрыто")
                    break
                except Exception as e:
                    logger.error(f"❌ Ошибка при получении сообщения {self.name}: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в прослушивании сообщений {self.name}: {e}")

async def add_friendship(user1_id: str, user2_id: str):
    """Добавление дружбы между пользователями через HTTP API"""
    try:
        # Имитируем добавление в друзья через RabbitMQ
        friendship_event = {
            "event_type": "friendship_created",
            "user_id": user1_id,
            "friend_user_id": user2_id,
            "created_at": datetime.now().isoformat()
        }
        
        # Отправляем событие через тестовый endpoint
        async with aiohttp.ClientSession() as session:
            # Публикуем событие дружбы для первого пользователя
            async with session.post(
                f"{HTTP_URL}/test-friendship",
                json=friendship_event
            ) as response:
                if response.status == 200:
                    logger.info(f"👥 Дружба добавлена: {user1_id} ↔ {user2_id}")
                    return True
                else:
                    logger.error(f"❌ Ошибка добавления дружбы: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении дружбы: {e}")
        return False

async def create_post(author_id: str, post_text: str, post_id: str = None):
    """Создание поста через HTTP API"""
    try:
        if not post_id:
            post_id = f"post_{int(time.time())}"
            
        async with aiohttp.ClientSession() as session:
            params = {
                "post_id": post_id,
                "author_user_id": author_id,
                "post_text": post_text
            }
            
            async with session.post(f"{HTTP_URL}/test-post", params=params) as response:
                if response.status == 200:
                    logger.info(f"📝 Пост создан: {author_id} написал '{post_text}'")
                    return True
                else:
                    logger.error(f"❌ Ошибка создания поста: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Ошибка при создании поста: {e}")
        return False

async def check_server_health():
    """Проверка здоровья сервера"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{HTTP_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"🏥 Сервер здоров: {data.get('status', 'unknown')}")
                    return True
                else:
                    logger.error(f"❌ Сервер нездоров: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Ошибка проверки здоровья сервера: {e}")
        return False

async def main():
    """Основная функция демонстрации"""
    logger.info("🎭 Запуск демонстрации взаимодействия пользователей")
    logger.info("=" * 60)
    
    # Проверяем здоровье сервера
    if not await check_server_health():
        logger.error("❌ Сервер недоступен. Убедитесь, что WebSocket сервер запущен.")
        return
    
    # Создаем двух пользователей
    alice = User("alice_123", "Алиса")
    bob = User("bob_456", "Боб")
    
    try:
        # Этап 1: Подключение пользователей
        logger.info("\n🔌 Этап 1: Подключение пользователей к WebSocket")
        logger.info("-" * 40)
        
        alice_connected = await alice.connect()
        bob_connected = await bob.connect()
        
        if not (alice_connected and bob_connected):
            logger.error("❌ Не удалось подключить всех пользователей")
            return
        
        # Запускаем прослушивание сообщений в фоне
        alice_listener = asyncio.create_task(alice.listen_for_messages())
        bob_listener = asyncio.create_task(bob.listen_for_messages())
        
        await asyncio.sleep(2)
        
        # Этап 2: Добавление в друзья
        logger.info("\n👥 Этап 2: Добавление в друзья")
        logger.info("-" * 40)
        
        # Алиса добавляет Боба в друзья
        await add_friendship("alice_123", "bob_456")
        await asyncio.sleep(2)
        
        # Боб добавляет Алису в друзья (взаимная дружба)
        await add_friendship("bob_456", "alice_123")
        await asyncio.sleep(2)
        
        # Этап 3: Создание постов
        logger.info("\n📝 Этап 3: Создание постов и получение уведомлений")
        logger.info("-" * 40)
        
        # Алиса создает пост
        await create_post("alice_123", "Привет всем! Это мой первый пост 🎉")
        await asyncio.sleep(3)
        
        # Боб создает пост
        await create_post("bob_456", "Отличная погода сегодня! ☀️")
        await asyncio.sleep(3)
        
        # Алиса создает еще один пост
        await create_post("alice_123", "Изучаю WebSocket технологии 💻")
        await asyncio.sleep(3)
        
        # Боб отвечает
        await create_post("bob_456", "WebSocket это круто! Реальное время 🚀")
        await asyncio.sleep(3)
        
        # Этап 4: Статистика
        logger.info("\n📊 Этап 4: Статистика полученных сообщений")
        logger.info("-" * 40)
        
        logger.info(f"📬 Алиса получила {len(alice.messages_received)} сообщений")
        logger.info(f"📬 Боб получил {len(bob.messages_received)} сообщений")
        
        # Показываем последние сообщения
        for i, msg in enumerate(alice.messages_received[-3:], 1):
            msg_type = msg.get('type', 'unknown')
            logger.info(f"  📨 Алиса #{i}: {msg_type}")
            
        for i, msg in enumerate(bob.messages_received[-3:], 1):
            msg_type = msg.get('type', 'unknown')
            logger.info(f"  📨 Боб #{i}: {msg_type}")
        
        logger.info("\n🎉 Демонстрация завершена успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в демонстрации: {e}")
        
    finally:
        # Отключаем пользователей
        logger.info("\n👋 Отключение пользователей...")
        
        # Отменяем задачи прослушивания
        if 'alice_listener' in locals():
            alice_listener.cancel()
        if 'bob_listener' in locals():
            bob_listener.cancel()
            
        await alice.disconnect()
        await bob.disconnect()
        
        logger.info("✅ Все пользователи отключены")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️  Демонстрация прервана пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}") 