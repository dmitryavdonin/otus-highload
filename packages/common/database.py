from sqlalchemy.ext.declarative import declarative_base
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Create declarative base
Base = declarative_base()

# Database connection parameters
DB_HOST = os.getenv("DB_HOST", "citus-coordinator")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "social_network")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Create async engine for Citus coordinator
# Все запросы теперь идут через координатор, который сам распределяет нагрузку между шардами
citus_engine = create_async_engine(
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    echo=False
)

# Create session factory
citus_session_factory = sessionmaker(citus_engine, class_=AsyncSession, expire_on_commit=False)

# Function to get a database session
def get_db_session():
    return citus_session_factory()

# Для обратной совместимости с существующим кодом
def get_master_session():
    return get_db_session()

def get_slave_session():
    return get_db_session()
