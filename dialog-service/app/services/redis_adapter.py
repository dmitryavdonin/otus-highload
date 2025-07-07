import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
import redis.asyncio as redis
import os

from ..models.dialog import DialogMessageResponse

logger = logging.getLogger(__name__)

# Путь к Lua-скрипту
LUA_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'lua', 'dialog.lua')


class RedisDialogAdapter:
    """
    Адаптер для работы с диалогами через Redis с использованием UDF (Lua).
    """
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.dialog_script_sha = None
        logger.info(f"RedisDialogAdapter initialized with URL: {redis_url}")
    
    async def _load_lua_script(self):
        """Загрузка Lua-скрипта в Redis и кеширование его SHA-хэша."""
        if self.dialog_script_sha:
            return
        
        try:
            with open(LUA_SCRIPT_PATH, 'r') as f:
                script = f.read()
            self.dialog_script_sha = await self.redis_client.script_load(script)
            logger.info(f"Lua script '{LUA_SCRIPT_PATH}' loaded with SHA: {self.dialog_script_sha}")
        except FileNotFoundError:
            logger.error(f"Lua script not found at path: {LUA_SCRIPT_PATH}")
            raise
        except Exception as e:
            logger.error(f"Failed to load Lua script: {e}")
            raise

    async def connect(self):
        """Подключение к Redis и загрузка Lua-скрипта."""
        try:
            await self.redis_client.ping()
            logger.info(f"Successfully connected to Redis: {self.redis_url}")
            await self._load_lua_script()
        except Exception as e:
            logger.error(f"Failed to connect to Redis or load Lua script: {e}")
            raise
    
    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    def _get_dialog_key(self, user_id1: str, user_id2: str) -> str:
        """
        Генерация ключа диалога. Всегда в одном порядке для консистентности.
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            Ключ диалога в формате dialog:{smaller_id}:{larger_id}
        """
        ids = sorted([user_id1, user_id2])
        return f"dialog:{ids[0]}:{ids[1]}"
    
    def _message_to_dict(self, message_id: str, from_user_id: str, to_user_id: str, 
                        text: str, created_at: datetime) -> Dict:
        """Преобразование сообщения в словарь для хранения в Redis"""
        return {
            "id": message_id,
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "text": text,
            "created_at": created_at.isoformat()
        }
    
    def _dict_to_message_response(self, message_dict: Dict) -> DialogMessageResponse:
        """Преобразование словаря из Redis в объект ответа"""
        return DialogMessageResponse(
            from_user_id=message_dict["from_user_id"],
            to_user_id=message_dict["to_user_id"],
            text=message_dict["text"],
            created_at=datetime.fromisoformat(message_dict["created_at"])
        )
    
    async def save_dialog_message(self, from_user_id: str, to_user_id: str, text: str) -> str:
        """
        Сохранение сообщения в Redis с использованием Lua-скрипта.
        
        Args:
            from_user_id: ID отправителя
            to_user_id: ID получателя
            text: Текст сообщения
            
        Returns:
            ID созданного сообщения
        """
        message_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        message_data = self._message_to_dict(
            message_id, from_user_id, to_user_id, text, created_at
        )
        
        dialog_key = self._get_dialog_key(from_user_id, to_user_id)
        timestamp_score = created_at.timestamp()
        ttl_seconds = 30 * 24 * 60 * 60  # 30 дней

        try:
            await self.redis_client.evalsha(
                self.dialog_script_sha,
                1,  # Количество ключей
                dialog_key,
                'save_message',  # ARGV[1]: command
                json.dumps(message_data),  # ARGV[2]: message_data
                timestamp_score,  # ARGV[3]: score
                ttl_seconds  # ARGV[4]: ttl
            )
            logger.info(f"Message saved to Redis via Lua with ID: {message_id}")
            return message_id
        except redis.exceptions.NoScriptError:
            logger.warning("Lua script not found in cache, reloading...")
            await self._load_lua_script()
            return await self.save_dialog_message(from_user_id, to_user_id, text)
        except Exception as e:
            logger.error(f"Error saving message via Lua: {e}")
            raise
    
    async def get_dialog_messages(self, user_id1: str, user_id2: str, 
                                 limit: int = 100, offset: int = 0) -> List[DialogMessageResponse]:
        """
        Получение сообщений диалога из Redis с использованием Lua-скрипта.
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            limit: Максимальное количество сообщений
            offset: Смещение для пагинации
            
        Returns:
            Список сообщений диалога
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        
        try:
            messages_data = await self.redis_client.evalsha(
                self.dialog_script_sha,
                1,
                dialog_key,
                'get_messages',  # ARGV[1]: command
                offset,          # ARGV[2]: offset
                limit            # ARGV[3]: limit
            )
        except redis.exceptions.NoScriptError:
            logger.warning("Lua script not found in cache, reloading...")
            await self._load_lua_script()
            return await self.get_dialog_messages(user_id1, user_id2, limit, offset)
        except Exception as e:
            logger.error(f"Error getting messages via Lua: {e}")
            return []

        messages = []
        for message_json in messages_data:
            try:
                message_dict = json.loads(message_json)
                message_response = self._dict_to_message_response(message_dict)
                messages.append(message_response)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing message from Lua response: {e}")
                continue
        
        logger.info(f"Retrieved {len(messages)} messages from Redis via Lua")
        return messages
    
    async def get_recent_dialog_messages(self, user_id1: str, user_id2: str, 
                                       limit: int = 50) -> List[DialogMessageResponse]:
        """
        Получение последних сообщений диалога
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            limit: Количество последних сообщений
            
        Returns:
            Список последних сообщений
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        
        # Получаем последние сообщения (с конца Sorted Set)
        # Lua-скрипт для zrevrange не создавался, используем прямую команду
        messages_data = await self.redis_client.zrange(
            dialog_key, 
            -limit,  # Последние limit элементов
            -1,      # До конца
            desc=True
        )
        
        # Преобразуем в объекты ответа
        messages = []
        for message_json in messages_data:
            try:
                message_dict = json.loads(message_json)
                message_response = self._dict_to_message_response(message_dict)
                messages.append(message_response)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing message: {e}")
                continue
        
        logger.info(f"Retrieved {len(messages)} recent messages from Redis")
        return messages
    
    async def get_dialog_stats(self) -> Dict:
        """
        Получение статистики по диалогам
        
        Returns:
            Словарь со статистикой
        """
        try:
            # Получаем все ключи диалогов
            dialog_keys = await self.redis_client.keys("dialog:*")
            total_dialogs = len(dialog_keys)
            
            total_messages = 0
            for key in dialog_keys:
                messages_count = await self.redis_client.zcard(key)
                total_messages += messages_count
            
            avg_messages_per_dialog = total_messages / total_dialogs if total_dialogs > 0 else 0
            
            stats = {
                "total_dialogs": total_dialogs,
                "total_messages": total_messages,
                "avg_messages_per_dialog": round(avg_messages_per_dialog, 2)
            }
            
            logger.info(f"Retrieved dialog stats from Redis: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats from Redis: {e}")
            return {
                "total_dialogs": 0,
                "total_messages": 0,
                "avg_messages_per_dialog": 0
            } 