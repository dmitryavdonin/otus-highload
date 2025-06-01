#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import traceback
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from enum import Enum


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Настройки сервера
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False
    
    # Настройки базы данных
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/social_network"
    DATABASE_SLAVE_URL: Optional[str] = None
    
    # Настройки Redis
    REDIS_URL: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    
    # Настройки RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "social_network"
    RABBITMQ_QUEUE_FEED_UPDATES: str = "feed_updates"
    
    # Настройки WebSocket
    WS_MAX_CONNECTIONS_PER_USER: int = 3
    WS_HEARTBEAT_INTERVAL: int = 30  # секунды
    WS_CONNECTION_TIMEOUT: int = 300  # секунды
    
    # Настройки обработчика знаменитостей
    CELEBRITY_THRESHOLD: int = 1000  # количество друзей для статуса знаменитости
    CELEBRITY_BATCH_SIZE: int = 100  # размер батча для обработки
    CELEBRITY_BATCH_DELAY: float = 0.1  # задержка между батчами в секундах
    
    # Настройки безопасности
    JWT_SECRET_KEY: str = "your-secret-key-here"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Настройки CORS
    CORS_ORIGINS: list = ["*"]  # В продакшене указать конкретные домены
    
    # Настройки мониторинга
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8002
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"  # Разрешаем дополнительные поля
    }


class DialogBackend(Enum):
    """Типы бэкендов для диалогов"""
    POSTGRESQL = "postgresql"
    REDIS = "redis"


class Config:
    """Конфигурация приложения"""
    
    def __init__(self):
        print(f"🔍 ОТЛАДКА: Инициализация Config")
        print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
        
        # Настройки диалогов
        dialog_backend_env = os.getenv("DIALOG_BACKEND", "postgresql")
        print(f"🔍 DIALOG_BACKEND из env: {dialog_backend_env}")
        self.DIALOG_BACKEND = DialogBackend(dialog_backend_env)
        
        # PostgreSQL настройки
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
        self.POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
        self.POSTGRES_DB = os.getenv("POSTGRES_DB", "social_network")
        self.POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
        
        # Redis настройки - используем переменные окружения из Docker Compose
        redis_host_env = os.getenv("REDIS_HOST", "localhost")
        redis_port_env = os.getenv("REDIS_PORT", "6379")
        redis_db_env = os.getenv("REDIS_DB", "0")
        
        print(f"🔍 REDIS_HOST из env: {redis_host_env}")
        print(f"🔍 REDIS_PORT из env: {redis_port_env}")
        print(f"🔍 REDIS_DB из env: {redis_db_env}")
        
        self.REDIS_HOST = redis_host_env
        self.REDIS_PORT = int(redis_port_env)
        self.REDIS_DB = int(redis_db_env)
        
        # Настройки диалогов
        self.DIALOG_MESSAGES_LIMIT = int(os.getenv("DIALOG_MESSAGES_LIMIT", "100"))
        self.DIALOG_TTL_DAYS = int(os.getenv("DIALOG_TTL_DAYS", "30"))
        
        print(f"🔍 Итоговые значения Config:")
        print(f"🔍 self.REDIS_HOST = {self.REDIS_HOST}")
        print(f"🔍 self.REDIS_PORT = {self.REDIS_PORT}")
        print(f"🔍 self.REDIS_DB = {self.REDIS_DB}")
    
    def get_redis_url(self) -> str:
        """Получение URL для подключения к Redis"""
        print(f"🔍 ОТЛАДКА: get_redis_url() вызван")
        print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
        
        # Приоритет: переменная окружения REDIS_URL, затем составляем из компонентов
        redis_url = os.getenv("REDIS_URL")
        print(f"🔍 REDIS_URL из env: {redis_url}")
        
        if redis_url:
            print(f"🔍 Возвращаем REDIS_URL из env: {redis_url}")
            return redis_url
        
        # Используем уже загруженные переменные экземпляра
        result_url = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        print(f"🔍 Составляем URL из компонентов: {result_url}")
        print(f"🔍 self.REDIS_HOST = {self.REDIS_HOST}")
        print(f"🔍 self.REDIS_PORT = {self.REDIS_PORT}")
        print(f"🔍 self.REDIS_DB = {self.REDIS_DB}")
        
        return result_url
    
    def is_redis_backend(self) -> bool:
        """Проверка, используется ли Redis для диалогов"""
        return self.DIALOG_BACKEND == DialogBackend.REDIS
    
    def is_postgresql_backend(self) -> bool:
        """Проверка, используется ли PostgreSQL для диалогов"""
        return self.DIALOG_BACKEND == DialogBackend.POSTGRESQL


# Глобальный экземпляр настроек
settings = Settings()

# Глобальный экземпляр конфигурации
print(f"🔍 ОТЛАДКА: Создание глобального экземпляра config")
print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
config = Config()


def get_database_url() -> str:
    """Получить URL основной базы данных"""
    return settings.DATABASE_URL


def get_slave_database_url() -> str:
    """Получить URL slave базы данных"""
    return settings.DATABASE_SLAVE_URL or settings.DATABASE_URL


def get_redis_url() -> str:
    """Получить URL Redis"""
    print(f"🔍 ОТЛАДКА: функция get_redis_url() вызвана")
    print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
    return Config().get_redis_url()


def get_rabbitmq_url() -> str:
    """Получить URL RabbitMQ"""
    return settings.RABBITMQ_URL


def is_debug_mode() -> bool:
    """Проверить, включен ли режим отладки"""
    return settings.DEBUG


def get_celebrity_settings() -> dict:
    """Получить настройки обработчика знаменитостей"""
    return {
        "threshold": settings.CELEBRITY_THRESHOLD,
        "batch_size": settings.CELEBRITY_BATCH_SIZE,
        "batch_delay": settings.CELEBRITY_BATCH_DELAY
    }


def get_websocket_settings() -> dict:
    """Получить настройки WebSocket"""
    return {
        "max_connections_per_user": settings.WS_MAX_CONNECTIONS_PER_USER,
        "heartbeat_interval": settings.WS_HEARTBEAT_INTERVAL,
        "connection_timeout": settings.WS_CONNECTION_TIMEOUT
    }


def get_jwt_settings() -> dict:
    """Получить настройки JWT"""
    return {
        "secret_key": settings.JWT_SECRET_KEY,
        "algorithm": settings.JWT_ALGORITHM,
        "expire_minutes": settings.JWT_EXPIRE_MINUTES
    } 