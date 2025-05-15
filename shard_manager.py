import hashlib
import bisect
from typing import Dict, List, Tuple, Optional, Any
import logging
import json
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConsistentHash:
    """Реализация консистентного хеширования для распределения данных между шардами"""
    
    def __init__(self, nodes: List[str] = None, replicas: int = 100):
        """
        Инициализирует консистентное хеширование
        
        Args:
            nodes: Список узлов (шардов)
            replicas: Количество виртуальных узлов для каждого реального узла
        """
        self.replicas = replicas
        self.ring = {}
        self._sorted_keys = []
        
        if nodes:
            for node in nodes:
                self.add_node(node)
    
    def add_node(self, node: str) -> None:
        """
        Добавляет новый узел в хеш-кольцо
        
        Args:
            node: Идентификатор узла
        """
        for i in range(self.replicas):
            key = self._hash_key(f"{node}:{i}")
            self.ring[key] = node
            bisect.insort(self._sorted_keys, key)
        
        logger.info(f"Node {node} added to the consistent hash ring")
    
    def remove_node(self, node: str) -> None:
        """
        Удаляет узел из хеш-кольца
        
        Args:
            node: Идентификатор узла
        """
        for i in range(self.replicas):
            key = self._hash_key(f"{node}:{i}")
            if key in self.ring:
                self.ring.pop(key)
                self._sorted_keys.remove(key)
        
        logger.info(f"Node {node} removed from the consistent hash ring")
    
    def get_node(self, key: str) -> str:
        """
        Получает узел для заданного ключа
        
        Args:
            key: Ключ для поиска узла
            
        Returns:
            Идентификатор узла
        """
        if not self.ring:
            raise Exception("Hash ring is empty")
        
        hash_key = self._hash_key(key)
        
        # Если хеш больше самого большого ключа, возвращаем первый узел
        if hash_key > self._sorted_keys[-1]:
            return self.ring[self._sorted_keys[0]]
        
        # Находим ближайший больший или равный ключ
        idx = bisect.bisect_left(self._sorted_keys, hash_key)
        if idx == len(self._sorted_keys):
            idx = 0
        
        return self.ring[self._sorted_keys[idx]]
    
    def _hash_key(self, key: str) -> int:
        """
        Хеширует ключ
        
        Args:
            key: Ключ для хеширования
            
        Returns:
            Целочисленное значение хеша
        """
        m = hashlib.md5()
        m.update(key.encode('utf-8'))
        return int(m.hexdigest(), 16)
    
    def get_nodes(self) -> List[str]:
        """
        Возвращает список уникальных узлов
        
        Returns:
            Список узлов
        """
        return list(set(self.ring.values()))


class ShardManager:
    """Менеджер шардов для управления подключениями к разным шардам базы данных"""
    
    _instance = None
    
    def __new__(cls):
        """Реализация синглтона для менеджера шардов"""
        if cls._instance is None:
            cls._instance = super(ShardManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Инициализация менеджера шардов"""
        if self._initialized:
            return
            
        # Загружаем конфигурацию шардов
        self._load_config()
        
        # Создаем хеш-кольцо
        self.hash_ring = ConsistentHash(self.shard_nodes)
        
        # Создаем пулы соединений для каждого шарда
        self._create_connection_pools()
        
        self._initialized = True
        logger.info("Shard manager initialized")
    
    def _load_config(self) -> None:
        """Загружает конфигурацию шардов из переменных окружения или файла"""
        # Параметры шардов из переменных окружения
        shard_hosts = os.getenv("SHARD_HOSTS", "localhost:5432").split(",")
        self.shard_nodes = [f"shard{i}" for i in range(len(shard_hosts))]
        self.shard_configs = {}
        
        for i, host in enumerate(shard_hosts):
            host_parts = host.split(":")
            host = host_parts[0]
            port = int(host_parts[1]) if len(host_parts) > 1 else 5432
            
            shard_name = f"shard{i}"
            self.shard_configs[shard_name] = {
                "host": host,
                "port": port,
                "db_name": os.getenv(f"SHARD{i}_DB_NAME", "social_network"),
                "user": os.getenv(f"SHARD{i}_DB_USER", os.getenv("DB_USER", "postgres")),
                "password": os.getenv(f"SHARD{i}_DB_PASSWORD", os.getenv("DB_PASSWORD", "postgres"))
            }
        
        # Сохраняем мастер-базу для хранения не шардированных данных
        self.master_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "db_name": os.getenv("DB_NAME", "social_network"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres")
        }
        
        # Конфигурация для чтения
        self.slave_configs = []
        slave_hosts = os.getenv("DB_SLAVE_HOSTS", "").split(",")
        for i, host in enumerate(slave_hosts):
            if not host:
                continue
                
            host_parts = host.split(":")
            host = host_parts[0]
            port = int(host_parts[1]) if len(host_parts) > 1 else 5432
            
            self.slave_configs.append({
                "host": host,
                "port": port,
                "db_name": os.getenv("DB_NAME", "social_network"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "postgres")
            })
    
    def _create_connection_pools(self) -> None:
        """Создает пулы соединений для шардов и мастер-базы"""
        self.engines = {}
        self.session_factories = {}
        
        # Создаем подключения к мастер-базе
        master_url = f"postgresql+asyncpg://{self.master_config['user']}:{self.master_config['password']}@{self.master_config['host']}:{self.master_config['port']}/{self.master_config['db_name']}"
        master_engine = create_async_engine(master_url, echo=False)
        self.engines["master"] = master_engine
        self.session_factories["master"] = sessionmaker(master_engine, class_=AsyncSession, expire_on_commit=False)
        
        # Создаем подключения к шардам
        for shard_name, config in self.shard_configs.items():
            shard_url = f"postgresql+asyncpg://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['db_name']}"
            shard_engine = create_async_engine(shard_url, echo=False)
            self.engines[shard_name] = shard_engine
            self.session_factories[shard_name] = sessionmaker(shard_engine, class_=AsyncSession, expire_on_commit=False)
        
        # Создаем подключения к слейвам
        self.slave_engines = []
        self.slave_session_factories = []
        
        for config in self.slave_configs:
            slave_url = f"postgresql+asyncpg://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['db_name']}"
            slave_engine = create_async_engine(slave_url, echo=False)
            self.slave_engines.append(slave_engine)
            self.slave_session_factories.append(
                sessionmaker(slave_engine, class_=AsyncSession, expire_on_commit=False)
            )
    
    def get_shard_for_user(self, user_id: str) -> str:
        """
        Определяет шард для пользователя
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            Имя шарда
        """
        return self.hash_ring.get_node(user_id)
    
    def get_shard_session(self, user_id: str) -> AsyncSession:
        """
        Возвращает сессию для шарда, соответствующего пользователю
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            Асинхронная сессия SQLAlchemy
        """
        shard_name = self.get_shard_for_user(user_id)
        return self.session_factories[shard_name]()
    
    def get_master_session(self) -> AsyncSession:
        """
        Возвращает сессию для мастер-базы
        
        Returns:
            Асинхронная сессия SQLAlchemy
        """
        return self.session_factories["master"]()
    
    def get_slave_session(self) -> AsyncSession:
        """
        Возвращает сессию для одной из slave-баз (балансировка нагрузки)
        
        Returns:
            Асинхронная сессия SQLAlchemy
        """
        if not self.slave_session_factories:
            # Если слейвов нет, используем мастер
            return self.get_master_session()
        
        # Простая round-robin балансировка
        import random
        idx = random.randint(0, len(self.slave_session_factories) - 1)
        return self.slave_session_factories[idx]()
    
    async def add_shard(self, shard_name: str, config: Dict[str, Any]) -> bool:
        """
        Добавляет новый шард
        
        Args:
            shard_name: Имя шарда
            config: Конфигурация шарда
            
        Returns:
            True если шард успешно добавлен
        """
        if shard_name in self.shard_configs:
            logger.warning(f"Shard {shard_name} already exists")
            return False
        
        try:
            # Добавляем конфигурацию
            self.shard_configs[shard_name] = config
            
            # Создаем подключение
            shard_url = f"postgresql+asyncpg://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['db_name']}"
            shard_engine = create_async_engine(shard_url, echo=False)
            self.engines[shard_name] = shard_engine
            self.session_factories[shard_name] = sessionmaker(shard_engine, class_=AsyncSession, expire_on_commit=False)
            
            # Добавляем в хеш-кольцо
            self.hash_ring.add_node(shard_name)
            
            logger.info(f"Shard {shard_name} added successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to add shard {shard_name}: {e}")
            return False
    
    async def remove_shard(self, shard_name: str) -> bool:
        """
        Удаляет шард
        
        Args:
            shard_name: Имя шарда
            
        Returns:
            True если шард успешно удален
        """
        if shard_name not in self.shard_configs:
            logger.warning(f"Shard {shard_name} does not exist")
            return False
        
        try:
            # Удаляем из хеш-кольца
            self.hash_ring.remove_node(shard_name)
            
            # Закрываем соединения
            engine = self.engines.pop(shard_name)
            await engine.dispose()
            
            # Удаляем фабрику сессий
            self.session_factories.pop(shard_name)
            
            # Удаляем конфигурацию
            self.shard_configs.pop(shard_name)
            
            logger.info(f"Shard {shard_name} removed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to remove shard {shard_name}: {e}")
            return False
    
    async def rebalance_shards(self) -> Dict[str, int]:
        """
        Перебалансирует данные между шардами
        
        Returns:
            Словарь с количеством перемещенных данных для каждого шарда
        """
        # Здесь будет реализована логика перебалансировки
        # TODO: Реализовать перебалансировку при решардинге
        return {}
    
    async def close(self) -> None:
        """Закрывает все соединения с базами данных"""
        for engine in self.engines.values():
            await engine.dispose()
        
        for engine in self.slave_engines:
            await engine.dispose()
        
        logger.info("All database connections closed")

# Создаем глобальный экземпляр менеджера шардов
shard_manager = ShardManager() 