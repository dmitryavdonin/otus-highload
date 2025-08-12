import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
import uuid
from datetime import datetime

from shard_manager import shard_manager
from database import SHARDED_TABLES, Base
from models import Post, DialogMessage

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Размер батча для переноса данных
BATCH_SIZE = 100

async def get_table_schema(session: AsyncSession, table_name: str) -> str:
    """
    Получает SQL-схему таблицы
    
    Args:
        session: Сессия SQLAlchemy
        table_name: Имя таблицы
        
    Returns:
        SQL-схема таблицы
    """
    query = text("""
    SELECT 
        column_name, 
        data_type, 
        character_maximum_length,
        is_nullable,
        column_default
    FROM 
        information_schema.columns
    WHERE 
        table_name = :table_name
    ORDER BY 
        ordinal_position
    """)
    
    result = await session.execute(query, {"table_name": table_name})
    columns = result.fetchall()
    
    create_table = f"CREATE TABLE IF NOT EXISTS {table_name} ("
    column_defs = []
    
    for column in columns:
        name, data_type, max_length, is_nullable, default = column
        
        column_def = f"{name} {data_type}"
        
        if max_length:
            column_def += f"({max_length})"
        
        if is_nullable == "NO":
            column_def += " NOT NULL"
            
        if default:
            column_def += f" DEFAULT {default}"
            
        column_defs.append(column_def)
    
    # Получаем информацию о первичном ключе
    query = text("""
    SELECT 
        kc.column_name 
    FROM 
        information_schema.table_constraints tc 
        JOIN information_schema.key_column_usage kc 
        ON kc.constraint_name = tc.constraint_name 
    WHERE 
        tc.constraint_type = 'PRIMARY KEY' 
        AND tc.table_name = :table_name
    """)
    
    result = await session.execute(query, {"table_name": table_name})
    primary_keys = [row[0] for row in result.fetchall()]
    
    if primary_keys:
        column_defs.append(f"PRIMARY KEY ({', '.join(primary_keys)})")
    
    create_table += ", ".join(column_defs) + ");"
    
    return create_table

async def ensure_table_exists(session: AsyncSession, table_name: str) -> None:
    """
    Проверяет существование таблицы и создает ее, если она не существует
    
    Args:
        session: Сессия SQLAlchemy
        table_name: Имя таблицы
    """
    # Проверяем существование таблицы
    query = text("""
    SELECT EXISTS (
       SELECT FROM information_schema.tables 
       WHERE table_name = :table_name
    );
    """)
    
    result = await session.execute(query, {"table_name": table_name})
    exists = result.scalar()
    
    if not exists:
        # Получаем схему таблицы с мастера
        async with shard_manager.get_master_session() as master_session:
            schema = await get_table_schema(master_session, table_name)
            
        # Создаем таблицу
        await session.execute(text(schema))
        await session.commit()
        
        logger.info(f"Table {table_name} created")

async def copy_data_between_shards(
    source_shard: str, 
    target_shard: str, 
    table_name: str, 
    user_id: str
) -> int:
    """
    Копирует данные пользователя между шардами
    
    Args:
        source_shard: Исходный шард
        target_shard: Целевой шард
        table_name: Имя таблицы
        user_id: ID пользователя
        
    Returns:
        Количество скопированных строк
    """
    total_rows = 0
    
    # Получаем сессии для исходного и целевого шардов
    async with shard_manager.session_factories[source_shard]() as source_session, \
               shard_manager.session_factories[target_shard]() as target_session:
        
        # Проверяем существование таблицы на целевом шарде
        await ensure_table_exists(target_session, table_name)
        
        # Определяем модель данных в зависимости от таблицы
        if table_name == "posts":
            model_class = Post
            user_field = Post.author_user_id
        elif table_name == "dialog_messages":
            model_class = DialogMessage
            user_field = DialogMessage.from_user_id  # или to_user_id, в зависимости от того, как шардируем
        else:
            raise ValueError(f"Unsupported table for sharding: {table_name}")
        
        # Получаем все данные пользователя с исходного шарда
        offset = 0
        while True:
            # Запрашиваем батч данных
            query = select(model_class).where(user_field == user_id).offset(offset).limit(BATCH_SIZE)
            result = await source_session.execute(query)
            rows = result.scalars().all()
            
            if not rows:
                break
                
            # Копируем данные на целевой шард
            for row in rows:
                # Проверяем, существует ли уже запись на целевом шарде
                check_query = select(model_class).where(model_class.id == row.id)
                check_result = await target_session.execute(check_query)
                existing_row = check_result.scalar_one_or_none()
                
                if existing_row:
                    # Если запись уже существует, пропускаем
                    continue
                
                # Создаем новую запись (клонируем объект)
                new_row = model_class()
                for column in row.__table__.columns:
                    setattr(new_row, column.name, getattr(row, column.name))
                
                target_session.add(new_row)
            
            # Сохраняем изменения
            await target_session.commit()
            
            total_rows += len(rows)
            offset += BATCH_SIZE
            
            logger.info(f"Copied {total_rows} rows from {source_shard} to {target_shard} for user {user_id} in table {table_name}")
    
    return total_rows

async def delete_data_from_shard(
    shard: str, 
    table_name: str, 
    user_id: str
) -> int:
    """
    Удаляет данные пользователя с шарда
    
    Args:
        shard: Имя шарда
        table_name: Имя таблицы
        user_id: ID пользователя
        
    Returns:
        Количество удаленных строк
    """
    # Определяем модель данных в зависимости от таблицы
    if table_name == "posts":
        model_class = Post
        user_field = Post.author_user_id
    elif table_name == "dialog_messages":
        model_class = DialogMessage
        user_field = DialogMessage.from_user_id  # или to_user_id, в зависимости от того, как шардируем
    else:
        raise ValueError(f"Unsupported table for sharding: {table_name}")
    
    # Получаем сессию для шарда
    async with shard_manager.session_factories[shard]() as session:
        # Удаляем данные
        query = model_class.__table__.delete().where(user_field == user_id)
        result = await session.execute(query)
        await session.commit()
        
        return result.rowcount

async def reshard_user(user_id: str) -> Dict[str, Any]:
    """
    Перемещает данные пользователя на правильный шард согласно текущей конфигурации хеширования
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Словарь с результатами решардинга
    """
    # Определяем правильный шард для пользователя
    target_shard = shard_manager.get_shard_for_user(user_id)
    
    # Получаем список всех шардов
    all_shards = shard_manager.hash_ring.get_nodes()
    
    results = {
        "user_id": user_id,
        "target_shard": target_shard,
        "tables": {}
    }
    
    # Для каждой шардированной таблицы
    for table in SHARDED_TABLES:
        results["tables"][table] = {
            "copied": 0,
            "deleted": 0
        }
        
        # Для каждого шарда (кроме целевого)
        for source_shard in all_shards:
            if source_shard == target_shard:
                continue
                
            # Копируем данные с исходного шарда на целевой
            rows_copied = await copy_data_between_shards(source_shard, target_shard, table, user_id)
            results["tables"][table]["copied"] += rows_copied
            
            if rows_copied > 0:
                # Если были скопированные данные, удаляем их с исходного шарда
                rows_deleted = await delete_data_from_shard(source_shard, table, user_id)
                results["tables"][table]["deleted"] += rows_deleted
    
    return results

async def reshard_all_users(batch_size: int = 100) -> Dict[str, Any]:
    """
    Перемещает данные всех пользователей на правильные шарды
    
    Args:
        batch_size: Размер батча пользователей
        
    Returns:
        Словарь со статистикой решардинга
    """
    start_time = datetime.now()
    
    stats = {
        "total_users": 0,
        "processed_users": 0,
        "errors": 0,
        "tables": {table: {"copied": 0, "deleted": 0} for table in SHARDED_TABLES},
        "start_time": start_time.isoformat(),
        "end_time": None,
        "duration_seconds": None
    }
    
    # Получаем все ID пользователей
    async with shard_manager.get_master_session() as session:
        from models import User
        query = select(User.id)
        result = await session.execute(query)
        user_ids = [str(row[0]) for row in result.fetchall()]
    
    stats["total_users"] = len(user_ids)
    logger.info(f"Starting resharding for {len(user_ids)} users")
    
    # Обрабатываем пользователей батчами
    for i in range(0, len(user_ids), batch_size):
        batch = user_ids[i:i+batch_size]
        
        # Создаем задачи для решардинга пользователей
        tasks = [reshard_user(user_id) for user_id in batch]
        
        # Выполняем задачи конкурентно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error resharding user: {str(result)}")
                stats["errors"] += 1
                continue
                
            stats["processed_users"] += 1
            
            # Обновляем статистику
            for table, table_stats in result["tables"].items():
                stats["tables"][table]["copied"] += table_stats["copied"]
                stats["tables"][table]["deleted"] += table_stats["deleted"]
        
        # Выводим прогресс
        logger.info(f"Resharded {stats['processed_users']}/{stats['total_users']} users")
    
    # Завершаем статистику
    end_time = datetime.now()
    stats["end_time"] = end_time.isoformat()
    stats["duration_seconds"] = (end_time - start_time).total_seconds()
    
    return stats


class ReshardingJob:
    """Класс для управления задачами решардинга"""
    
    def __init__(self):
        self.jobs = {}
        self.running = False
    
    async def start_all_users_resharding(self, batch_size: int = 100) -> str:
        """
        Запускает решардинг всех пользователей
        
        Args:
            batch_size: Размер батча пользователей
            
        Returns:
            ID задачи
        """
        # Генерируем ID задачи
        job_id = str(uuid.uuid4())
        
        # Создаем задачу
        task = asyncio.create_task(self._run_resharding_job(job_id, batch_size))
        
        # Сохраняем задачу
        self.jobs[job_id] = {
            "task": task,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "result": None
        }
        
        return job_id
    
    async def _run_resharding_job(self, job_id: str, batch_size: int) -> None:
        """
        Выполняет задачу решардинга
        
        Args:
            job_id: ID задачи
            batch_size: Размер батча пользователей
        """
        try:
            # Запускаем решардинг
            result = await reshard_all_users(batch_size)
            
            # Обновляем статус задачи
            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["end_time"] = datetime.now().isoformat()
            self.jobs[job_id]["result"] = result
            
        except Exception as e:
            logger.error(f"Error in resharding job {job_id}: {str(e)}")
            
            # Обновляем статус задачи
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["end_time"] = datetime.now().isoformat()
            self.jobs[job_id]["error"] = str(e)
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Получает статус задачи решардинга
        
        Args:
            job_id: ID задачи
            
        Returns:
            Статус задачи
        """
        if job_id not in self.jobs:
            return {"error": "Job not found"}
        
        return self.jobs[job_id]
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """
        Получает список всех задач решардинга
        
        Returns:
            Список задач
        """
        return [
            {
                "job_id": job_id,
                "status": job["status"],
                "start_time": job["start_time"],
                "end_time": job["end_time"]
            }
            for job_id, job in self.jobs.items()
        ]

# Создаем глобальный экземпляр менеджера решардинга
resharding_job = ReshardingJob() 