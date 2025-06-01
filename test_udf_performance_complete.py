#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
import time
import json
import random
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import argparse
import sys
import os

# Конфигурация
API_URL = "http://localhost:9000"
TEST_USERS_COUNT = 50
MESSAGES_PER_DIALOG = 20
DIALOGS_PER_USER = 5

class UDFPerformanceTester:
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.session = None
        self.users = []  # List of (user_id, token, name)
        self.metrics = {
            'user_registration': [],
            'user_login': [],
            'friend_addition': [],
            'message_send_regular': [],
            'message_send_udf': [],
            'message_list_regular': [],
            'message_list_udf': [],
            'message_recent_udf': [],
            'dialog_stats_udf': [],
        }
    
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
    
    async def send_message_regular(self, token: str, recipient_id: str, text: str) -> float:
        """Отправка сообщения обычным способом с измерением времени"""
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
    
    async def send_message_udf(self, token: str, recipient_id: str, text: str) -> float:
        """Отправка сообщения через UDF с измерением времени"""
        headers = {"Authorization": f"Bearer {token}"}
        data = {"text": text}
        
        start_time = time.time()
        try:
            async with self.session.post(f"{self.api_url}/dialog/{recipient_id}/send_udf", 
                                       headers=headers, json=data) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    return duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Send message UDF failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Send message UDF error after {duration:.3f}s: {e}")
    
    async def get_messages_regular(self, token: str, interlocutor_id: str) -> Tuple[List[Dict], float]:
        """Получение сообщений диалога обычным способом с измерением времени"""
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
    
    async def get_messages_udf(self, token: str, interlocutor_id: str) -> Tuple[List[Dict], float]:
        """Получение сообщений диалога через UDF с измерением времени"""
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = time.time()
        try:
            async with self.session.get(f"{self.api_url}/dialog/{interlocutor_id}/list_udf", 
                                      headers=headers) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    messages = await response.json()
                    return messages, duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Get messages UDF failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Get messages UDF error after {duration:.3f}s: {e}")
    
    async def get_recent_messages_udf(self, token: str, interlocutor_id: str) -> Tuple[List[Dict], float]:
        """Получение последних сообщений через UDF с измерением времени"""
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = time.time()
        try:
            async with self.session.get(f"{self.api_url}/dialog/{interlocutor_id}/recent_udf", 
                                      headers=headers) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    messages = await response.json()
                    return messages, duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Get recent messages UDF failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Get recent messages UDF error after {duration:.3f}s: {e}")
    
    async def get_dialog_stats_udf(self, token: str) -> Tuple[Dict, float]:
        """Получение статистики диалогов через UDF с измерением времени"""
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = time.time()
        try:
            async with self.session.get(f"{self.api_url}/dialog/stats_udf", 
                                      headers=headers) as response:
                duration = time.time() - start_time
                if response.status == 200:
                    stats = await response.json()
                    return stats, duration
                else:
                    error_text = await response.text()
                    raise Exception(f"Get dialog stats UDF failed: {response.status} - {error_text}")
        except Exception as e:
            duration = time.time() - start_time
            raise Exception(f"Get dialog stats UDF error after {duration:.3f}s: {e}")
    
    async def setup_test_users(self, count: int) -> None:
        """Создание тестовых пользователей"""
        print(f"🔄 Создание {count} тестовых пользователей...")
        
        tasks = []
        for i in range(count):
            first_name = f"UDFUser{i}"
            second_name = f"Test{i}"
            password = f"password{i}"
            tasks.append(self.register_and_login_user(first_name, second_name, password))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_users = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Ошибка создания пользователя {i}: {result}")
            else:
                user_id, token, reg_time, login_time = result
                successful_users.append((user_id, token, f"UDFUser{i} Test{i}"))
                self.metrics['user_registration'].append(reg_time)
                self.metrics['user_login'].append(login_time)
        
        self.users = successful_users
        print(f"✅ Успешно создано {len(self.users)} пользователей")
    
    async def register_and_login_user(self, first_name: str, second_name: str, password: str) -> Tuple[str, str, float, float]:
        """Регистрация и авторизация пользователя"""
        user_id, reg_time = await self.register_user(first_name, second_name, password)
        token, login_time = await self.login_user(user_id, password)
        return user_id, token, reg_time, login_time
    
    async def setup_friendships(self) -> None:
        """Установка дружеских связей между пользователями"""
        print(f"🔄 Установка дружеских связей...")
        
        tasks = []
        for i, (user_id, token, name) in enumerate(self.users):
            # Каждый пользователь добавляет в друзья следующих DIALOGS_PER_USER пользователей
            for j in range(1, min(DIALOGS_PER_USER + 1, len(self.users))):
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    tasks.append(self.add_friend(token, friend_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_friendships = 0
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка добавления друга: {result}")
            else:
                self.metrics['friend_addition'].append(result)
                successful_friendships += 1
        
        print(f"✅ Успешно установлено {successful_friendships} дружеских связей")
    
    async def run_comparison_tests(self) -> None:
        """Запуск сравнительных тестов обычных методов и UDF"""
        print(f"🔄 Тестирование производительности: обычные методы vs UDF...")
        
        # Тест 1: Отправка сообщений (обычный способ)
        print("📤 Отправка сообщений обычным способом...")
        send_regular_tasks = []
        for i, (user_id, token, name) in enumerate(self.users[:10]):  # Ограничиваем для теста
            for j in range(1, min(3, len(self.users))):  # Меньше диалогов для теста
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    for msg_num in range(5):  # Меньше сообщений для теста
                        message_text = f"Обычное сообщение {msg_num + 1} от {name}"
                        send_regular_tasks.append(self.send_message_regular(token, friend_id, message_text))
        
        send_regular_results = await asyncio.gather(*send_regular_tasks, return_exceptions=True)
        
        successful_regular_sends = 0
        for result in send_regular_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка отправки обычного сообщения: {result}")
            else:
                self.metrics['message_send_regular'].append(result)
                successful_regular_sends += 1
        
        print(f"✅ Успешно отправлено {successful_regular_sends} обычных сообщений")
        
        # Тест 2: Отправка сообщений через UDF
        print("📤 Отправка сообщений через UDF...")
        send_udf_tasks = []
        for i, (user_id, token, name) in enumerate(self.users[:10]):
            for j in range(1, min(3, len(self.users))):
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    for msg_num in range(5):
                        message_text = f"UDF сообщение {msg_num + 1} от {name}"
                        send_udf_tasks.append(self.send_message_udf(token, friend_id, message_text))
        
        send_udf_results = await asyncio.gather(*send_udf_tasks, return_exceptions=True)
        
        successful_udf_sends = 0
        for result in send_udf_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка отправки UDF сообщения: {result}")
            else:
                self.metrics['message_send_udf'].append(result)
                successful_udf_sends += 1
        
        print(f"✅ Успешно отправлено {successful_udf_sends} UDF сообщений")
        
        # Тест 3: Чтение сообщений (обычный способ)
        print("📥 Чтение сообщений обычным способом...")
        read_regular_tasks = []
        for i, (user_id, token, name) in enumerate(self.users[:10]):
            for j in range(1, min(3, len(self.users))):
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    read_regular_tasks.append(self.get_messages_regular(token, friend_id))
        
        read_regular_results = await asyncio.gather(*read_regular_tasks, return_exceptions=True)
        
        successful_regular_reads = 0
        total_regular_messages = 0
        for result in read_regular_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка чтения обычных сообщений: {result}")
            else:
                messages, duration = result
                self.metrics['message_list_regular'].append(duration)
                successful_regular_reads += 1
                total_regular_messages += len(messages)
        
        print(f"✅ Успешно прочитано {successful_regular_reads} обычных диалогов ({total_regular_messages} сообщений)")
        
        # Тест 4: Чтение сообщений через UDF
        print("📥 Чтение сообщений через UDF...")
        read_udf_tasks = []
        for i, (user_id, token, name) in enumerate(self.users[:10]):
            for j in range(1, min(3, len(self.users))):
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    read_udf_tasks.append(self.get_messages_udf(token, friend_id))
        
        read_udf_results = await asyncio.gather(*read_udf_tasks, return_exceptions=True)
        
        successful_udf_reads = 0
        total_udf_messages = 0
        for result in read_udf_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка чтения UDF сообщений: {result}")
            else:
                messages, duration = result
                self.metrics['message_list_udf'].append(duration)
                successful_udf_reads += 1
                total_udf_messages += len(messages)
        
        print(f"✅ Успешно прочитано {successful_udf_reads} UDF диалогов ({total_udf_messages} сообщений)")
        
        # Тест 5: Получение последних сообщений через UDF
        print("📥 Получение последних сообщений через UDF...")
        recent_udf_tasks = []
        for i, (user_id, token, name) in enumerate(self.users[:10]):
            for j in range(1, min(3, len(self.users))):
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    recent_udf_tasks.append(self.get_recent_messages_udf(token, friend_id))
        
        recent_udf_results = await asyncio.gather(*recent_udf_tasks, return_exceptions=True)
        
        successful_recent_reads = 0
        for result in recent_udf_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка получения последних UDF сообщений: {result}")
            else:
                messages, duration = result
                self.metrics['message_recent_udf'].append(duration)
                successful_recent_reads += 1
        
        print(f"✅ Успешно получено {successful_recent_reads} списков последних сообщений")
        
        # Тест 6: Статистика диалогов через UDF
        print("📊 Получение статистики диалогов через UDF...")
        stats_tasks = []
        for user_id, token, name in self.users[:5]:  # Только несколько пользователей
            stats_tasks.append(self.get_dialog_stats_udf(token))
        
        stats_results = await asyncio.gather(*stats_tasks, return_exceptions=True)
        
        successful_stats = 0
        for result in stats_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка получения статистики UDF: {result}")
            else:
                stats, duration = result
                self.metrics['dialog_stats_udf'].append(duration)
                successful_stats += 1
        
        print(f"✅ Успешно получено {successful_stats} статистик диалогов")
    
    def print_comparison_metrics(self) -> None:
        """Вывод сравнительных метрик производительности"""
        print("\n" + "="*80)
        print("📊 СРАВНИТЕЛЬНЫЕ МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ: ОБЫЧНЫЕ МЕТОДЫ vs UDF")
        print("="*80)
        
        # Сравнение отправки сообщений
        if self.metrics['message_send_regular'] and self.metrics['message_send_udf']:
            regular_avg = statistics.mean(self.metrics['message_send_regular'])
            udf_avg = statistics.mean(self.metrics['message_send_udf'])
            improvement = ((regular_avg - udf_avg) / regular_avg) * 100
            
            print(f"\n📤 ОТПРАВКА СООБЩЕНИЙ:")
            print(f"  Обычный способ: {regular_avg:.3f}s ({1/regular_avg:.1f} ops/s)")
            print(f"  UDF способ:     {udf_avg:.3f}s ({1/udf_avg:.1f} ops/s)")
            print(f"  Улучшение:      {improvement:+.1f}%")
        
        # Сравнение чтения сообщений
        if self.metrics['message_list_regular'] and self.metrics['message_list_udf']:
            regular_avg = statistics.mean(self.metrics['message_list_regular'])
            udf_avg = statistics.mean(self.metrics['message_list_udf'])
            improvement = ((regular_avg - udf_avg) / regular_avg) * 100
            
            print(f"\n📥 ЧТЕНИЕ СООБЩЕНИЙ:")
            print(f"  Обычный способ: {regular_avg:.3f}s ({1/regular_avg:.1f} ops/s)")
            print(f"  UDF способ:     {udf_avg:.3f}s ({1/udf_avg:.1f} ops/s)")
            print(f"  Улучшение:      {improvement:+.1f}%")
        
        # Дополнительные UDF метрики
        for operation, times in self.metrics.items():
            if times and 'udf' in operation and operation not in ['message_send_udf', 'message_list_udf']:
                avg_time = statistics.mean(times)
                median_time = statistics.median(times)
                min_time = min(times)
                max_time = max(times)
                p95_time = sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0]
                
                print(f"\n{operation.replace('_', ' ').title()}:")
                print(f"  Количество операций: {len(times)}")
                print(f"  Среднее время: {avg_time:.3f}s")
                print(f"  Медиана: {median_time:.3f}s")
                print(f"  Минимум: {min_time:.3f}s")
                print(f"  Максимум: {max_time:.3f}s")
                print(f"  95-й перцентиль: {p95_time:.3f}s")
                print(f"  Операций в секунду: {1/avg_time:.1f}")
        
        print("\n" + "="*80)
    
    def save_metrics_to_file(self, filename: str = None) -> None:
        """Сохранение метрик в JSON файл"""
        if filename is None:
            filename = f"lesson-07/udf_comparison_metrics.json"
        
        # Обрабатываем метрики и вычисляем статистику
        metrics_summary = {}
        for operation, times in self.metrics.items():
            if times:
                metrics_summary[operation] = {
                    'count': len(times),
                    'avg': statistics.mean(times),
                    'median': statistics.median(times),
                    'min': min(times),
                    'max': max(times),
                    'p95': sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
                    'ops_per_second': 1/statistics.mean(times),
                    'raw_times': times
                }
        
        # Вычисляем сравнительные метрики
        comparisons = {}
        if metrics_summary.get('message_send_regular') and metrics_summary.get('message_send_udf'):
            regular_avg = metrics_summary['message_send_regular']['avg']
            udf_avg = metrics_summary['message_send_udf']['avg']
            comparisons['message_send_improvement'] = ((regular_avg - udf_avg) / regular_avg) * 100
        
        if metrics_summary.get('message_list_regular') and metrics_summary.get('message_list_udf'):
            regular_avg = metrics_summary['message_list_regular']['avg']
            udf_avg = metrics_summary['message_list_udf']['avg']
            comparisons['message_list_improvement'] = ((regular_avg - udf_avg) / regular_avg) * 100
        
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "database": "Redis UDF",
            "test_config": {
                "users_count": TEST_USERS_COUNT,
                "messages_per_dialog": MESSAGES_PER_DIALOG,
                "dialogs_per_user": DIALOGS_PER_USER
            },
            "metrics": metrics_summary,
            "comparisons": comparisons
        }
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(metrics_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Метрики сохранены в файл: {filename}")

async def main():
    global TEST_USERS_COUNT, MESSAGES_PER_DIALOG, DIALOGS_PER_USER
    
    parser = argparse.ArgumentParser(description='Тестирование производительности UDF функций Redis')
    parser.add_argument('--users', type=int, default=20, 
                       help='Количество тестовых пользователей (по умолчанию: 20)')
    parser.add_argument('--messages', type=int, default=5,
                       help='Сообщений на диалог (по умолчанию: 5)')
    parser.add_argument('--dialogs', type=int, default=3,
                       help='Диалогов на пользователя (по умолчанию: 3)')
    parser.add_argument('--api-url', default=API_URL,
                       help=f'URL API сервера (по умолчанию: {API_URL})')
    
    args = parser.parse_args()
    
    TEST_USERS_COUNT = args.users
    MESSAGES_PER_DIALOG = args.messages
    DIALOGS_PER_USER = args.dialogs
    
    print("🚀 ТЕСТИРОВАНИЕ ПРОИЗВОДИТЕЛЬНОСТИ UDF ФУНКЦИЙ REDIS")
    print(f"📊 Конфигурация теста:")
    print(f"   - Пользователей: {TEST_USERS_COUNT}")
    print(f"   - Сообщений на диалог: {MESSAGES_PER_DIALOG}")
    print(f"   - Диалогов на пользователя: {DIALOGS_PER_USER}")
    print(f"   - API URL: {args.api_url}")
    print()
    
    async with UDFPerformanceTester(args.api_url) as tester:
        # Проверка доступности сервиса
        if not await tester.check_service_availability():
            print("❌ Сервис недоступен. Убедитесь, что сервер запущен.")
            sys.exit(1)
        
        print("✅ Сервис доступен")
        
        try:
            # Этап 1: Создание пользователей
            await tester.setup_test_users(TEST_USERS_COUNT)
            
            # Этап 2: Установка дружеских связей
            await tester.setup_friendships()
            
            # Этап 3: Сравнительное тестирование
            await tester.run_comparison_tests()
            
            # Вывод результатов
            tester.print_comparison_metrics()
            tester.save_metrics_to_file()
            
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 