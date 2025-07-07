import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings

logger = logging.getLogger(__name__)

# Создаем движок базы данных
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Создаем фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Контекстный менеджер для получения сессии базы данных
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error: {e}")
            raise
        finally:
            await session.close()


async def init_database():
    """Инициализация подключения к базе данных"""
    try:
        # Проверяем соединение
        async with engine.begin() as conn:
            logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def close_database():
    """Закрытие подключения к базе данных"""
    await engine.dispose()
    logger.info("Database connection closed") 