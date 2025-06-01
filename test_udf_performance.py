#!/usr/bin/env python3
"""
Скрипт для тестирования производительности UDF функций Redis
"""

import asyncio
import time
import json
import aiohttp
from datetime import datetime
from typing import List, Dict


class UDFPerformanceTester:
    """Тестер производительности UDF функций"""
    
    def __init__(self, base_url: str = "http://localhost:9000"):
        self.base_url = base_url
        self.session = None
        self.auth_token = None
        
    async def __aenter__(self):
        """Асинхронный контекст менеджер - вход"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекст менеджер - выход"""
        if self.session:
            await self.session.close()
    
    async def login(self, user_id: str, password: str) -> bool:
        """Авторизация пользователя"""
        try:
            data = {
                "username": user_id,
                "password": password
            }
            
            async with self.session.post(
                f"{self.base_url}/login",
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.auth_token = result.get("access_token")
                    print(f"✅ Авторизация успешна для пользователя {user_id}")
                    return True
                else:
                    print(f"❌ Ошибка авторизации: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Ошибка авторизации: {e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков с токеном авторизации"""
        if not self.auth_token:
            raise Exception("Не выполнена авторизация")
        
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    async def send_message_standard(self, to_user_id: str, text: str) -> bool:
        """Отправка сообщения через стандартный endpoint"""
        try:
            data = {"text": text}
            
            async with self.session.post(
                f"{self.base_url}/dialog/{to_user_id}/send",
                headers=self._get_headers(),
                json=data
            ) as response:
                return response.status == 200
                
        except Exception as e:
            print(f"❌ Ошибка отправки стандартного сообщения: {e}")
            return False
    
    async def send_message_udf(self, to_user_id: str, text: str) -> bool:
        """Отправка сообщения через UDF endpoint"""
        try:
            data = {"text": text}
            
            async with self.session.post(
                f"{self.base_url}/dialog/{to_user_id}/send_udf",
                headers=self._get_headers(),
                json=data
            ) as response:
                return response.status == 200
                
        except Exception as e:
            print(f"❌ Ошибка отправки UDF сообщения: {e}")
            return False
    
    async def get_messages_standard(self, user_id: str, limit: int = 100) -> List:
        """Получение сообщений через стандартный endpoint"""
        try:
            async with self.session.get(
                f"{self.base_url}/dialog/{user_id}/list?limit={limit}",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    return await response.json()
                return []
                
        except Exception as e:
            print(f"❌ Ошибка получения стандартных сообщений: {e}")
            return []
    
    async def get_messages_udf(self, user_id: str, limit: int = 100) -> List:
        """Получение сообщений через UDF endpoint"""
        try:
            async with self.session.get(
                f"{self.base_url}/dialog/{user_id}/list_udf?limit={limit}",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    return await response.json()
                return []
                
        except Exception as e:
            print(f"❌ Ошибка получения UDF сообщений: {e}")
            return []
    
    async def get_stats_udf(self) -> Dict:
        """Получение статистики через UDF endpoint"""
        try:
            async with self.session.get(
                f"{self.base_url}/dialog/stats_udf",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {}
                
        except Exception as e:
            print(f"❌ Ошибка получения UDF статистики: {e}")
            return {}


async def measure_time(func, *args, **kwargs):
    """Измерение времени выполнения функции"""
    start_time = time.time()
    result = await func(*args, **kwargs)
    end_time = time.time()
    return result, (end_time - start_time) * 1000  # в миллисекундах


async def test_send_performance(tester: UDFPerformanceTester, 
                              user1_id: str, user2_id: str, 
                              message_count: int = 100):
    """Тестирование производительности отправки сообщений"""
    print(f"\n📨 Тестирование отправки {message_count} сообщений...")
    
    # Тест стандартного метода
    print("🔄 Тестирование стандартного метода...")
    standard_times = []
    
    for i in range(message_count):
        text = f"Стандартное сообщение #{i+1} от {user1_id}"
        _, duration = await measure_time(
            tester.send_message_standard, user2_id, text
        )
        standard_times.append(duration)
        
        if (i + 1) % 10 == 0:
            print(f"  Отправлено {i+1}/{message_count} стандартных сообщений")
    
    # Тест UDF метода
    print("🔄 Тестирование UDF метода...")
    udf_times = []
    
    for i in range(message_count):
        text = f"UDF сообщение #{i+1} от {user1_id}"
        _, duration = await measure_time(
            tester.send_message_udf, user2_id, text
        )
        udf_times.append(duration)
        
        if (i + 1) % 10 == 0:
            print(f"  Отправлено {i+1}/{message_count} UDF сообщений")
    
    # Анализ результатов
    standard_avg = sum(standard_times) / len(standard_times)
    udf_avg = sum(udf_times) / len(udf_times)
    
    print(f"\n📊 Результаты отправки сообщений:")
    print(f"  Стандартный метод: {standard_avg:.2f}ms (среднее)")
    print(f"  UDF метод: {udf_avg:.2f}ms (среднее)")
    
    improvement = ((standard_avg - udf_avg) / standard_avg) * 100
    if improvement > 0:
        print(f"  🚀 UDF быстрее на {improvement:.1f}%")
    else:
        print(f"  🐌 UDF медленнее на {abs(improvement):.1f}%")
    
    return {
        "standard_avg": standard_avg,
        "udf_avg": udf_avg,
        "improvement_percent": improvement
    }


async def test_read_performance(tester: UDFPerformanceTester, 
                              user1_id: str, user2_id: str, 
                              read_count: int = 50):
    """Тестирование производительности чтения сообщений"""
    print(f"\n📖 Тестирование чтения сообщений ({read_count} запросов)...")
    
    # Тест стандартного метода
    print("🔄 Тестирование стандартного метода...")
    standard_times = []
    
    for i in range(read_count):
        _, duration = await measure_time(
            tester.get_messages_standard, user2_id, 100
        )
        standard_times.append(duration)
        
        if (i + 1) % 10 == 0:
            print(f"  Выполнено {i+1}/{read_count} стандартных запросов")
    
    # Тест UDF метода
    print("🔄 Тестирование UDF метода...")
    udf_times = []
    
    for i in range(read_count):
        _, duration = await measure_time(
            tester.get_messages_udf, user2_id, 100
        )
        udf_times.append(duration)
        
        if (i + 1) % 10 == 0:
            print(f"  Выполнено {i+1}/{read_count} UDF запросов")
    
    # Анализ результатов
    standard_avg = sum(standard_times) / len(standard_times)
    udf_avg = sum(udf_times) / len(udf_times)
    
    print(f"\n📊 Результаты чтения сообщений:")
    print(f"  Стандартный метод: {standard_avg:.2f}ms (среднее)")
    print(f"  UDF метод: {udf_avg:.2f}ms (среднее)")
    
    improvement = ((standard_avg - udf_avg) / standard_avg) * 100
    if improvement > 0:
        print(f"  🚀 UDF быстрее на {improvement:.1f}%")
    else:
        print(f"  🐌 UDF медленнее на {abs(improvement):.1f}%")
    
    return {
        "standard_avg": standard_avg,
        "udf_avg": udf_avg,
        "improvement_percent": improvement
    }


async def test_stats_performance(tester: UDFPerformanceTester, 
                               stats_count: int = 20):
    """Тестирование производительности получения статистики"""
    print(f"\n📊 Тестирование получения статистики ({stats_count} запросов)...")
    
    udf_times = []
    
    for i in range(stats_count):
        _, duration = await measure_time(tester.get_stats_udf)
        udf_times.append(duration)
        
        if (i + 1) % 5 == 0:
            print(f"  Выполнено {i+1}/{stats_count} запросов статистики")
    
    # Анализ результатов
    udf_avg = sum(udf_times) / len(udf_times)
    
    print(f"\n📊 Результаты получения статистики:")
    print(f"  UDF метод: {udf_avg:.2f}ms (среднее)")
    
    return {"udf_avg": udf_avg}


async def main():
    """Основная функция тестирования"""
    print("🧪 Запуск тестирования производительности UDF функций Redis")
    print("=" * 60)
    
    # Параметры тестирования
    user1_id = "test_user_1"
    user2_id = "test_user_2"
    password = "password123"
    
    async with UDFPerformanceTester() as tester:
        # Авторизация
        print("🔐 Авторизация...")
        if not await tester.login(user1_id, password):
            print("❌ Не удалось авторизоваться")
            return
        
        # Тестирование отправки сообщений
        send_results = await test_send_performance(
            tester, user1_id, user2_id, message_count=50
        )
        
        # Тестирование чтения сообщений
        read_results = await test_read_performance(
            tester, user1_id, user2_id, read_count=30
        )
        
        # Тестирование статистики
        stats_results = await test_stats_performance(tester, stats_count=10)
        
        # Итоговый отчет
        print("\n" + "=" * 60)
        print("📋 ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 60)
        
        print(f"📨 Отправка сообщений:")
        print(f"  Стандартный: {send_results['standard_avg']:.2f}ms")
        print(f"  UDF: {send_results['udf_avg']:.2f}ms")
        print(f"  Улучшение: {send_results['improvement_percent']:.1f}%")
        
        print(f"\n📖 Чтение сообщений:")
        print(f"  Стандартный: {read_results['standard_avg']:.2f}ms")
        print(f"  UDF: {read_results['udf_avg']:.2f}ms")
        print(f"  Улучшение: {read_results['improvement_percent']:.1f}%")
        
        print(f"\n📊 Статистика:")
        print(f"  UDF: {stats_results['udf_avg']:.2f}ms")
        
        # Общая оценка
        total_improvement = (send_results['improvement_percent'] + 
                           read_results['improvement_percent']) / 2
        
        print(f"\n🎯 ОБЩАЯ ОЦЕНКА:")
        if total_improvement > 0:
            print(f"  🚀 UDF функции показывают улучшение на {total_improvement:.1f}%")
        else:
            print(f"  🐌 UDF функции показывают снижение на {abs(total_improvement):.1f}%")
        
        print("\n✅ Тестирование завершено")


if __name__ == "__main__":
    asyncio.run(main()) 