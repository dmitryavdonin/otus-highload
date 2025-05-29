import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os

from websocket_manager import websocket_manager
from feed_processor import feed_processor
from celebrity_handler import celebrity_handler
from rabbitmq_client import rabbitmq_client
from websocket_models import WebSocketMessage, WebSocketMessageType
from auth import get_current_user_from_token

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запуск
    logger.info("Starting WebSocket server...")
    
    try:
        # Запускаем процессор ленты
        await feed_processor.start()
        logger.info("Feed processor started")
        
        yield
        
    finally:
        # Остановка
        logger.info("Shutting down WebSocket server...")
        
        # Останавливаем процессор ленты
        await feed_processor.stop()
        logger.info("Feed processor stopped")
        
        # Отключаем всех пользователей
        if hasattr(websocket_manager, 'disconnect_all'):
            await websocket_manager.disconnect_all()
        logger.info("All WebSocket connections closed")


# Создаем FastAPI приложение
app = FastAPI(
    title="Social Network WebSocket Server",
    description="Real-time updates server for social network",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str = None):
    """
    WebSocket эндпоинт для подключения пользователей
    
    Args:
        websocket: WebSocket соединение
        user_id: ID пользователя
        token: JWT токен для аутентификации
    """
    try:
        # Аутентификация пользователя
        if token:
            try:
                authenticated_user = await get_current_user_from_token(token)
                logger.info(f"User {user_id} authenticated successfully")
            except Exception as e:
                logger.warning(f"Authentication failed for user {user_id}: {e}")
                await websocket.close(code=4001, reason="Authentication failed")
                return
        
        # Регистрируем пользователя (accept() вызывается внутри connect_user)
        success = await websocket_manager.connect_user(user_id, websocket)
        if not success:
            await websocket.close(code=4002, reason="Failed to register connection")
            return
        
        logger.info(f"User {user_id} connected via WebSocket")
        
        # Отправляем приветственное сообщение
        welcome_message = WebSocketMessage(
            type=WebSocketMessageType.SYSTEM,
            data={
                "message": "Connected successfully",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "server_info": {
                    "version": "1.0.0",
                    "features": ["real_time_feed", "celebrity_handling", "batched_notifications"]
                }
            }
        )
        await websocket.send_text(welcome_message.model_dump_json())
        
        # Основной цикл обработки сообщений
        try:
            while True:
                # Ожидаем сообщения от клиента
                data = await websocket.receive_text()
                
                try:
                    message_data = json.loads(data)
                    await handle_client_message(user_id, message_data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from user {user_id}: {data}")
                except Exception as e:
                    logger.error(f"Error handling message from user {user_id}: {e}")
                    
        except WebSocketDisconnect:
            logger.info(f"User {user_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {e}")
        finally:
            # Отключаем пользователя
            await websocket_manager.disconnect_user(user_id)
            
    except Exception as e:
        logger.error(f"WebSocket endpoint error for user {user_id}: {e}")
        try:
            await websocket.close(code=4000, reason="Internal server error")
        except:
            pass


async def handle_client_message(user_id: str, message_data: Dict[str, Any]):
    """
    Обработать сообщение от клиента
    
    Args:
        user_id: ID пользователя
        message_data: Данные сообщения
    """
    try:
        message_type = message_data.get("type")
        data = message_data.get("data", {})
        
        if message_type == "ping":
            # Ответ на ping
            pong_message = WebSocketMessage(
                type=WebSocketMessageType.SYSTEM,
                data={
                    "message": "pong",
                    "timestamp": datetime.now().isoformat()
                }
            )
            await websocket_manager.send_to_user(user_id, pong_message.model_dump())
            
        elif message_type == "get_stats":
            # Получить статистику
            stats = await get_server_stats()
            stats_message = WebSocketMessage(
                type=WebSocketMessageType.SYSTEM,
                data={
                    "message": "server_stats",
                    "stats": stats,
                    "timestamp": datetime.now().isoformat()
                }
            )
            await websocket_manager.send_to_user(user_id, stats_message.model_dump())
            
        elif message_type == "subscribe_feed":
            # Подписка на обновления ленты (уже активна по умолчанию)
            response_message = WebSocketMessage(
                type=WebSocketMessageType.SYSTEM,
                data={
                    "message": "subscribed_to_feed",
                    "timestamp": datetime.now().isoformat()
                }
            )
            await websocket_manager.send_to_user(user_id, response_message.model_dump())
            
        else:
            logger.warning(f"Unknown message type from user {user_id}: {message_type}")
            
    except Exception as e:
        logger.error(f"Error handling client message from user {user_id}: {e}")


@app.get("/health")
async def health_check():
    """Проверка здоровья сервера"""
    stats = await get_server_stats()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "stats": stats
    }


@app.get("/stats")
async def get_stats():
    """Получить статистику сервера"""
    return await get_server_stats()


@app.get("/celebrity-stats")
async def get_celebrity_stats():
    """Получить статистику знаменитостей"""
    return await celebrity_handler.get_celebrity_stats()


@app.post("/celebrity-settings")
async def update_celebrity_settings(
    celebrity_threshold: Optional[int] = None,
    batch_size: Optional[int] = None,
    batch_delay: Optional[float] = None
):
    """
    Обновить настройки обработчика знаменитостей
    
    Args:
        celebrity_threshold: Порог знаменитости
        batch_size: Размер батча
        batch_delay: Задержка между батчами
    """
    try:
        celebrity_handler.update_settings(
            celebrity_threshold=celebrity_threshold,
            batch_size=batch_size,
            batch_delay=batch_delay
        )
        
        return {
            "success": True,
            "message": "Settings updated successfully",
            "current_settings": {
                "celebrity_threshold": celebrity_handler.celebrity_threshold,
                "batch_size": celebrity_handler.batch_size,
                "batch_delay": celebrity_handler.batch_delay
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test-post")
async def test_post_notification(
    post_id: str,
    author_user_id: str,
    post_text: str = "Test post"
):
    """
    Тестовый эндпоинт для отправки уведомления о посте
    
    Args:
        post_id: ID поста
        author_user_id: ID автора
        post_text: Текст поста
    """
    try:
        # Публикуем событие в RabbitMQ
        event_data = {
            "event_type": "post_created",
            "post_id": post_id,
            "author_user_id": author_user_id,
            "post_text": post_text,
            "created_at": datetime.now().isoformat()
        }
        
        await rabbitmq_client.publish_event("feed_updates", event_data)
        
        return {
            "success": True,
            "message": "Test post notification sent",
            "event_data": event_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test-friendship")
async def test_friendship_notification(friendship_data: dict):
    """
    Тестовый эндпоинт для отправки уведомления о дружбе
    
    Args:
        friendship_data: Данные о дружбе
    """
    try:
        # Проверяем обязательные поля
        required_fields = ["event_type", "user_id", "friend_user_id"]
        for field in required_fields:
            if field not in friendship_data:
                raise HTTPException(
                    status_code=422, 
                    detail=f"Missing required field: {field}"
                )
        
        # Добавляем timestamp если его нет
        if "created_at" not in friendship_data:
            friendship_data["created_at"] = datetime.now().isoformat()
        
        # Публикуем событие в RabbitMQ
        await rabbitmq_client.publish_event("feed_updates", friendship_data)
        
        return {
            "success": True,
            "message": "Test friendship notification sent",
            "event_data": friendship_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_server_stats() -> Dict[str, Any]:
    """Получить статистику сервера"""
    try:
        # Статистика WebSocket соединений
        ws_stats = websocket_manager.get_stats()
        
        # Статистика процессора ленты
        processor_stats = await feed_processor.get_processing_stats()
        
        # Статистика знаменитостей
        celebrity_stats = await celebrity_handler.get_celebrity_stats()
        
        return {
            "websocket": ws_stats,
            "feed_processor": processor_stats,
            "celebrity_handler": {
                "threshold": celebrity_handler.celebrity_threshold,
                "batch_size": celebrity_handler.batch_size,
                "batch_delay": celebrity_handler.batch_delay,
                "total_celebrities": celebrity_stats.get("total_celebrities", 0)
            },
            "rabbitmq": {
                "connected": rabbitmq_client.is_connected() if hasattr(rabbitmq_client, 'is_connected') else False
            },
            "server": {
                "uptime": "N/A",  # Можно добавить отслеживание времени работы
                "version": "1.0.0"
            }
        }
    except Exception as e:
        logger.error(f"Error getting server stats: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Проверяем режим разработки
    development_mode = os.getenv("DEVELOPMENT_MODE", "false").lower() == "true"
    
    # Запуск сервера
    uvicorn.run(
        "websocket_server:app",
        host="0.0.0.0",
        port=8001,
        reload=development_mode,  # Автоперезагрузка только в режиме разработки
        log_level="info"
    ) 