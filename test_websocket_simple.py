#!/usr/bin/env python3
"""
Простой тест WebSocket сервера
"""

import sys
import os
import subprocess

# Проверяем и активируем виртуальное окружение
def setup_environment():
    """Настройка окружения для запуска тестов"""
    
    # Проверяем, находимся ли мы уже в виртуальном окружении
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Виртуальное окружение уже активировано")
        return True
    
    # Ищем виртуальное окружение
    venv_paths = ['venv', '.venv', 'env', '.env']
    venv_path = None
    
    for path in venv_paths:
        if os.path.exists(path) and os.path.isdir(path):
            venv_path = path
            break
    
    if not venv_path:
        print("❌ Виртуальное окружение не найдено")
        print("💡 Запустите сначала: ./start_service.sh")
        return False
    
    # Путь к Python в виртуальном окружении
    if os.name == 'nt':  # Windows
        python_path = os.path.join(venv_path, 'Scripts', 'python.exe')
    else:  # Unix/Linux/macOS
        python_path = os.path.join(venv_path, 'bin', 'python')
    
    if not os.path.exists(python_path):
        print(f"❌ Python не найден в виртуальном окружении: {python_path}")
        return False
    
    # Перезапускаем скрипт с Python из виртуального окружения
    print(f"🔄 Перезапуск с виртуальным окружением: {venv_path}")
    os.execv(python_path, [python_path] + sys.argv)

# Проверяем окружение при запуске
if __name__ == "__main__" and len(sys.argv) == 1:
    setup_environment()

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_websocket_connection():
    """Тестирование WebSocket подключения"""
    
    server_url = "ws://localhost:8001"
    user_id = "test_user_123"
    # Используем правильный формат токена: user_id:signature
    token = f"{user_id}:test_signature"
    
    uri = f"{server_url}/ws/{user_id}?token={token}"
    
    try:
        logger.info(f"Подключение к {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Успешно подключились к WebSocket серверу")
            
            # Ожидаем приветственное сообщение
            welcome_msg = await websocket.recv()
            welcome_data = json.loads(welcome_msg)
            logger.info(f"Получено приветствие: {welcome_data.get('data', {}).get('message')}")
            
            # Отправляем ping
            ping_message = {
                "type": "ping",
                "data": {}
            }
            await websocket.send(json.dumps(ping_message))
            logger.info("📤 Отправлен ping")
            
            # Ожидаем pong
            pong_msg = await websocket.recv()
            pong_data = json.loads(pong_msg)
            logger.info(f"📥 Получен ответ: {pong_data.get('data', {}).get('message')}")
            
            # Запрашиваем статистику
            stats_message = {
                "type": "get_stats",
                "data": {}
            }
            await websocket.send(json.dumps(stats_message))
            logger.info("📤 Запрошена статистика")
            
            # Ожидаем статистику - может прийти несколько сообщений
            stats = None
            for _ in range(3):  # Пытаемся получить до 3 сообщений
                stats_msg = await websocket.recv()
                stats_data = json.loads(stats_msg)
                
                if stats_data.get('data', {}).get('message') == 'server_stats':
                    stats = stats_data.get('data', {}).get('stats', {})
                    break
            
            if stats is None:
                logger.error("❌ Не удалось получить статистику сервера")
                return
            
            logger.info("📊 Статистика сервера:")
            logger.info(f"   WebSocket соединения: {stats.get('websocket', {}).get('total_connections', 0)}")
            logger.info(f"   Feed processor: {'работает' if stats.get('feed_processor', {}).get('is_running') else 'не работает'}")
            logger.info(f"   RabbitMQ: {'подключен' if stats.get('rabbitmq', {}).get('connected') else 'не подключен'}")
            
            # Дополнительная информация о статистике
            if stats.get('rabbitmq', {}).get('connected'):
                logger.info("✅ Система готова к обработке уведомлений")
            else:
                logger.warning("⚠️  RabbitMQ не подключен - уведомления работать не будут")
            
            # Подписываемся на обновления ленты
            subscribe_message = {
                "type": "subscribe_feed",
                "data": {}
            }
            await websocket.send(json.dumps(subscribe_message))
            logger.info("📤 Подписались на обновления ленты")
            
            # Ожидаем подтверждение
            subscribe_msg = await websocket.recv()
            subscribe_data = json.loads(subscribe_msg)
            logger.info(f"📥 Подтверждение подписки: {subscribe_data.get('data', {}).get('message')}")
            
            logger.info("✅ Тест WebSocket соединения завершен успешно")
            
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"❌ Соединение закрыто сервером: {e}")
        logger.error("💡 Возможные причины:")
        logger.error("   - Неверный токен аутентификации")
        logger.error("   - Сервер не поддерживает тестовые соединения")
        logger.error("   - Проблемы с базой данных или Redis")
    except websockets.exceptions.InvalidURI:
        logger.error("❌ Неверный URI WebSocket сервера")
    except ConnectionRefusedError:
        logger.error("❌ Не удалось подключиться к серверу. Убедитесь, что сервер запущен на localhost:8001")
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}")
        logger.error(f"   Тип ошибки: {type(e).__name__}")


async def test_http_endpoints():
    """Тестирование HTTP endpoints"""
    import aiohttp
    
    base_url = "http://localhost:8001"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Тест health check
            async with session.get(f"{base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("✅ Health check: OK")
                    logger.info(f"   Статус: {data.get('status')}")
                else:
                    logger.error(f"❌ Health check failed: {response.status}")
            
            # Тест статистики
            async with session.get(f"{base_url}/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("✅ Stats endpoint: OK")
                    logger.info(f"   WebSocket соединения: {data.get('websocket', {}).get('total_connections', 0)}")
                else:
                    logger.error(f"❌ Stats endpoint failed: {response.status}")
            
            # Тест статистики знаменитостей
            async with session.get(f"{base_url}/celebrity-stats") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("✅ Celebrity stats endpoint: OK")
                    logger.info(f"   Порог знаменитости: {data.get('celebrity_threshold', 0)}")
                else:
                    logger.error(f"❌ Celebrity stats endpoint failed: {response.status}")
                    
    except aiohttp.ClientConnectorError:
        logger.error("❌ Не удалось подключиться к HTTP серверу. Убедитесь, что сервер запущен на localhost:8001")
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании HTTP endpoints: {e}")


async def main():
    """Главная функция"""
    logger.info("🧪 Запуск тестов WebSocket сервера")
    logger.info("=" * 50)
    
    # Тестируем HTTP endpoints
    logger.info("🌐 Тестирование HTTP endpoints...")
    await test_http_endpoints()
    
    logger.info("")
    
    # Тестируем WebSocket соединение
    logger.info("🔌 Тестирование WebSocket соединения...")
    await test_websocket_connection()
    
    logger.info("")
    logger.info("🎉 Все тесты завершены!")


if __name__ == "__main__":
    asyncio.run(main()) 