from sqlalchemy.ext.declarative import declarative_base
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Create declarative base
Base = declarative_base()

def get_database_config():
    """Получение конфигурации базы данных в зависимости от режима работы"""
    use_haproxy = os.getenv("USE_HAPROXY", "false").lower() == "true"
    
    if use_haproxy:
        # Режим с HAProxy
        master_host = os.getenv("DB_MASTER_HOST", "haproxy")
        master_port = os.getenv("DB_MASTER_PORT", "5000")
        slave_host = os.getenv("DB_SLAVE_HOST", "haproxy")
        slave_port = os.getenv("DB_SLAVE_PORT", "5001")
        
        print(f"🔧 Используется HAProxy режим:")
        print(f"🔧 Master: {master_host}:{master_port}")
        print(f"🔧 Slaves: {slave_host}:{slave_port}")
    else:
        # Прямое подключение (обратная совместимость)
        master_host = os.getenv("DB_HOST", "postgres")
        master_port = os.getenv("DB_PORT", "5432")
        slave_host = master_host  # Если HAProxy не используется, слейв = мастер
        slave_port = master_port
        
        print(f"🔧 Используется прямое подключение:")
        print(f"🔧 Database: {master_host}:{master_port}")
    
    return {
        "master_host": master_host,
        "master_port": master_port,
        "slave_host": slave_host,
        "slave_port": slave_port,
        "db_name": os.getenv("DB_NAME", "social_network"),
        "db_user": os.getenv("DB_USER", "postgres"),
        "db_password": os.getenv("DB_PASSWORD", "postgres"),
        "use_haproxy": use_haproxy
    }

# Получаем конфигурацию
config = get_database_config()

# Создаем движки для мастера и слейвов
master_url = f"postgresql+asyncpg://{config['db_user']}:{config['db_password']}@{config['master_host']}:{config['master_port']}/{config['db_name']}"
slave_url = f"postgresql+asyncpg://{config['db_user']}:{config['db_password']}@{config['slave_host']}:{config['slave_port']}/{config['db_name']}"

print(f"🔧 Master URL: {master_url}")
print(f"🔧 Slave URL: {slave_url}")

# Создаем движки
master_engine = create_async_engine(
    master_url, 
    echo=False, 
    pool_size=10, 
    max_overflow=20, 
    pool_recycle=300,  # Более частый recycle для failover (5 минут)
    pool_pre_ping=True,
    pool_timeout=30,
    pool_reset_on_return='rollback',  # Сбрасываем соединения при возврате в pool
    connect_args={
        "server_settings": {"application_name": "social_network_master"},
        "command_timeout": 10  # Таймаут команд для быстрого обнаружения мертвых соединений
    }
)
slave_engine = create_async_engine(
    slave_url, 
    echo=False, 
    pool_size=10, 
    max_overflow=20, 
    pool_recycle=300,  # Более частый recycle для failover (5 минут)
    pool_pre_ping=True,
    pool_timeout=30,
    pool_reset_on_return='rollback',  # Сбрасываем соединения при возврате в pool
    connect_args={
        "server_settings": {"application_name": "social_network_slave"},
        "command_timeout": 10  # Таймаут команд для быстрого обнаружения мертвых соединений
    }
)

# Создаем фабрики сессий
master_session_factory = sessionmaker(master_engine, class_=AsyncSession, expire_on_commit=False)
slave_session_factory = sessionmaker(slave_engine, class_=AsyncSession, expire_on_commit=False)

# Функции для получения сессий
def get_master_session():
    """Получить сессию для записи (мастер)"""
    return master_session_factory()

def get_slave_session():
    """Получить сессию для чтения (слейвы через HAProxy или мастер)"""
    return slave_session_factory()

# Для обратной совместимости
def get_db_session():
    """Получить сессию БД (по умолчанию мастер)"""
    return get_master_session()

# Информация о конфигурации
def get_db_info():
    """Получить информацию о текущей конфигурации БД"""
    return {
        "use_haproxy": config["use_haproxy"],
        "master_host": config["master_host"],
        "master_port": config["master_port"],
        "slave_host": config["slave_host"],
        "slave_port": config["slave_port"],
        "db_name": config["db_name"]
    } 