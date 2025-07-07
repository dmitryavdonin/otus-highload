import os
from typing import Optional
from pydantic_settings import BaseSettings


class DialogServiceSettings(BaseSettings):
    """Настройки сервиса диалогов"""
    
    # Настройки сервера
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DEBUG: bool = False
    
    # Настройки базы данных - используем переменную из docker-compose или отдельные параметры
    DATABASE_URL: Optional[str] = None
    DB_HOST: str = "postgres"  # изменено с localhost на postgres
    DB_PORT: int = 5432
    DB_NAME: str = "social_network"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    
    # Настройки Redis - используем переменную из docker-compose или отдельные параметры
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "redis"  # изменено с localhost на redis
    REDIS_PORT: int = 6379
    REDIS_DB: int = 1  # изменено с 0 на 1 для dialog service
    REDIS_PASSWORD: Optional[str] = None
    
    # Настройки диалогов
    DIALOG_MESSAGES_LIMIT: int = 100
    DIALOG_TTL_DAYS: int = 30
    DIALOG_BACKEND: str = "redis"  # изменено с postgresql на redis
    
    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"
    }
    
    @property
    def database_url(self) -> str:
        """Получить URL для подключения к базе данных"""
        # Если DATABASE_URL задан в окружении, используем его
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def redis_url(self) -> str:
        """Получить URL для подключения к Redis"""
        # Если REDIS_URL задан в окружении, используем его
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    def is_redis_backend(self) -> bool:
        """Проверка, используется ли Redis для диалогов"""
        return self.DIALOG_BACKEND == "redis"


# Глобальный экземпляр настроек
settings = DialogServiceSettings() 