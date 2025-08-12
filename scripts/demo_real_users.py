#!/usr/bin/env python3
"""
Демонстрационный скрипт для тестирования реального взаимодействия пользователей
через ваше приложение - регистрация, добавление в друзья, создание постов
и получение уведомлений через WebSocket.
"""

import asyncio
import json
import logging
import websockets
import aiohttp
import time
from datetime import datetime, date
from typing import Dict, Any, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
MAIN_API_URL = "http://localhost:9000"  # Ваше основное приложение в Docker
WEBSOCKET_URL = "ws://localhost:8001"   # WebSocket сервер
HTTP_WS_URL = "http://localhost:8001"   # HTTP API WebSocket сервера

class DemoUser:
    """Класс для представления пользователя в демонстрации"""
    
    def __init__(self, first_name: str, second_name: str, city: str, password: str):
        self.first_name = first_name
        self.second_name = second_name
        self.city = city
        self.password = password
        self.birthdate = "1990-01-01"
        self.biography = f"Пользователь {first_name} для демонстрации"
        
        # Данные после регистрации
        self.user_id = None
        self.token = None
        
        # WebSocket соединение
        self.websocket = None
        self.connected = False
        self.messages_received = []
        
    async def register(self):
        """Регистрация пользователя через API"""
        try:
            user_data = {
                "first_name": self.first_name,
                "second_name": self.second_name,
                "birthdate": self.birthdate,
                "biography": self.biography,
                "city": self.city,
                "password": self.password
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{MAIN_API_URL}/user/register", json=user_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.user_id = data["id"]
                        logger.info(f"✅ Пользователь {self.first_name} зарегистрирован с ID: {self.user_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка регистрации {self.first_name}: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Исключение при регистрации {self.first_name}: {e}")
            return False
    
    async def login(self):
        """Авторизация пользователя и получение токена"""
        try:
            login_data = {
                "id": self.user_id,
                "password": self.password
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{MAIN_API_URL}/user/login", json=login_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.token = data["token"]
                        logger.info(f"✅ Пользователь {self.first_name} авторизован")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка авторизации {self.first_name}: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Исключение при авторизации {self.first_name}: {e}")
            return False
    
    async def add_friend(self, friend_user_id: str):
        """Добавление друга через API"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.put(f"{MAIN_API_URL}/friend/set/{friend_user_id}", headers=headers) as response:
                    if response.status == 200:
                        logger.info(f"✅ {self.first_name} добавил в друзья пользователя {friend_user_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка добавления друга {self.first_name}: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Исключение при добавлении друга {self.first_name}: {e}")
            return False
    
    async def create_post(self, text: str):
        """Создание поста через API"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            post_data = {"text": text}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{MAIN_API_URL}/post/create", json=post_data, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        post_id = data["id"]
                        logger.info(f"📝 {self.first_name} создал пост: '{text}' (ID: {post_id})")
                        return post_id
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка создания поста {self.first_name}: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Исключение при создании поста {self.first_name}: {e}")
            return None
    
    async def connect_websocket(self):
        """Подключение к WebSocket серверу"""
        try:
            uri = f"{WEBSOCKET_URL}/ws/{self.user_id}?token={self.user_id}:test_signature"
            logger.info(f"🔌 {self.first_name} подключается к WebSocket...")
            
            self.websocket = await websockets.connect(uri)
            self.connected = True
            
            # Получаем приветственное сообщение
            welcome_msg = await self.websocket.recv()
            welcome_data = json.loads(welcome_msg)
            logger.info(f"✅ {self.first_name} подключен к WebSocket! Приветствие: {welcome_data.get('data', {}).get('message', 'N/A')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения {self.first_name} к WebSocket: {e}")
            return False
    
    async def disconnect_websocket(self):
        """Отключение от WebSocket сервера"""
        if self.websocket and self.connected:
            await self.websocket.close()
            self.connected = False
            logger.info(f"👋 {self.first_name} отключен от WebSocket")
    
    async def listen_for_messages(self):
        """Прослушивание входящих WebSocket сообщений"""
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
                        logger.info(f"📢 {self.first_name} получил уведомление о новом посте от {author}: '{text}'")
                        
                    elif msg_type == 'friendship_update':
                        friend_id = msg_data.get('friend_user_id', 'Unknown')
                        action = msg_data.get('action', 'unknown')
                        logger.info(f"👥 {self.first_name} получил уведомление о дружбе: {action} с {friend_id}")
                        
                    elif msg_type == 'system':
                        message_text = msg_data.get('message', '')
                        if message_text not in ['pong', 'subscribed_to_feed', 'Connected successfully']:
                            logger.info(f"🔧 {self.first_name} получил системное сообщение: {message_text}")
                    
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"🔌 WebSocket соединение {self.first_name} закрыто")
                    break
                except Exception as e:
                    logger.error(f"❌ Ошибка при получении сообщения {self.first_name}: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в прослушивании сообщений {self.first_name}: {e}")

async def check_services():
    """Проверка доступности сервисов"""
    logger.info("🔍 Проверка доступности сервисов...")
    
    # Проверяем основное API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MAIN_API_URL}/docs") as response:
                if response.status == 200:
                    logger.info("✅ Основное API доступно")
                else:
                    logger.error(f"❌ Основное API недоступно: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к основному API: {e}")
        return False
    
    # Проверяем WebSocket сервер
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{HTTP_WS_URL}/health") as response:
                if response.status == 200:
                    logger.info("✅ WebSocket сервер доступен")
                else:
                    logger.error(f"❌ WebSocket сервер недоступен: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к WebSocket серверу: {e}")
        return False
    
    return True

async def trigger_post_notification(post_id: str, author_user_id: str, post_text: str):
    """Отправка уведомления о посте через WebSocket сервер"""
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "post_id": post_id,
                "author_user_id": author_user_id,
                "post_text": post_text
            }
            
            async with session.post(f"{HTTP_WS_URL}/test-post", params=params) as response:
                if response.status == 200:
                    logger.info(f"📡 Уведомление о посте отправлено через WebSocket сервер")
                    return True
                else:
                    logger.error(f"❌ Ошибка отправки уведомления: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления: {e}")
        return False

async def main():
    """Основная функция демонстрации"""
    logger.info("🎭 Запуск демонстрации реального взаимодействия пользователей")
    logger.info("=" * 70)
    
    # Проверяем доступность сервисов
    if not await check_services():
        logger.error("❌ Не все сервисы доступны. Убедитесь, что запущены:")
        logger.error("   - Основное приложение на порту 9000")
        logger.error("   - WebSocket сервер на порту 8001")
        return
    
    # Создаем двух пользователей
    alice = DemoUser("Алиса", "Иванова", "Москва", "password123")
    bob = DemoUser("Боб", "Петров", "Санкт-Петербург", "password456")
    
    try:
        # Этап 1: Регистрация пользователей
        logger.info("\n👤 Этап 1: Регистрация пользователей")
        logger.info("-" * 50)
        
        alice_registered = await alice.register()
        bob_registered = await bob.register()
        
        if not (alice_registered and bob_registered):
            logger.error("❌ Не удалось зарегистрировать всех пользователей")
            return
        
        await asyncio.sleep(1)
        
        # Этап 2: Авторизация пользователей
        logger.info("\n🔐 Этап 2: Авторизация пользователей")
        logger.info("-" * 50)
        
        alice_logged = await alice.login()
        bob_logged = await bob.login()
        
        if not (alice_logged and bob_logged):
            logger.error("❌ Не удалось авторизовать всех пользователей")
            return
        
        await asyncio.sleep(1)
        
        # Этап 3: Добавление в друзья
        logger.info("\n👥 Этап 3: Добавление в друзья")
        logger.info("-" * 50)
        
        # Взаимное добавление в друзья
        await alice.add_friend(bob.user_id)
        await asyncio.sleep(1)
        await bob.add_friend(alice.user_id)
        await asyncio.sleep(2)
        
        # Этап 4: Подключение к WebSocket
        logger.info("\n🔌 Этап 4: Подключение к WebSocket")
        logger.info("-" * 50)
        
        alice_connected = await alice.connect_websocket()
        bob_connected = await bob.connect_websocket()
        
        if not (alice_connected and bob_connected):
            logger.error("❌ Не удалось подключить всех пользователей к WebSocket")
            return
        
        # Запускаем прослушивание сообщений в фоне
        alice_listener = asyncio.create_task(alice.listen_for_messages())
        bob_listener = asyncio.create_task(bob.listen_for_messages())
        
        await asyncio.sleep(2)
        
        # Этап 5: Создание постов и получение уведомлений
        logger.info("\n📝 Этап 5: Создание постов и получение уведомлений")
        logger.info("-" * 50)
        
        # Алиса создает пост
        post_text = "Привет всем! Это мой первый пост в социальной сети! 🎉"
        post_id = await alice.create_post(post_text)
        if post_id:
            await trigger_post_notification(post_id, alice.user_id, post_text)
        await asyncio.sleep(3)
        
        # Боб создает пост
        post_text = "Отличная погода сегодня! Идеальный день для прогулки ☀️"
        post_id = await bob.create_post(post_text)
        if post_id:
            await trigger_post_notification(post_id, bob.user_id, post_text)
        await asyncio.sleep(3)
        
        # Алиса создает еще один пост
        post_text = "Изучаю WebSocket технологии. Очень интересно! 💻"
        post_id = await alice.create_post(post_text)
        if post_id:
            await trigger_post_notification(post_id, alice.user_id, post_text)
        await asyncio.sleep(3)
        
        # Боб отвечает
        post_text = "WebSocket действительно круто! Реальное время - это будущее 🚀"
        post_id = await bob.create_post(post_text)
        if post_id:
            await trigger_post_notification(post_id, bob.user_id, post_text)
        await asyncio.sleep(3)
        
        # Этап 6: Статистика
        logger.info("\n📊 Этап 6: Статистика полученных уведомлений")
        logger.info("-" * 50)
        
        logger.info(f"📬 Алиса получила {len(alice.messages_received)} WebSocket сообщений")
        logger.info(f"📬 Боб получил {len(bob.messages_received)} WebSocket сообщений")
        
        # Показываем типы полученных сообщений
        feed_updates_alice = [msg for msg in alice.messages_received if msg.get('type') == 'feed_update']
        feed_updates_bob = [msg for msg in bob.messages_received if msg.get('type') == 'feed_update']
        
        logger.info(f"📢 Алиса получила {len(feed_updates_alice)} уведомлений о постах")
        logger.info(f"📢 Боб получил {len(feed_updates_bob)} уведомлений о постах")
        
        logger.info("\n🎉 Демонстрация завершена успешно!")
        logger.info("✅ Показано:")
        logger.info("   - Регистрация пользователей через API")
        logger.info("   - Авторизация и получение токенов")
        logger.info("   - Добавление в друзья")
        logger.info("   - Подключение к WebSocket")
        logger.info("   - Создание постов через API")
        logger.info("   - Получение уведомлений через WebSocket")
        
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
            
        await alice.disconnect_websocket()
        await bob.disconnect_websocket()
        
        logger.info("✅ Все пользователи отключены")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️  Демонстрация прервана пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}") 