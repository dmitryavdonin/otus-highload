#!/usr/bin/env python3
"""
Скрипт для проверки корректности сохранения сообщений в PostgreSQL и Redis
"""

import asyncio
import aiohttp
import json
import os
from typing import Dict, List, Any

API_URL = "http://localhost:9000"

class MessageVerifier:
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_service_health(self) -> bool:
        """Проверка доступности сервиса"""
        try:
            async with self.session.get(f"{self.api_url}/docs") as response:
                return response.status == 200
        except Exception as e:
            print(f"❌ Сервис недоступен: {e}")
            return False
    
    async def get_test_users(self) -> List[Dict[str, Any]]:
        """Получение списка тестовых пользователей"""
        test_users = []
        
        # Пытаемся найти пользователей с именами User{i} и паролями password{i}
        for i in range(50):  # Проверяем до 50 пользователей
            try:
                # Пытаемся войти как тестовый пользователь
                login_data = {
                    "id": f"User{i}",  # Изменено с test_user_{i} на User{i}
                    "password": f"password{i}"  # Изменено с test_password на password{i}
                }
                
                async with self.session.post(f"{self.api_url}/login", json=login_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        test_users.append({
                            "id": f"User{i}",
                            "token": result["token"],
                            "name": f"User{i} Test{i}"
                        })
                        
                        # Если нашли достаточно пользователей, прекращаем поиск
                        if len(test_users) >= 40:  # Ограничиваем количество для производительности
                            break
            except Exception:
                continue
                
        return test_users
    
    async def get_user_dialogs(self, token: str, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка диалогов пользователя"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with self.session.get(f"{self.api_url}/dialog/{user_id}/list", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ Ошибка получения диалогов: {response.status}")
                    return []
        except Exception as e:
            print(f"❌ Ошибка при получении диалогов: {e}")
            return []
    
    async def get_dialog_messages(self, token: str, friend_id: str) -> List[Dict[str, Any]]:
        """Получение сообщений диалога"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with self.session.get(f"{self.api_url}/dialog/{friend_id}/list", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ Ошибка получения сообщений: {response.status}")
                    return []
        except Exception as e:
            print(f"❌ Ошибка при получении сообщений: {e}")
            return []
    
    async def verify_backend_messages(self, backend_name: str) -> Dict[str, Any]:
        """Проверка сообщений для конкретного бэкенда"""
        print(f"\n🔍 Проверка сообщений в {backend_name}...")
        
        # Получаем тестовых пользователей
        users = await self.get_test_users()
        if not users:
            return {
                "backend": backend_name,
                "status": "error",
                "message": "Не найдено тестовых пользователей",
                "users_count": 0,
                "dialogs_count": 0,
                "messages_count": 0
            }
        
        print(f"✅ Найдено {len(users)} тестовых пользователей")
        
        total_dialogs = 0
        total_messages = 0
        user_stats = []
        
        for user in users:
            user_id = user["id"]
            token = user["token"]
            
            # Получаем диалоги пользователя
            dialogs = await self.get_user_dialogs(token, user_id)
            user_dialogs_count = len(dialogs) if dialogs else 0
            
            user_messages_count = 0
            dialog_details = []
            
            # Для каждого диалога получаем сообщения
            for other_user in users:
                if other_user["id"] != user_id:
                    messages = await self.get_dialog_messages(token, other_user["id"])
                    if messages:
                        dialog_details.append({
                            "friend_id": other_user["id"],
                            "messages_count": len(messages)
                        })
                        user_messages_count += len(messages)
            
            user_stats.append({
                "user_id": user_id,
                "dialogs_count": user_dialogs_count,
                "messages_count": user_messages_count,
                "dialog_details": dialog_details
            })
            
            total_dialogs += user_dialogs_count
            total_messages += user_messages_count
        
        return {
            "backend": backend_name,
            "status": "success",
            "users_count": len(users),
            "total_dialogs": total_dialogs,
            "total_messages": total_messages,
            "user_stats": user_stats
        }
    
    async def run_verification(self) -> None:
        """Запуск полной проверки"""
        print("🚀 Запуск проверки корректности сохранения сообщений")
        print("=" * 60)
        
        # Проверяем доступность сервиса
        if not await self.check_service_health():
            print("❌ Сервис недоступен")
            return
        
        print("✅ Сервис доступен")
        
        results = {}
        
        # Проверяем PostgreSQL
        print("\n📊 Проверка PostgreSQL...")
        os.environ["DIALOG_BACKEND"] = "postgresql"
        results["postgresql"] = await self.verify_backend_messages("PostgreSQL")
        
        # Проверяем Redis
        print("\n📊 Проверка Redis...")
        os.environ["DIALOG_BACKEND"] = "redis"
        results["redis"] = await self.verify_backend_messages("Redis")
        
        # Выводим сравнительный отчет
        self.print_comparison_report(results)
        
        # Сохраняем результаты
        await self.save_verification_results(results)
    
    def print_comparison_report(self, results: Dict[str, Any]) -> None:
        """Вывод сравнительного отчета"""
        print("\n" + "=" * 60)
        print("📋 СРАВНИТЕЛЬНЫЙ ОТЧЕТ")
        print("=" * 60)
        
        for backend_key, result in results.items():
            backend_name = result.get("backend", backend_key)
            status = result.get("status", "unknown")
            
            print(f"\n🔹 {backend_name}:")
            if status == "success":
                print(f"   ✅ Статус: Успешно")
                print(f"   👥 Пользователей: {result.get('users_count', 0)}")
                print(f"   💬 Диалогов: {result.get('total_dialogs', 0)}")
                print(f"   📝 Сообщений: {result.get('total_messages', 0)}")
                
                # Детали по пользователям
                for user_stat in result.get('user_stats', []):
                    print(f"      • {user_stat['user_id']}: {user_stat['messages_count']} сообщений в {user_stat['dialogs_count']} диалогах")
            else:
                print(f"   ❌ Статус: Ошибка")
                print(f"   📄 Сообщение: {result.get('message', 'Неизвестная ошибка')}")
        
        # Сравнение результатов
        if "postgresql" in results and "redis" in results:
            pg_result = results["postgresql"]
            redis_result = results["redis"]
            
            if pg_result.get("status") == "success" and redis_result.get("status") == "success":
                print(f"\n🔍 СРАВНЕНИЕ:")
                print(f"   📊 Пользователи: PostgreSQL={pg_result.get('users_count', 0)}, Redis={redis_result.get('users_count', 0)}")
                print(f"   📊 Диалоги: PostgreSQL={pg_result.get('total_dialogs', 0)}, Redis={redis_result.get('total_dialogs', 0)}")
                print(f"   📊 Сообщения: PostgreSQL={pg_result.get('total_messages', 0)}, Redis={redis_result.get('total_messages', 0)}")
                
                # Проверка консистентности
                if (pg_result.get('total_messages', 0) == redis_result.get('total_messages', 0) and
                    pg_result.get('users_count', 0) == redis_result.get('users_count', 0)):
                    print(f"   ✅ Данные консистентны между системами")
                else:
                    print(f"   ⚠️  Обнаружены различия в данных между системами")
    
    async def save_verification_results(self, results: Dict[str, Any]) -> None:
        """Сохранение результатов проверки"""
        os.makedirs("lesson-07", exist_ok=True)
        
        with open("lesson-07/message_verification.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты проверки сохранены в: lesson-07/message_verification.json")

async def main():
    """Главная функция"""
    async with MessageVerifier() as verifier:
        await verifier.run_verification()

if __name__ == "__main__":
    asyncio.run(main()) 