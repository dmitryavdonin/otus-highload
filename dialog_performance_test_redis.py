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

class DialogPerformanceTester:
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.session = None
        self.users = []  # List of (user_id, token, name)
        self.metrics = {
            'user_registration': [],
            'user_login': [],
            'friend_addition': [],
            'message_send': [],
            'message_list': [],
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
    
    async def send_message(self, token: str, recipient_id: str, text: str) -> float:
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
    
    async def get_messages(self, token: str, interlocutor_id: str) -> Tuple[List[Dict], float]:
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
    
    async def setup_test_users(self, count: int) -> None:
        """Создание тестовых пользователей"""
        print(f"🔄 Создание {count} тестовых пользователей...")
        
        tasks = []
        for i in range(count):
            first_name = f"RedisUser{i}"
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
                successful_users.append((user_id, token, f"RedisUser{i} Test{i}"))
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
    
    async def run_dialog_tests(self) -> None:
        """Запуск тестов диалогов через UDF"""
        print(f"🔄 Тестирование диалогов через Redis UDF...")
        
        # Отправка сообщений
        send_tasks = []
        for i, (user_id, token, name) in enumerate(self.users):
            for j in range(1, min(DIALOGS_PER_USER + 1, len(self.users))):
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    
                    # Отправляем несколько сообщений в каждый диалог
                    for msg_num in range(MESSAGES_PER_DIALOG):
                        message_text = f"Redis UDF сообщение {msg_num + 1} от {name}"
                        send_tasks.append(self.send_message(token, friend_id, message_text))
        
        print(f"📤 Отправка {len(send_tasks)} сообщений через UDF...")
        send_results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        successful_sends = 0
        for result in send_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка отправки UDF сообщения: {result}")
            else:
                self.metrics['message_send'].append(result)
                successful_sends += 1
        
        print(f"✅ Успешно отправлено {successful_sends} UDF сообщений")
        
        # Чтение сообщений
        read_tasks = []
        for i, (user_id, token, name) in enumerate(self.users):
            for j in range(1, min(DIALOGS_PER_USER + 1, len(self.users))):
                friend_idx = (i + j) % len(self.users)
                if friend_idx != i:
                    friend_id, _, _ = self.users[friend_idx]
                    read_tasks.append(self.get_messages(token, friend_id))
        
        print(f"📥 Чтение {len(read_tasks)} диалогов через UDF...")
        read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
        
        successful_reads = 0
        total_messages_read = 0
        for result in read_results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка чтения UDF сообщений: {result}")
            else:
                messages, duration = result
                self.metrics['message_list'].append(duration)
                successful_reads += 1
                total_messages_read += len(messages)
        
        print(f"✅ Успешно прочитано {successful_reads} UDF диалогов ({total_messages_read} сообщений)")
    
    def print_metrics(self) -> None:
        """Вывод метрик производительности"""
        print("\n" + "="*60)
        print("📊 МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ (Redis UDF)")
        print("="*60)
        
        for operation, times in self.metrics.items():
            if times:
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
        
        print("\n" + "="*60)
    
    def save_metrics_to_file(self, filename: str = "lesson-07/dialog_metrics_redis_udf.json") -> None:
        """Сохранение метрик в файл"""
        # Создаем папку lesson-07, если её нет
        os.makedirs("lesson-07", exist_ok=True)
        
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
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'database': 'Redis',
                'test_config': {
                    'users_count': len(self.users),
                    'messages_per_dialog': MESSAGES_PER_DIALOG,
                    'dialogs_per_user': DIALOGS_PER_USER
                },
                'metrics': metrics_summary
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Метрики сохранены в файл: {filename}")

async def main():
    global TEST_USERS_COUNT, MESSAGES_PER_DIALOG, DIALOGS_PER_USER
    
    parser = argparse.ArgumentParser(description='Тестирование производительности диалогов (Redis UDF)')
    parser.add_argument('--users', type=int, default=TEST_USERS_COUNT, 
                       help=f'Количество тестовых пользователей (по умолчанию: {TEST_USERS_COUNT})')
    parser.add_argument('--messages', type=int, default=MESSAGES_PER_DIALOG,
                       help=f'Сообщений на диалог (по умолчанию: {MESSAGES_PER_DIALOG})')
    parser.add_argument('--dialogs', type=int, default=DIALOGS_PER_USER,
                       help=f'Диалогов на пользователя (по умолчанию: {DIALOGS_PER_USER})')
    parser.add_argument('--api-url', default=API_URL,
                       help=f'URL API сервера (по умолчанию: {API_URL})')
    
    args = parser.parse_args()
    
    TEST_USERS_COUNT = args.users
    MESSAGES_PER_DIALOG = args.messages
    DIALOGS_PER_USER = args.dialogs
    
    print("🚀 ТЕСТИРОВАНИЕ ПРОИЗВОДИТЕЛЬНОСТИ ДИАЛОГОВ (Redis UDF)")
    print(f"📊 Конфигурация теста:")
    print(f"   - Пользователей: {TEST_USERS_COUNT}")
    print(f"   - Сообщений на диалог: {MESSAGES_PER_DIALOG}")
    print(f"   - Диалогов на пользователя: {DIALOGS_PER_USER}")
    print(f"   - API URL: {args.api_url}")
    print()
    
    async with DialogPerformanceTester(args.api_url) as tester:
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
            
            # Этап 3: Тестирование диалогов
            await tester.run_dialog_tests()
            
            # Вывод результатов
            tester.print_metrics()
            tester.save_metrics_to_file()
            
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 