#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import traceback
import uuid
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import redis.asyncio as redis
from models import DialogMessage, DialogMessageResponse


class RedisDialogAdapter:
    """
    Адаптер для работы с диалогами через Redis
    """
    
    def __init__(self, redis_url: str):
        print(f"🔍 ОТЛАДКА: RedisDialogAdapter.__init__ вызван с redis_url={redis_url}")
        print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
        
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        
        print(f"🔍 RedisDialogAdapter инициализирован с URL: {redis_url}")
        print(f"🔍 Отладка: redis_dialog_adapter.redis_url = {self.redis_url}")
    
    async def connect(self):
        """Подключение к Redis"""
        print(f"🔍 ОТЛАДКА: RedisDialogAdapter.connect() вызван")
        print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
        print(f"🔍 Подключение к Redis: {self.redis_url}")
        
        try:
            await self.redis_client.ping()
            print(f"✅ Успешное подключение к Redis: {self.redis_url}")
        except Exception as e:
            print(f"❌ Ошибка подключения к Redis: {e}")
            raise
    
    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis_client:
            await self.redis_client.close()
    
    def _get_dialog_key(self, user_id1: str, user_id2: str) -> str:
        """
        Генерация ключа диалога. Всегда в одном порядке для консистентности.
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            Ключ диалога в формате dialog:{smaller_id}:{larger_id}
        """
        # Сортируем ID для консистентности ключей
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
        Сохранение сообщения в Redis
        
        Args:
            from_user_id: ID отправителя
            to_user_id: ID получателя
            text: Текст сообщения
            
        Returns:
            ID созданного сообщения
        """
        message_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        # Создаем объект сообщения
        message_data = self._message_to_dict(
            message_id, from_user_id, to_user_id, text, created_at
        )
        
        # Получаем ключ диалога
        dialog_key = self._get_dialog_key(from_user_id, to_user_id)
        
        # Используем timestamp как score для автоматической сортировки
        timestamp_score = created_at.timestamp()
        
        # Сохраняем в Sorted Set
        await self.redis_client.zadd(
            dialog_key, 
            {json.dumps(message_data): timestamp_score}
        )
        
        # Устанавливаем TTL для диалога (опционально, например 30 дней)
        await self.redis_client.expire(dialog_key, 30 * 24 * 60 * 60)
        
        return message_id
    
    async def get_dialog_messages(self, user_id1: str, user_id2: str, 
                                 limit: int = 100, offset: int = 0) -> List[DialogMessageResponse]:
        """
        Получение сообщений диалога из Redis
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            limit: Максимальное количество сообщений
            offset: Смещение для пагинации
            
        Returns:
            Список сообщений диалога
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        
        # Получаем сообщения из Sorted Set (уже отсортированы по времени)
        # ZRANGE возвращает элементы в порядке возрастания score (времени)
        messages_data = await self.redis_client.zrange(
            dialog_key, 
            offset, 
            offset + limit - 1
        )
        
        # Преобразуем JSON-строки обратно в объекты
        messages = []
        for message_json in messages_data:
            try:
                message_dict = json.loads(message_json)
                message_response = self._dict_to_message_response(message_dict)
                messages.append(message_response)
            except (json.JSONDecodeError, KeyError) as e:
                # Логируем ошибку, но продолжаем обработку
                print(f"Ошибка парсинга сообщения: {e}")
                continue
        
        return messages
    
    async def get_dialog_messages_count(self, user_id1: str, user_id2: str) -> int:
        """
        Получение количества сообщений в диалоге
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            Количество сообщений в диалоге
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        return await self.redis_client.zcard(dialog_key)
    
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
        messages_data = await self.redis_client.zrange(
            dialog_key, 
            -limit,  # Последние limit элементов
            -1       # До конца
        )
        
        # Преобразуем в объекты ответа
        messages = []
        for message_json in messages_data:
            try:
                message_dict = json.loads(message_json)
                message_response = self._dict_to_message_response(message_dict)
                messages.append(message_response)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Ошибка парсинга сообщения: {e}")
                continue
        
        return messages
    
    async def delete_dialog(self, user_id1: str, user_id2: str) -> bool:
        """
        Удаление всего диалога
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            True если диалог был удален, False если диалога не было
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        deleted_count = await self.redis_client.delete(dialog_key)
        return deleted_count > 0
    
    async def get_dialog_stats(self) -> Dict:
        """
        Получение статистики по диалогам в Redis
        
        Returns:
            Словарь со статистикой
        """
        # Получаем все ключи диалогов
        dialog_keys = await self.redis_client.keys("dialog:*")
        
        total_dialogs = len(dialog_keys)
        total_messages = 0
        
        # Подсчитываем общее количество сообщений
        for key in dialog_keys:
            count = await self.redis_client.zcard(key)
            total_messages += count
        
        return {
            "total_dialogs": total_dialogs,
            "total_messages": total_messages,
            "avg_messages_per_dialog": total_messages / total_dialogs if total_dialogs > 0 else 0
        }


# Глобальный экземпляр адаптера
redis_dialog_adapter = None


async def init_redis_adapter(redis_url: str):
    """Инициализация Redis-адаптера"""
    print(f"🔍 ОТЛАДКА: init_redis_adapter() вызван с redis_url={redis_url}")
    print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
    
    global redis_dialog_adapter
    print(f"🔧 Инициализация Redis адаптера с URL: {redis_url}")
    print(f"🔍 Отладка: переданный redis_url = {redis_url}")
    
    redis_dialog_adapter = RedisDialogAdapter(redis_url)
    await redis_dialog_adapter.connect()
    print(f"✅ Redis адаптер инициализирован с URL: {redis_url}")


async def close_redis_adapter():
    """Закрытие соединения с Redis"""
    global redis_dialog_adapter
    if redis_dialog_adapter:
        await redis_dialog_adapter.disconnect() 