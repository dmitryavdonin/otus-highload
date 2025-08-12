#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# Конфигурация
API_URL = "http://localhost:9000"

class SimpleDialogTester:
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.session = None
        self.users = []  # List of (user_id, token, name)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_service_availability(self) -> bool:
        """Проверка доступности сервиса"""
        try:
            async with self.session.get(f"{self.api_url}/docs", timeout=5) as response:
                return response.status == 200
        except Exception as e:
            print(f"❌ Сервис недоступен: {e}")
            return False
    
    async def register_user(self, first_name: str, second_name: str, password: str) -> Tuple[str, float]:
        """Регистрация пользователя с измерением времени"""
        data = {
            "first_name": first_name,
            "second_name": second_name,
            "birthdate": (datetime.now() - timedelta(days=365 * 25)).strftime("%Y-%m-%dT%H:%M:%S"),
            "biography": f"Тестовый пользователь {first_name} {second_name}",
            "city": "Москва",
            "password": password
        }
        
        start_time = time.time()
        try:
            async with self.session.post(f"{self.api_url}/user/register", json=data) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    user_data = await response.json()
                    return user_data['id'], duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Registration failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Registration error after {duration:.3f}s: {e}")
    
    async def login_user(self, user_id: str, password: str) -> Tuple[str, float]:
        """Авторизация пользователя с измерением времени"""
        data = {
            "id": user_id,
            "password": password
        }
        
        start_time = time.time()
        try:
            async with self.session.post(f"{self.api_url}/user/login", json=data) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    token_data = await response.json()
                    return token_data['token'], duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Login failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Login error after {duration:.3f}s: {e}")
    
    async def add_friend(self, token: str, friend_id: str) -> float:
        """Добавление друга с измерением времени"""
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = time.time()
        try:
            async with self.session.put(f"{self.api_url}/friend/set/{friend_id}", headers=headers) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    return duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Add friend failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Add friend error after {duration:.3f}s: {e}")
    
    async def send_message(self, token: str, recipient_id: str, text: str) -> float:
        """Отправка сообщения с измерением времени"""
        headers = {"Authorization": f"Bearer {token}"}
        data = {"text": text}
        
        start_time = time.time()
        try:
            async with self.session.post(f"{self.api_url}/dialog/{recipient_id}/send", 
                                       headers=headers, json=data) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    return duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Send message failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Send message error after {duration:.3f}s: {e}")
    
    async def get_messages(self, token: str, interlocutor_id: str) -> Tuple[List[Dict], float]:
        """Получение сообщений диалога с измерением времени"""
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = time.time()
        try:
            async with self.session.get(f"{self.api_url}/dialog/{interlocutor_id}/list", 
                                      headers=headers) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    messages = await response.json()
                    return messages, duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Get messages failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Get messages error after {duration:.3f}s: {e}")
    
    async def register_and_login_user(self, first_name: str, second_name: str, password: str) -> Tuple[str, str, float, float]:
        """Регистрация и авторизация пользователя"""
        user_id, reg_time = await self.register_user(first_name, second_name, password)
        token, login_time = await self.login_user(user_id, password)
        return user_id, token, reg_time, login_time

async def main():
    """Основная функция для простого теста диалогов"""
    print("🚀 ПРОСТОЙ ТЕСТ ДИАЛОГОВ")
    print("=" * 50)
    print("📊 Конфигурация:")
    print("   - Пользователей: 2")
    print("   - Сообщений: 1")
    print("   - Бэкенд: Redis")
    print()
    
    async with SimpleDialogTester() as tester:
        # Проверка доступности сервиса
        print("🔍 Проверка доступности сервиса...")
        if not await tester.check_service_availability():
            print("❌ Сервис недоступен")
            return
        print("✅ Сервис доступен")
        
        try:
            # Этап 1: Создание пользователей
            print("\n👤 Создание пользователей...")
            
            print("Регистрация и авторизация пользователя Alice...")
            alice_id, alice_token, alice_reg_time, alice_login_time = await tester.register_and_login_user(
                "Alice", "Sender", "password123"
            )
            print(f"✅ Alice зарегистрирована: {alice_id}")
            print(f"   Время регистрации: {alice_reg_time:.3f}s")
            print(f"   Время авторизации: {alice_login_time:.3f}s")
            
            print("Регистрация и авторизация пользователя Bob...")
            bob_id, bob_token, bob_reg_time, bob_login_time = await tester.register_and_login_user(
                "Bob", "Recipient", "password456"
            )
            print(f"✅ Bob зарегистрирован: {bob_id}")
            print(f"   Время регистрации: {bob_reg_time:.3f}s")
            print(f"   Время авторизации: {bob_login_time:.3f}s")
            
            # Этап 2: Добавление в друзья
            print("\n🤝 Добавление в друзья...")
            
            print("Alice добавляет Bob в друзья...")
            friend_time1 = await tester.add_friend(alice_token, bob_id)
            print(f"✅ Alice добавила Bob в друзья за {friend_time1:.3f}s")
            
            print("Bob добавляет Alice в друзья...")
            friend_time2 = await tester.add_friend(bob_token, alice_id)
            print(f"✅ Bob добавил Alice в друзья за {friend_time2:.3f}s")
            
            # Этап 3: Отправка сообщения
            print("\n📤 Отправка сообщения...")
            
            message_text = "Привет, Bob! Это тестовое сообщение из Redis."
            send_time = await tester.send_message(alice_token, bob_id, message_text)
            print(f"✅ Alice отправила сообщение Bob за {send_time:.3f}s")
            print(f"   Текст: {message_text}")
            
            # Этап 4: Чтение сообщений
            print("\n📥 Чтение сообщений...")
            
            print("Alice читает диалог с Bob...")
            alice_messages, alice_read_time = await tester.get_messages(alice_token, bob_id)
            print(f"✅ Alice прочитала диалог за {alice_read_time:.3f}s")
            print(f"   Найдено сообщений: {len(alice_messages)}")
            
            print("Bob читает диалог с Alice...")
            bob_messages, bob_read_time = await tester.get_messages(bob_token, alice_id)
            print(f"✅ Bob прочитал диалог за {bob_read_time:.3f}s")
            print(f"   Найдено сообщений: {len(bob_messages)}")
            
            # Проверка содержимого сообщений
            if alice_messages and len(alice_messages) > 0:
                last_message = alice_messages[-1]
                print(f"📝 Последнее сообщение в диалоге Alice:")
                print(f"   От: {last_message.get('from_user_id', 'N/A')}")
                print(f"   Кому: {last_message.get('to_user_id', 'N/A')}")
                print(f"   Текст: {last_message.get('text', 'N/A')}")
                print(f"   Время: {last_message.get('created_at', 'N/A')}")
            
            if bob_messages and len(bob_messages) > 0:
                last_message = bob_messages[-1]
                print(f"📝 Последнее сообщение в диалоге Bob:")
                print(f"   От: {last_message.get('from_user_id', 'N/A')}")
                print(f"   Кому: {last_message.get('to_user_id', 'N/A')}")
                print(f"   Текст: {last_message.get('text', 'N/A')}")
                print(f"   Время: {last_message.get('created_at', 'N/A')}")
            
            # Итоговая статистика
            print("\n📊 ИТОГОВАЯ СТАТИСТИКА:")
            print("=" * 50)
            print(f"Регистрация пользователей:")
            print(f"  Alice: {alice_reg_time:.3f}s")
            print(f"  Bob: {bob_reg_time:.3f}s")
            print(f"  Среднее: {(alice_reg_time + bob_reg_time) / 2:.3f}s")
            
            print(f"Авторизация пользователей:")
            print(f"  Alice: {alice_login_time:.3f}s")
            print(f"  Bob: {bob_login_time:.3f}s")
            print(f"  Среднее: {(alice_login_time + bob_login_time) / 2:.3f}s")
            
            print(f"Добавление в друзья:")
            print(f"  Alice -> Bob: {friend_time1:.3f}s")
            print(f"  Bob -> Alice: {friend_time2:.3f}s")
            print(f"  Среднее: {(friend_time1 + friend_time2) / 2:.3f}s")
            
            print(f"Отправка сообщения:")
            print(f"  Alice -> Bob: {send_time:.3f}s")
            
            print(f"Чтение сообщений:")
            print(f"  Alice: {alice_read_time:.3f}s")
            print(f"  Bob: {bob_read_time:.3f}s")
            print(f"  Среднее: {(alice_read_time + bob_read_time) / 2:.3f}s")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    print("\n🎉 Тест завершен!")

if __name__ == "__main__":
    asyncio.run(main()) 