#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
import time
from datetime import datetime, timedelta

# Конфигурация
API_URL = "http://localhost:9000"

class SingleMessageSender:
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.session = None
    
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
    
    async def register_user(self, first_name: str, second_name: str, password: str) -> str:
        """Регистрация пользователя"""
        data = {
            "first_name": first_name,
            "second_name": second_name,
            "birthdate": (datetime.now() - timedelta(days=365 * 25)).strftime("%Y-%m-%dT%H:%M:%S"),
            "biography": f"Тестовый пользователь {first_name} {second_name}",
            "city": "Москва",
            "password": password
        }
        
        try:
            async with self.session.post(f"{self.api_url}/user/register", json=data) as response:
                if response.status == 200:
                    user_data = await response.json()
                    return user_data['id']
                else:
                    error_text = await response.text()
                    raise Exception(f"Registration failed: {response.status} - {error_text}")
        except Exception as e:
            raise Exception(f"Registration error: {e}")
    
    async def login_user(self, user_id: str, password: str) -> str:
        """Авторизация пользователя"""
        data = {
            "id": user_id,
            "password": password
        }
        
        try:
            async with self.session.post(f"{self.api_url}/user/login", json=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    return token_data['token']
                else:
                    error_text = await response.text()
                    raise Exception(f"Login failed: {response.status} - {error_text}")
        except Exception as e:
            raise Exception(f"Login error: {e}")
    
    async def send_message(self, token: str, recipient_id: str, text: str) -> bool:
        """Отправка сообщения"""
        headers = {"Authorization": f"Bearer {token}"}
        data = {"text": text}
        
        try:
            async with self.session.post(f"{self.api_url}/dialog/{recipient_id}/send", 
                                       headers=headers, json=data) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    raise Exception(f"Send message failed: {response.status} - {error_text}")
        except Exception as e:
            raise Exception(f"Send message error: {e}")
    
    async def get_messages(self, token: str, interlocutor_id: str) -> list:
        """Получение сообщений диалога"""
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            async with self.session.get(f"{self.api_url}/dialog/{interlocutor_id}/list", 
                                      headers=headers) as response:
                if response.status == 200:
                    messages = await response.json()
                    return messages
                else:
                    error_text = await response.text()
                    raise Exception(f"Get messages failed: {response.status} - {error_text}")
        except Exception as e:
            raise Exception(f"Get messages error: {e}")

async def main():
    """Основная функция для отправки одного сообщения"""
    print("🚀 Тест отправки одного сообщения")
    print("=" * 50)
    
    async with SingleMessageSender() as sender:
        # Проверяем доступность сервиса
        print("🔍 Проверка доступности сервиса...")
        if not await sender.check_service_availability():
            print("❌ Сервис недоступен")
            return
        print("✅ Сервис доступен")
        
        try:
            # Создаем двух пользователей
            print("\n👤 Создание пользователей...")
            
            print("Регистрация отправителя...")
            sender_id = await sender.register_user("Alice", "Sender", "password123")
            print(f"✅ Отправитель зарегистрирован: {sender_id}")
            
            print("Регистрация получателя...")
            recipient_id = await sender.register_user("Bob", "Recipient", "password456")
            print(f"✅ Получатель зарегистрирован: {recipient_id}")
            
            # Авторизуемся как отправитель
            print("\n🔐 Авторизация отправителя...")
            token = await sender.login_user(sender_id, "password123")
            print("✅ Авторизация успешна")
            
            # Отправляем сообщение
            print("\n📤 Отправка сообщения...")
            message_text = "Привет! Это тестовое сообщение из Redis."
            success = await sender.send_message(token, recipient_id, message_text)
            
            if success:
                print("✅ Сообщение отправлено успешно!")
                
                # Проверяем, что сообщение сохранилось
                print("\n📥 Проверка сохранения сообщения...")
                messages = await sender.get_messages(token, recipient_id)
                
                if messages and len(messages) > 0:
                    print(f"✅ Найдено {len(messages)} сообщений в диалоге")
                    print(f"📝 Последнее сообщение: {messages[-1].get('text', 'N/A')}")
                else:
                    print("⚠️  Сообщения не найдены")
            else:
                print("❌ Ошибка отправки сообщения")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    print("\n🎉 Тест завершен!")

if __name__ == "__main__":
    asyncio.run(main()) 