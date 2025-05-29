import asyncio
import json
import logging
from typing import Dict, Set, Optional, List, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from websocket_models import (
    WebSocketMessage, 
    WebSocketConnectionInfo, 
    ConnectionAckMessage, 
    ErrorMessage,
    PostCreatedWebSocketMessage,
    PostCreatedEvent,
    WebSocketMessageType
)

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Менеджер для управления WebSocket соединениями"""
    
    def __init__(self):
        # Словарь активных соединений: user_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Информация о соединениях: user_id -> WebSocketConnectionInfo
        self.connection_info: Dict[str, WebSocketConnectionInfo] = {}
        # Обратный индекс: WebSocket -> user_id
        self.websocket_to_user: Dict[WebSocket, str] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str) -> bool:
        """
        Подключить пользователя к WebSocket
        
        Args:
            websocket: WebSocket соединение
            user_id: ID пользователя
            
        Returns:
            True если подключение успешно, False иначе
        """
        try:
            await websocket.accept()
            
            # Если пользователь уже подключен, отключаем старое соединение
            if user_id in self.active_connections:
                old_websocket = self.active_connections[user_id]
                await self._disconnect_websocket(old_websocket)
            
            # Добавляем новое соединение
            self.active_connections[user_id] = websocket
            self.websocket_to_user[websocket] = user_id
            self.connection_info[user_id] = WebSocketConnectionInfo(user_id=user_id)
            
            # Отправляем подтверждение подключения
            ack_message = ConnectionAckMessage()
            await self._send_to_websocket(websocket, ack_message.model_dump())
            
            logger.info(f"User {user_id} connected via WebSocket")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting user {user_id}: {e}")
            return False
    
    async def disconnect(self, user_id: str):
        """
        Отключить пользователя от WebSocket
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            await self._disconnect_websocket(websocket)
    
    async def disconnect_websocket(self, websocket: WebSocket):
        """
        Отключить WebSocket соединение
        
        Args:
            websocket: WebSocket соединение
        """
        await self._disconnect_websocket(websocket)
    
    async def _disconnect_websocket(self, websocket: WebSocket):
        """Внутренний метод для отключения WebSocket"""
        try:
            user_id = self.websocket_to_user.get(websocket)
            if user_id:
                # Удаляем из всех словарей
                self.active_connections.pop(user_id, None)
                self.connection_info.pop(user_id, None)
                self.websocket_to_user.pop(websocket, None)
                
                logger.info(f"User {user_id} disconnected from WebSocket")
            
            # Закрываем соединение если оно еще открыто
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.close()
                
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def send_to_user(self, user_id: str, message: Dict) -> bool:
        """
        Отправить сообщение конкретному пользователю
        
        Args:
            user_id: ID пользователя
            message: Сообщение для отправки
            
        Returns:
            True если сообщение отправлено, False иначе
        """
        if user_id not in self.active_connections:
            logger.debug(f"User {user_id} is not connected")
            return False
        
        websocket = self.active_connections[user_id]
        return await self._send_to_websocket(websocket, message)
    
    async def send_to_multiple_users(self, user_ids: List[str], message: Dict) -> int:
        """
        Отправить сообщение нескольким пользователям
        
        Args:
            user_ids: Список ID пользователей
            message: Сообщение для отправки
            
        Returns:
            Количество пользователей, которым сообщение было отправлено
        """
        sent_count = 0
        
        # Создаем задачи для параллельной отправки
        tasks = []
        for user_id in user_ids:
            if user_id in self.active_connections:
                websocket = self.active_connections[user_id]
                task = self._send_to_websocket(websocket, message)
                tasks.append((user_id, task))
        
        # Выполняем все задачи параллельно
        if tasks:
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            for (user_id, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"Error sending message to user {user_id}: {result}")
                elif result:
                    sent_count += 1
        
        logger.info(f"Message sent to {sent_count}/{len(user_ids)} users")
        return sent_count
    
    async def _send_to_websocket(self, websocket: WebSocket, message: Dict) -> bool:
        """
        Отправить сообщение через WebSocket
        
        Args:
            websocket: WebSocket соединение
            message: Сообщение для отправки
            
        Returns:
            True если сообщение отправлено, False иначе
        """
        try:
            await websocket.send_text(json.dumps(message, default=str))
            return True
        except WebSocketDisconnect:
            # Соединение разорвано, удаляем его
            await self._disconnect_websocket(websocket)
            return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            # При ошибке также удаляем соединение
            await self._disconnect_websocket(websocket)
            return False
    
    async def send_post_created_notification(self, user_ids: List[str], post_id: str, 
                                           post_text: str, author_user_id: str, 
                                           created_at: datetime) -> int:
        """
        Отправить уведомление о создании поста
        
        Args:
            user_ids: Список ID пользователей для уведомления
            post_id: ID поста
            post_text: Текст поста
            author_user_id: ID автора поста
            created_at: Время создания поста
            
        Returns:
            Количество пользователей, которым отправлено уведомление
        """
        event = PostCreatedEvent(
            post_id=post_id,
            post_text=post_text,
            author_user_id=author_user_id,
            created_at=created_at
        )
        
        message = PostCreatedWebSocketMessage(data=event)
        return await self.send_to_multiple_users(user_ids, message.model_dump())
    
    async def send_error_to_user(self, user_id: str, error_message: str) -> bool:
        """
        Отправить сообщение об ошибке пользователю
        
        Args:
            user_id: ID пользователя
            error_message: Текст ошибки
            
        Returns:
            True если сообщение отправлено, False иначе
        """
        error_msg = ErrorMessage(data={"error": error_message})
        return await self.send_to_user(user_id, error_msg.model_dump())
    
    def get_connected_users(self) -> Set[str]:
        """Получить множество ID подключенных пользователей"""
        return set(self.active_connections.keys())
    
    def get_connection_count(self) -> int:
        """Получить количество активных соединений"""
        return len(self.active_connections)
    
    def is_user_connected(self, user_id: str) -> bool:
        """Проверить, подключен ли пользователь"""
        return user_id in self.active_connections
    
    async def ping_user(self, user_id: str) -> bool:
        """
        Отправить ping пользователю
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если ping отправлен, False иначе
        """
        ping_message = WebSocketMessage(
            type=WebSocketMessageType.PING,
            data={"timestamp": datetime.now().isoformat()}
        )
        
        success = await self.send_to_user(user_id, ping_message.model_dump())
        
        if success and user_id in self.connection_info:
            self.connection_info[user_id].last_ping = datetime.now()
        
        return success
    
    async def handle_pong(self, user_id: str):
        """
        Обработать pong от пользователя
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self.connection_info:
            self.connection_info[user_id].last_ping = datetime.now()
            logger.debug(f"Received pong from user {user_id}")
    
    async def connect_user(self, user_id: str, websocket: WebSocket) -> bool:
        """
        Подключить пользователя к WebSocket (алиас для connect)
        
        Args:
            user_id: ID пользователя
            websocket: WebSocket соединение
            
        Returns:
            True если подключение успешно, False иначе
        """
        return await self.connect(websocket, user_id)
    
    async def disconnect_user(self, user_id: str):
        """
        Отключить пользователя от WebSocket (алиас для disconnect)
        
        Args:
            user_id: ID пользователя
        """
        await self.disconnect(user_id)
    
    async def disconnect_all(self):
        """Отключить всех пользователей"""
        try:
            # Получаем копию списка пользователей
            user_ids = list(self.active_connections.keys())
            
            logger.info(f"Disconnecting {len(user_ids)} users")
            
            # Отключаем всех пользователей
            for user_id in user_ids:
                try:
                    await self.disconnect(user_id)
                except Exception as e:
                    logger.error(f"Error disconnecting user {user_id}: {e}")
            
            logger.info("All users disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting all users: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику WebSocket соединений"""
        return {
            "total_connections": len(self.active_connections),
            "active_users": len(self.connection_info),
            "connections_per_user": {
                user_id: 1 for user_id in self.active_connections.keys()
            }
        }


# Глобальный экземпляр менеджера
websocket_manager = WebSocketManager() 