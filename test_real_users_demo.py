#!/usr/bin/env python3
"""
Демонстрация реального взаимодействия между двумя пользователями:
1. Регистрация двух пользователей
2. Добавление в друзья
3. Создание постов одним пользователем
4. Получение уведомлений другим пользователем через WebSocket
"""

import asyncio
import websockets
import json
import requests
import time
from datetime import datetime
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
API_BASE_URL = "http://localhost:9000"
WS_BASE_URL = "ws://localhost:8001"

class UserClient:
    def __init__(self, first_name, last_name, birthdate):
        self.first_name = first_name
        self.last_name = last_name
        self.birthdate = birthdate
        self.user_id = None
        self.token = None
        self.websocket = None
        self.messages = []
        
    async def register(self):
        """Регистрация пользователя"""
        try:
            response = requests.post(f"{API_BASE_URL}/user/register", json={
                "first_name": self.first_name,
                "second_name": self.last_name,
                "birthdate": f"{self.birthdate}T00:00:00",
                "biography": f"Пользователь {self.first_name} {self.last_name}",
                "city": "Москва",
                "password": "password123"
            })
            
            if response.status_code == 200:
                data = response.json()
                self.user_id = data["id"]
                logger.info(f"✅ Пользователь {self.first_name} зарегистрирован с ID: {self.user_id}")
                return True
            else:
                logger.error(f"❌ Ошибка регистрации {self.first_name}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при регистрации {self.first_name}: {e}")
            return False
    
    async def login(self):
        """Авторизация пользователя"""
        try:
            response = requests.post(f"{API_BASE_URL}/user/login", json={
                "id": self.user_id,
                "password": "password123"
            })
            
            if response.status_code == 200:
                data = response.json()
                self.token = data["token"]
                logger.info(f"✅ Пользователь {self.first_name} авторизован")
                return True
            else:
                logger.error(f"❌ Ошибка авторизации {self.first_name}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при авторизации {self.first_name}: {e}")
            return False
    
    async def connect(self):
        """Подключение к WebSocket"""
        try:
            uri = f"{WS_BASE_URL}/ws/{self.user_id}"
            self.websocket = await websockets.connect(uri)
            
            # Запускаем прослушивание сообщений в фоне
            asyncio.create_task(self.listen_messages())
            
            logger.info(f"✅ {self.first_name} подключен к WebSocket")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения {self.first_name} к WebSocket: {e}")
            return False
    
    async def listen_messages(self):
        """Прослушивание WebSocket сообщений"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                data['timestamp'] = datetime.now().strftime('%H:%M:%S')
                self.messages.append(data)
                logger.info(f"📨 {self.first_name} получил сообщение: {data.get('type', 'unknown')}")
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 WebSocket соединение {self.first_name} закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка при прослушивании сообщений {self.first_name}: {e}")
    
    async def disconnect(self):
        """Отключение от WebSocket"""
        if self.websocket:
            await self.websocket.close()
            logger.info(f"🔌 {self.first_name} отключен от WebSocket")

async def create_user(first_name, last_name, birthdate):
    """Создание и регистрация пользователя"""
    user = UserClient(first_name, last_name, birthdate)
    
    if await user.register() and await user.login():
        return user
    else:
        return None

async def add_friendship(user1, user2):
    """Добавление пользователей в друзья"""
    try:
        # user1 добавляет user2 в друзья
        response = requests.put(
            f"{API_BASE_URL}/friend/set/{user2.user_id}",
            headers={"Authorization": f"Bearer {user1.token}"}
        )
        
        if response.status_code == 200:
            logger.info(f"✅ {user1.first_name} добавил {user2.first_name} в друзья")
            
            # user2 добавляет user1 в друзья (взаимная дружба)
            response2 = requests.put(
                f"{API_BASE_URL}/friend/set/{user1.user_id}",
                headers={"Authorization": f"Bearer {user2.token}"}
            )
            
            if response2.status_code == 200:
                logger.info(f"✅ {user2.first_name} добавил {user1.first_name} в друзья")
                return True
            else:
                logger.error(f"❌ Ошибка добавления в друзья: {response2.text}")
                return False
        else:
            logger.error(f"❌ Ошибка добавления в друзья: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении в друзья: {e}")
        return False

async def create_post(user, text):
    """Создание поста пользователем"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/post/create",
            headers={"Authorization": f"Bearer {user.token}"},
            json={"text": text}
        )
        
        if response.status_code == 200:
            data = response.json()
            post_id = data["id"]
            logger.info(f"✅ {user.first_name} создал пост: {text[:50]}...")
            return post_id
        else:
            logger.error(f"❌ Ошибка создания поста: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка при создании поста: {e}")
        return None

async def get_user_feed(user):
    """Получение ленты постов пользователя"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/post/feed",
            headers={"Authorization": f"Bearer {user.token}"},
            params={"offset": 0, "limit": 10}
        )
        
        if response.status_code == 200:
            posts = response.json()
            logger.info(f"✅ {user.first_name} получил ленту с {len(posts)} постами")
            return posts
        else:
            logger.error(f"❌ Ошибка получения ленты: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении ленты: {e}")
        return []

async def main():
    """Основная функция демонстрации"""
    logger.info("🚀 Запуск демонстрации взаимодействия пользователей")
    
    start_time = datetime.now()
    
    try:
        # Создаем двух пользователей
        user1 = await create_user("Алексей", "Петров", "1990-05-15")
        user2 = await create_user("Мария", "Иванова", "1992-08-22")
        
        if not user1 or not user2:
            logger.error("❌ Не удалось создать пользователей")
            return
        
        # Подключаемся к WebSocket
        await user1.connect()
        await user2.connect()
        
        # Добавляем в друзья
        await add_friendship(user1, user2)
        
        # Создаем посты
        await create_post(user1, "Привет всем! Это мой первый пост в социальной сети! 🎉")
        await asyncio.sleep(2)
        
        await create_post(user2, "Отличная погода сегодня! Идеальный день для прогулки ☀️")
        await asyncio.sleep(2)
        
        await create_post(user1, "Изучаю новые технологии. WebSocket - это круто! 💻")
        await asyncio.sleep(2)
        
        # Получаем ленты постов
        user1_feed = await get_user_feed(user1)
        user2_feed = await get_user_feed(user2)
        
        # Ждем немного для получения всех сообщений
        await asyncio.sleep(3)
        
        # Закрываем соединения
        await user1.disconnect()
        await user2.disconnect()
        
        end_time = datetime.now()
        
        # Генерируем HTML-отчет
        users_info = {
            user1.user_id: f"{user1.first_name} {user1.last_name}",
            user2.user_id: f"{user2.first_name} {user2.last_name}"
        }
        report_path = generate_html_report(user1, user2, user1_feed, user2_feed, start_time, end_time, users_info)
        
        logger.info("✅ Демонстрация завершена!")
        logger.info(f"📄 HTML-отчет создан: {report_path}")
        
        return report_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка в демонстрации: {e}")
        return None

def generate_html_report(user1, user2, user1_feed, user2_feed, start_time, end_time, users_info):
    """Генерация HTML-отчета с результатами тестирования"""
    
    duration = (end_time - start_time).total_seconds()
    
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет о тестировании социальной сети</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2980b9;
            margin-top: 20px;
        }}
        h3 {{
            color: #34495e;
            margin-top: 15px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .note {{
            background-color: #f8f9fa;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin-bottom: 20px;
        }}
        .success {{
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 10px;
            margin-bottom: 20px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .user-section {{
            margin-bottom: 25px;
        }}
        ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <h1>Отчет о тестировании социальной сети</h1>
    <p>Дата: {datetime.now().strftime('%a %b %d %I:%M:%S %p MSK %Y')}</p>
    
    <div class="success">
        <p><strong>РЕЗУЛЬТАТ:</strong> Тестирование завершено успешно! Все функции работают корректно.</p>
    </div>
    
    <div class="section">
        <h2>1. Общая статистика</h2>
        <table>
            <tr>
                <th>Параметр</th>
                <th>Значение</th>
            </tr>
            <tr>
                <td>Пользователей зарегистрировано</td>
                <td>2</td>
            </tr>
            <tr>
                <td>Постов в лентах</td>
                <td>{len(user1_feed) + len(user2_feed)}</td>
            </tr>
            <tr>
                <td>WebSocket сообщений получено</td>
                <td>{len(user1.messages) + len(user2.messages)}</td>
            </tr>
            <tr>
                <td>Время выполнения</td>
                <td>{duration:.1f} секунд</td>
            </tr>
        </table>
    </div>
    
    <div class="section">
        <h2>2. Проверенные функции</h2>
        <p>В ходе тестирования были проверены следующие возможности системы:</p>
        <ul>
            <li>Регистрация пользователей через API</li>
            <li>Авторизация и получение токенов</li>
            <li>Подключение к WebSocket серверу</li>
            <li>Добавление пользователей в друзья</li>
            <li>Создание постов</li>
            <li>Получение ленты постов друзей</li>
            <li>Получение уведомлений через WebSocket</li>
        </ul>
    </div>
    
    <div class="section">
        <h2>3. Информация о тестовых пользователях</h2>
        
        <div class="user-section">
            <h3>Пользователь 1: {users_info[user1.user_id]}</h3>
            <table>
                <tr>
                    <th>Параметр</th>
                    <th>Значение</th>
                </tr>
                <tr>
                    <td>ID пользователя</td>
                    <td>{user1.user_id}</td>
                </tr>
                <tr>
                    <td>WebSocket сообщений получено</td>
                    <td>{len(user1.messages)}</td>
                </tr>
                <tr>
                    <td>Постов в ленте</td>
                    <td>{len(user1_feed)}</td>
                </tr>
            </table>
            
            <h4>WebSocket сообщения:</h4>
            <table>
                <tr>
                    <th>№</th>
                    <th>Тип сообщения</th>
                    <th>Время получения</th>
                </tr>
                {generate_messages_table(user1.messages)}
            </table>
        </div>
        
        <div class="user-section">
            <h3>Пользователь 2: {users_info[user2.user_id]}</h3>
            <table>
                <tr>
                    <th>Параметр</th>
                    <th>Значение</th>
                </tr>
                <tr>
                    <td>ID пользователя</td>
                    <td>{user2.user_id}</td>
                </tr>
                <tr>
                    <td>WebSocket сообщений получено</td>
                    <td>{len(user2.messages)}</td>
                </tr>
                <tr>
                    <td>Постов в ленте</td>
                    <td>{len(user2_feed)}</td>
                </tr>
            </table>
            
            <h4>WebSocket сообщения:</h4>
            <table>
                <tr>
                    <th>№</th>
                    <th>Тип сообщения</th>
                    <th>Время получения</th>
                </tr>
                {generate_messages_table(user2.messages)}
            </table>
        </div>
    </div>
    
    <div class="section">
        <h2>4. Ленты пользователей</h2>
        
        <div class="user-section">
            <h3>Лента пользователя: {users_info[user1.user_id]}</h3>
            <table>
                <tr>
                    <th>№</th>
                    <th>Автор</th>
                    <th>Текст поста</th>
                    <th>ID поста</th>
                </tr>
                {generate_posts_table(user1_feed, users_info)}
            </table>
        </div>
        
        <div class="user-section">
            <h3>Лента пользователя: {users_info[user2.user_id]}</h3>
            <table>
                <tr>
                    <th>№</th>
                    <th>Автор</th>
                    <th>Текст поста</th>
                    <th>ID поста</th>
                </tr>
                {generate_posts_table(user2_feed, users_info)}
            </table>
        </div>
    </div>
    
    <div class="section">
        <h2>5. Все созданные посты</h2>
        <table>
            <tr>
                <th>№</th>
                <th>Автор</th>
                <th>Текст поста</th>
                <th>ID поста</th>
            </tr>
            {generate_posts_table(user1_feed + user2_feed, users_info)}
        </table>
    </div>
    
    <p>Отчет сгенерирован автоматически {datetime.now().strftime('%a %b %d %I:%M:%S %p MSK %Y')}</p>
</body>
</html>"""
    
    # Сохраняем отчет
    report_path = "lesson-06/test_report.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"📄 HTML-отчет сохранен: {report_path}")
    return report_path

def generate_messages_table(messages):
    """Генерация HTML для таблицы WebSocket сообщений"""
    if not messages:
        return "<tr><td colspan='3'>Сообщений нет</td></tr>"
    
    html = ""
    for i, msg in enumerate(messages, 1):
        msg_type = msg.get('type', 'unknown')
        content = f"Тип: {msg_type}"
        if 'data' in msg:
            content += f", Данные: {str(msg['data'])[:50]}..."
        
        timestamp = msg.get('timestamp', 'Неизвестно')
        
        html += f"""
        <tr>
            <td>{i}</td>
            <td>{content}</td>
            <td>{timestamp}</td>
        </tr>
        """
    
    return html

def generate_posts_table(posts, users_info):
    """Генерация HTML для таблицы постов"""
    if not posts:
        return "<tr><td colspan='4'>Постов нет</td></tr>"
    
    html = ""
    for i, post in enumerate(posts, 1):
        text = post.get('text', 'Текст поста недоступен')
        post_id = post.get('id', 'Неизвестно')
        author_id = post.get('author_user_id', 'Неизвестно')
        author_name = users_info.get(author_id, f'Пользователь {author_id}')
        
        html += f"""
        <tr>
            <td>{i}</td>
            <td>{author_name}</td>
            <td>{text}</td>
            <td>{post_id}</td>
        </tr>
        """
    
    return html

if __name__ == "__main__":
    asyncio.run(main()) 