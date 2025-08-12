#!/usr/bin/env python3
"""
Нагрузочное тестирование отказоустойчивости для урока 9
"""

import asyncio
import aiohttp
import random
import json
import time
from datetime import date, timedelta
from typing import List, Dict, Optional
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
NGINX_URL = "http://localhost"
API_URL = "http://localhost:9000"  # Прямое подключение для отладки

# Данные для генерации пользователей
FIRST_NAMES = ["Александр", "Дмитрий", "Максим", "Сергей", "Андрей", "Алексей", "Артём", "Илья", "Кирилл", "Михаил",
               "Анна", "Мария", "Елена", "Ольга", "Татьяна", "Наталья", "Ирина", "Светлана", "Екатерина", "Юлия"]
LAST_NAMES = ["Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов", "Васильев", "Соколов", "Михайлов", "Новиков",
              "Федоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семенов", "Егоров", "Павлов", "Козлов", "Степанов"]
CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", 
          "Красноярск", "Челябинск", "Самара", "Уфа", "Ростов-на-Дону", "Краснодар", "Омск", "Воронеж", "Пермь"]
BIOGRAPHIES = ["Люблю путешествовать", "Увлекаюсь спортом", "Читаю книги", "Программист", 
               "Занимаюсь фотографией", "Играю на гитаре", "Изучаю языки", "Люблю готовить"]

class LoadTester:
    def __init__(self):
        self.users: List[Dict] = []
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'response_times': [],
            'errors': []
        }
    
    def generate_user_data(self, index: int) -> Dict:
        """Генерирует данные для пользователя"""
        birth_date = date(1980, 1, 1) + timedelta(days=random.randint(0, 15000))
        return {
            "first_name": random.choice(FIRST_NAMES),
            "second_name": random.choice(LAST_NAMES), 
            "birthdate": birth_date.strftime("%Y-%m-%dT00:00:00"),  # DateTime format
            "biography": random.choice(BIOGRAPHIES) if random.random() > 0.3 else None,
            "city": random.choice(CITIES),
            "password": f"password{index:03d}"
        }
    
    async def register_user(self, session: aiohttp.ClientSession, user_data: Dict) -> Optional[Dict]:
        """Регистрирует пользователя с retry логикой"""
        for attempt in range(2):  # Максимум 2 попытки
            start_time = time.time()
            try:
                async with session.post(f"{NGINX_URL}/user/register", json=user_data) as resp:
                    self.metrics['total_requests'] += 1
                    response_time = time.time() - start_time
                    self.metrics['response_times'].append(response_time)
                    
                    if resp.status == 200:
                        result = await resp.json()
                        self.metrics['successful_requests'] += 1
                        return {
                            'id': result['id'],
                            'first_name': result['first_name'],
                            'second_name': result['second_name'],
                            'password': user_data['password']
                        }
                    elif resp.status == 500 and attempt < 1:  # Retry только при 500 и первой попытке
                        await asyncio.sleep(0.1)
                        continue
                    else:
                        self.metrics['failed_requests'] += 1
                        error_msg = f"Registration failed: {resp.status}"
                        self.metrics['errors'].append(error_msg)
                        logger.error(error_msg)
                        return None
            except Exception as e:
                if attempt < 1:  # Retry при исключении
                    await asyncio.sleep(0.1)
                    continue
                else:
                    self.metrics['failed_requests'] += 1
                    error_msg = f"Registration error: {str(e)}"
                    self.metrics['errors'].append(error_msg)
                    logger.error(error_msg)
                    return None
        return None
    
    async def create_test_users(self, count: int = 100) -> List[Dict]:
        """Создает тестовых пользователей с ограничением параллельности"""
        logger.info(f"Creating {count} test users...")
        
        # Ограничиваем количество одновременных запросов
        semaphore = asyncio.Semaphore(5)  # Максимум 5 одновременных запросов
        
        async def register_with_semaphore(session, user_data):
            async with semaphore:
                return await self.register_user(session, user_data)
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in range(count):
                user_data = self.generate_user_data(i)
                tasks.append(register_with_semaphore(session, user_data))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            users = []
            for i, result in enumerate(results):
                if isinstance(result, dict) and result:
                    users.append(result)
                    if (i + 1) % 10 == 0:
                        logger.info(f"Created {i + 1}/{count} users")
                elif isinstance(result, Exception):
                    logger.error(f"User {i+1} creation failed: {result}")
            
            logger.info(f"Successfully created {len(users)} users out of {count}")
            self.users = users
            return users
    
    async def login_user(self, session: aiohttp.ClientSession, user: Dict) -> Optional[str]:
        """Авторизует пользователя с retry логикой для репликации"""
        login_data = {
            "id": user['id'],
            "password": user['password']
        }
        
        # Retry до 3 раз в случае проблем с репликацией
        for attempt in range(3):
            start_time = time.time()
            try:
                async with session.post(f"{NGINX_URL}/user/login", json=login_data) as resp:
                    self.metrics['total_requests'] += 1
                    response_time = time.time() - start_time
                    self.metrics['response_times'].append(response_time)
                    
                    if resp.status == 200:
                        result = await resp.json()
                        self.metrics['successful_requests'] += 1
                        return result['token']
                    elif resp.status == 500 and attempt < 2:  # Retry при 500 ошибке
                        self.metrics['failed_requests'] += 1
                        await asyncio.sleep(0.5 * (attempt + 1))  # Увеличивающаяся задержка
                        continue
                    else:
                        self.metrics['failed_requests'] += 1
                        response_text = await resp.text()
                        logger.error(f"Login failed with status {resp.status}: {response_text}")
                        return None
            except Exception as e:
                self.metrics['failed_requests'] += 1
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"Login error: {str(e)}")
                    return None
        return None
    
    async def get_user_profile(self, session: aiohttp.ClientSession, user_id: str, token: str) -> bool:
        """Получает профиль пользователя (тест чтения из слейвов)"""
        start_time = time.time()
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with session.get(f"{NGINX_URL}/user/get/{user_id}", headers=headers) as resp:
                self.metrics['total_requests'] += 1
                response_time = time.time() - start_time
                self.metrics['response_times'].append(response_time)
                
                if resp.status == 200:
                    self.metrics['successful_requests'] += 1
                    return True
                else:
                    self.metrics['failed_requests'] += 1
                    response_text = await resp.text()
                    error_msg = f"Get user failed {resp.status}: {response_text}"
                    self.metrics['errors'].append(error_msg)
                    logger.error(error_msg)
                    return False
        except Exception as e:
            self.metrics['failed_requests'] += 1
            error_msg = f"Get user error: {str(e)}"
            self.metrics['errors'].append(error_msg)
            logger.error(error_msg)
            return False
    
    async def search_users(self, session: aiohttp.ClientSession, query: str, token: str) -> bool:
        """Поиск пользователей (тест чтения из слейвов)"""
        start_time = time.time()
        try:
            headers = {"Authorization": f"Bearer {token}"}
            params = {"first_name": query, "second_name": query}
            async with session.get(f"{NGINX_URL}/user/search", params=params, headers=headers) as resp:
                self.metrics['total_requests'] += 1
                response_time = time.time() - start_time
                self.metrics['response_times'].append(response_time)
                
                if resp.status == 200:
                    self.metrics['successful_requests'] += 1
                    return True
                else:
                    self.metrics['failed_requests'] += 1
                    response_text = await resp.text()
                    error_msg = f"Search users failed {resp.status}: {response_text}"
                    self.metrics['errors'].append(error_msg)
                    logger.error(error_msg)
                    return False
        except Exception as e:
            self.metrics['failed_requests'] += 1
            error_msg = f"Search users error: {str(e)}"
            self.metrics['errors'].append(error_msg)
            logger.error(error_msg)
            return False
    
    async def run_read_load_test(self, duration: int = 60):
        """Запускает нагрузочный тест для операций чтения"""
        logger.info(f"Starting read load test for {duration} seconds...")
        
        if not self.users:
            logger.error("No users available for testing. Run create_test_users() first.")
            return
        
        # Ждем синхронизацию репликации перед логином
        print("⏳ Ждем 3 секунды для синхронизации репликации...")
        await asyncio.sleep(3)
        
        # Получаем токены для пользователей
        user_tokens = {}
        async with aiohttp.ClientSession() as session:
            for user in self.users[:10]:  # Берем первых 10 пользователей для токенов
                token = await self.login_user(session, user)
                if token:
                    user_tokens[user['id']] = token
                # Небольшая задержка между логинами
                await asyncio.sleep(0.1)
        
        if not user_tokens:
            logger.error("No user tokens available for read test")
            return
        
        logger.info(f"Got {len(user_tokens)} user tokens for read test")
        
        end_time = time.time() + duration
        tasks = []
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                # Случайный выбор операции чтения
                operation = random.choice(['get_profile', 'search'])
                user_id = random.choice(list(user_tokens.keys()))
                token = user_tokens[user_id]
                
                if operation == 'get_profile':
                    tasks.append(self.get_user_profile(session, user_id, token))
                elif operation == 'search':
                    query = random.choice(['Иван', 'Анна', 'Тест', 'User', 'Петр'])
                    tasks.append(self.search_users(session, query, token))
                
                # Ограничиваем количество одновременных запросов
                if len(tasks) >= 20:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    tasks = []
                
                await asyncio.sleep(0.1)  # Небольшая пауза между запросами
            
            # Завершаем оставшиеся задачи
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Read load test completed")
    
    async def add_friend(self, session: aiohttp.ClientSession, token: str, friend_id: str) -> bool:
        """Добавляет друга (операция записи в мастер)"""
        start_time = time.time()
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with session.put(f"{NGINX_URL}/friend/set/{friend_id}", headers=headers) as resp:
                self.metrics['total_requests'] += 1
                response_time = time.time() - start_time
                self.metrics['response_times'].append(response_time)
                
                if resp.status in [200, 201]:  # Успех или уже друзья
                    self.metrics['successful_requests'] += 1
                    return True
                else:
                    self.metrics['failed_requests'] += 1
                    return False
        except Exception as e:
            self.metrics['failed_requests'] += 1
            logger.error(f"Add friend error: {str(e)}")
            return False

    async def create_post(self, session: aiohttp.ClientSession, token: str, text: str) -> bool:
        """Создаёт пост (операция записи в мастер)"""
        start_time = time.time()
        try:
            headers = {"Authorization": f"Bearer {token}"}
            post_data = {"text": text}
            async with session.post(f"{NGINX_URL}/post/create", headers=headers, json=post_data) as resp:
                self.metrics['total_requests'] += 1
                response_time = time.time() - start_time
                self.metrics['response_times'].append(response_time)
                
                if resp.status in [200, 201]:
                    self.metrics['successful_requests'] += 1
                    return True
                else:
                    self.metrics['failed_requests'] += 1
                    return False
        except Exception as e:
            self.metrics['failed_requests'] += 1
            logger.error(f"Create post error: {str(e)}")
            return False

    async def run_mixed_load_test(self, duration: int = 60):
        """Запускает смешанный нагрузочный тест (чтение + запись)"""
        logger.info(f"Starting mixed load test for {duration} seconds...")
        
        if not self.users:
            logger.error("No users available for testing. Run create_test_users() first.")
            return
        
        # Ждем синхронизацию репликации 
        print("⏳ Ждем 2 секунды для синхронизации репликации...")
        await asyncio.sleep(2)
        
        # Получаем токены для операций записи
        user_tokens = []
        async with aiohttp.ClientSession() as session:
            for user in self.users[:10]:  # Берём первых 10 пользователей
                token = await self.login_user(session, user)
                if token:
                    user_tokens.append({'user': user, 'token': token})
                await asyncio.sleep(0.1)  # Пауза между логинами
        
        if not user_tokens:
            logger.error("Failed to get any user tokens")
            return
        
        end_time = time.time() + duration
        tasks = []
        post_texts = [
            "Отличная погода сегодня!",
            "Работаю над новым проектом",
            "Хороший день для программирования",
            "Изучаю отказоустойчивые системы",
            "HAProxy работает отлично!",
            "Nginx балансирует нагрузку",
            "PostgreSQL слейвы справляются",
            "Тестируем производительность"
        ]
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                # 70% чтение, 30% запись
                if random.random() < 0.7:
                    # Операции чтения (из слейвов) - нужны токены для авторизации
                    if user_tokens:
                        user_with_token = random.choice(user_tokens)
                        operation = random.choice(['get_profile', 'search'])
                        if operation == 'get_profile':
                            tasks.append(self.get_user_profile(session, user_with_token['user']['id'], user_with_token['token']))
                        elif operation == 'search':
                            query = random.choice(['Иван', 'Анна', 'Тест', 'User', 'Петр'])
                            tasks.append(self.search_users(session, query, user_with_token['token']))
                else:
                    # Операции записи (в мастер)
                    if user_tokens:
                        user_with_token = random.choice(user_tokens)
                        operation = random.choice(['add_friend', 'create_post'])
                        
                        if operation == 'add_friend':
                            friend = random.choice([u for u in self.users if u['id'] != user_with_token['user']['id']])
                            tasks.append(self.add_friend(session, user_with_token['token'], friend['id']))
                        elif operation == 'create_post':
                            text = random.choice(post_texts)
                            tasks.append(self.create_post(session, user_with_token['token'], text))
                
                # Ограничиваем количество одновременных запросов
                if len(tasks) >= 20:  # Уменьшаем для стабильности
                    await asyncio.gather(*tasks, return_exceptions=True)
                    tasks = []
                
                await asyncio.sleep(0.08)  # Немного увеличиваем интервал для стабильности
            
            # Завершаем оставшиеся задачи
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Mixed load test completed")
    
    def print_metrics(self):
        """Выводит метрики тестирования"""
        success_rate = (self.metrics['successful_requests'] / self.metrics['total_requests']) * 100 if self.metrics['total_requests'] > 0 else 0
        avg_response_time = sum(self.metrics['response_times']) / len(self.metrics['response_times']) if self.metrics['response_times'] else 0
        
        print("\n" + "="*50)
        print("МЕТРИКИ ТЕСТИРОВАНИЯ")
        print("="*50)
        print(f"Всего запросов: {self.metrics['total_requests']}")
        print(f"Успешных: {self.metrics['successful_requests']}")
        print(f"Неудачных: {self.metrics['failed_requests']}")
        print(f"Процент успеха: {success_rate:.2f}%")
        print(f"Среднее время отклика: {avg_response_time:.3f}s")
        if self.metrics['response_times']:
            print(f"Мин. время отклика: {min(self.metrics['response_times']):.3f}s")
            print(f"Макс. время отклика: {max(self.metrics['response_times']):.3f}s")
        print(f"Создано пользователей: {len(self.users)}")
        
        if self.metrics['errors']:
            print(f"\nОшибки ({len(self.metrics['errors'])}):")
            for error in self.metrics['errors'][-5:]:  # Показываем последние 5 ошибок
                print(f"  - {error}")
        print("="*50)
    
    def reset_metrics(self):
        """Сбрасывает метрики для нового теста"""
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'response_times': [],
            'errors': []
        }

async def main():
    """Основная функция тестирования"""
    tester = LoadTester()
    
    # Этап 1: Создание тестовых пользователей
    print("\n📝 Этап 1: Создание тестовых пользователей")
    await tester.create_test_users(50)
    tester.print_metrics()
    
    # Этап 2: Тест чтения (перед отказами)
    print("\n📖 Этап 2: Базовый тест чтения (20 секунд)")
    tester.reset_metrics()
    await tester.run_read_load_test(20)
    tester.print_metrics()
    
    # Этап 3: Смешанный тест (перед отказами)
    print("\n🔄 Этап 3: Смешанный тест чтение+запись (20 секунд)")
    tester.reset_metrics()
    await tester.run_mixed_load_test(20)
    tester.print_metrics()
    
    print("\n✅ Подготовительные тесты завершены!")
    print("💀 Теперь можно тестировать отказы:")
    print("   1. kill -9 postgres-slave во время run_read_load_test()")
    print("   2. kill -9 app2 во время run_mixed_load_test()")
    print("   3. Мониторить HAProxy stats: http://localhost:8404/stats")

if __name__ == "__main__":
    asyncio.run(main()) 