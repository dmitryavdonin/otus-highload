#!/usr/bin/env python3
"""
Тестовый WebSocket клиент для проверки работы сервера real-time обновлений
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Optional
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebSocketTestClient:
    """Тестовый WebSocket клиент"""
    
    def __init__(self, server_url: str = "ws://localhost:8001", user_id: str = "test_user"):
        self.server_url = server_url
        self.user_id = user_id
        self.token = f"{user_id}:test_signature"  # Простой тестовый токен
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.running = False
    
    async def connect(self):
        """Подключиться к WebSocket серверу"""
        try:
            uri = f"{self.server_url}/ws/{self.user_id}?token={self.token}"
            logger.info(f"Connecting to {uri}")
            
            self.websocket = await websockets.connect(uri)
            self.running = True
            
            logger.info(f"Connected as user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Отключиться от сервера"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from server")
    
    async def send_message(self, message_type: str, data: dict = None):
        """Отправить сообщение серверу"""
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        message = {
            "type": message_type,
            "data": data or {}
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent: {message}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def listen_for_messages(self):
        """Слушать сообщения от сервера"""
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        try:
            while self.running:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                # Обработка разных типов сообщений
                msg_type = data.get("type", "unknown")
                msg_data = data.get("data", {})
                
                if msg_type == "system":
                    logger.info(f"System message: {msg_data.get('message')}")
                elif msg_type == "post_created":
                    logger.info(
                        f"New post from {msg_data.get('author_user_id')}: "
                        f"{msg_data.get('post_text')}"
                    )
                else:
                    logger.info(f"Received {msg_type}: {msg_data}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
        except Exception as e:
            logger.error(f"Error listening for messages: {e}")
    
    async def send_ping(self):
        """Отправить ping серверу"""
        await self.send_message("ping")
    
    async def request_stats(self):
        """Запросить статистику сервера"""
        await self.send_message("get_stats")
    
    async def subscribe_to_feed(self):
        """Подписаться на обновления ленты"""
        await self.send_message("subscribe_feed")
    
    async def run_interactive_mode(self):
        """Запустить интерактивный режим"""
        if not await self.connect():
            return
        
        # Запускаем прослушивание сообщений в фоне
        listen_task = asyncio.create_task(self.listen_for_messages())
        
        logger.info("Interactive mode started. Available commands:")
        logger.info("  ping - Send ping to server")
        logger.info("  stats - Request server statistics")
        logger.info("  subscribe - Subscribe to feed updates")
        logger.info("  quit - Exit")
        
        try:
            while self.running:
                try:
                    # Читаем команды от пользователя
                    command = await asyncio.get_event_loop().run_in_executor(
                        None, input, "Enter command: "
                    )
                    
                    command = command.strip().lower()
                    
                    if command == "ping":
                        await self.send_ping()
                    elif command == "stats":
                        await self.request_stats()
                    elif command == "subscribe":
                        await self.subscribe_to_feed()
                    elif command == "quit":
                        break
                    else:
                        logger.info(f"Unknown command: {command}")
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Error in interactive mode: {e}")
                    
        finally:
            await self.disconnect()
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
    
    async def run_auto_mode(self, duration: int = 60):
        """Запустить автоматический режим тестирования"""
        if not await self.connect():
            return
        
        # Запускаем прослушивание сообщений
        listen_task = asyncio.create_task(self.listen_for_messages())
        
        logger.info(f"Auto mode started for {duration} seconds")
        
        try:
            # Отправляем тестовые сообщения с интервалами
            for i in range(duration // 10):
                await asyncio.sleep(10)
                
                if i % 3 == 0:
                    await self.send_ping()
                elif i % 3 == 1:
                    await self.request_stats()
                else:
                    await self.subscribe_to_feed()
                    
        except KeyboardInterrupt:
            logger.info("Auto mode interrupted")
        finally:
            await self.disconnect()
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass


async def test_multiple_clients(num_clients: int = 5, duration: int = 30):
    """Тестирование с несколькими клиентами"""
    logger.info(f"Starting {num_clients} test clients for {duration} seconds")
    
    clients = []
    tasks = []
    
    try:
        # Создаем и подключаем клиентов
        for i in range(num_clients):
            client = WebSocketTestClient(user_id=f"test_user_{i}")
            clients.append(client)
            
            if await client.connect():
                # Запускаем прослушивание для каждого клиента
                task = asyncio.create_task(client.listen_for_messages())
                tasks.append(task)
        
        logger.info(f"Connected {len(clients)} clients")
        
        # Отправляем тестовые сообщения
        for i in range(duration // 5):
            await asyncio.sleep(5)
            
            # Случайный клиент отправляет ping
            if clients:
                client = clients[i % len(clients)]
                await client.send_ping()
                
        await asyncio.sleep(5)
        
    finally:
        # Отключаем всех клиентов
        for client in clients:
            await client.disconnect()
        
        # Отменяем все задачи
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info("All clients disconnected")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="WebSocket Test Client")
    parser.add_argument("--server", default="ws://localhost:8001", 
                       help="WebSocket server URL")
    parser.add_argument("--user-id", default="test_user", 
                       help="User ID for connection")
    parser.add_argument("--mode", choices=["interactive", "auto", "multi"], 
                       default="interactive", help="Test mode")
    parser.add_argument("--duration", type=int, default=60, 
                       help="Duration for auto/multi mode (seconds)")
    parser.add_argument("--clients", type=int, default=5, 
                       help="Number of clients for multi mode")
    
    args = parser.parse_args()
    
    if args.mode == "interactive":
        client = WebSocketTestClient(args.server, args.user_id)
        asyncio.run(client.run_interactive_mode())
    elif args.mode == "auto":
        client = WebSocketTestClient(args.server, args.user_id)
        asyncio.run(client.run_auto_mode(args.duration))
    elif args.mode == "multi":
        asyncio.run(test_multiple_clients(args.clients, args.duration))


if __name__ == "__main__":
    main() 