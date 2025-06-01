#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List
from models import DialogMessageResponse


class DialogService:
    """
    Универсальный сервис для работы с диалогами.
    Автоматически выбирает между PostgreSQL и Redis в зависимости от конфигурации.
    """
    
    def __init__(self):
        self._postgresql_adapter = None
        self._redis_adapter = None
    
    async def init(self):
        """Инициализация сервиса диалогов"""
        # Создаем новый экземпляр Config во время выполнения
        from config import Config
        config = Config()
        
        if config.is_redis_backend():
            from redis_adapter import init_redis_adapter
            redis_url = config.get_redis_url()
            print(f"🔍 Отладка dialog_service: config.get_redis_url() = {redis_url}")
            await init_redis_adapter(redis_url)
            print(f"🔴 Диалоги: используется Redis ({redis_url})")
        else:
            print("🐘 Диалоги: используется PostgreSQL")
    
    async def close(self):
        """Закрытие соединений"""
        from config import Config
        config = Config()
        if config.is_redis_backend():
            from redis_adapter import close_redis_adapter
            await close_redis_adapter()
    
    async def save_dialog_message(self, from_user_id: str, to_user_id: str, text: str) -> str:
        """
        Сохранение сообщения диалога
        
        Args:
            from_user_id: ID отправителя
            to_user_id: ID получателя
            text: Текст сообщения
            
        Returns:
            ID созданного сообщения
        """
        from config import Config
        config = Config()
        if config.is_redis_backend():
            from redis_adapter import redis_dialog_adapter
            return await redis_dialog_adapter.save_dialog_message(from_user_id, to_user_id, text)
        else:
            from db import save_dialog_message
            return await save_dialog_message(from_user_id, to_user_id, text)
    
    async def get_dialog_messages(self, user_id1: str, user_id2: str) -> List[DialogMessageResponse]:
        """
        Получение сообщений диалога
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            Список сообщений диалога
        """
        from config import Config
        config = Config()
        if config.is_redis_backend():
            from redis_adapter import redis_dialog_adapter
            return await redis_dialog_adapter.get_dialog_messages(
                user_id1, user_id2, limit=config.DIALOG_MESSAGES_LIMIT
            )
        else:
            from db import get_dialog_messages
            from models import DialogMessageResponse
            
            # Получаем сообщения из PostgreSQL
            messages = await get_dialog_messages(user_id1, user_id2)
            
            # Преобразуем в формат ответа API
            response_messages = []
            for msg in messages:
                response_messages.append(
                    DialogMessageResponse(
                        from_user_id=str(msg.from_user_id),
                        to_user_id=str(msg.to_user_id),
                        text=msg.text,
                        created_at=msg.created_at
                    )
                )
            
            # Ограничиваем количество сообщений
            return response_messages[-config.DIALOG_MESSAGES_LIMIT:]
    
    async def get_dialog_stats(self) -> dict:
        """
        Получение статистики по диалогам
        
        Returns:
            Словарь со статистикой
        """
        from config import Config
        config = Config()
        if config.is_redis_backend():
            from redis_adapter import redis_dialog_adapter
            stats = await redis_dialog_adapter.get_dialog_stats()
            stats["backend"] = "Redis"
            return stats
        else:
            # Для PostgreSQL можно добавить аналогичную статистику
            return {
                "backend": "PostgreSQL",
                "total_dialogs": "N/A",
                "total_messages": "N/A",
                "avg_messages_per_dialog": "N/A"
            }


# Глобальный экземпляр сервиса диалогов
dialog_service = DialogService() 