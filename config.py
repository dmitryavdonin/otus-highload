import os
from typing import Optional
from pydantic import BaseSettings


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
    REDIS_URL: str = "redis://localhost:6379/0"
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Глобальный экземпляр настроек
settings = Settings()


def get_database_url() -> str:
    """Получить URL основной базы данных"""
    return settings.DATABASE_URL


def get_slave_database_url() -> str:
    """Получить URL slave базы данных"""
    return settings.DATABASE_SLAVE_URL or settings.DATABASE_URL


def get_redis_url() -> str:
    """Получить URL Redis"""
    return settings.REDIS_URL


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