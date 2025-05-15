import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
import uuid
from datetime import datetime
from database import get_session, CITUS_ENABLED, HOT_USER_THRESHOLD

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def mark_hot_user(user_id: str, is_hot: bool = True) -> bool:
    """
    Отмечает пользователя как "горячего" или обычного
    
    Args:
        user_id: ID пользователя
        is_hot: True для отметки пользователя как горячего, False для снятия отметки
        
    Returns:
        True если операция успешна, False в противном случае
    """
    if not CITUS_ENABLED:
        logger.warning("Citus is not enabled, cannot mark hot user")
        return False
    
    try:
        async with get_session() as session:
            # Изменяем статус пользователя
            query = text("""
            UPDATE users 
            SET is_hot_user = :is_hot 
            WHERE id = :user_id
            RETURNING id
            """)
            
            result = await session.execute(query, {"user_id": user_id, "is_hot": is_hot})
            updated_id = result.scalar_one_or_none()
            
            if not updated_id:
                logger.warning(f"User {user_id} not found")
                return False
            
            await session.commit()
            
            logger.info(f"User {user_id} is now {'hot' if is_hot else 'regular'}")
            return True
            
    except Exception as e:
        logger.error(f"Error marking user {user_id} as hot: {e}")
        return False

async def migrate_hot_user_posts(user_id: str) -> Dict[str, Any]:
    """
    Перемещает посты пользователя из обычной таблицы в таблицу для горячих пользователей
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Статистика миграции
    """
    if not CITUS_ENABLED:
        logger.warning("Citus is not enabled, cannot migrate posts")
        return {"migrated": 0, "status": "failed", "reason": "Citus not enabled"}
    
    stats = {
        "user_id": user_id,
        "migrated": 0,
        "errors": 0,
        "status": "success"
    }
    
    try:
        async with get_session() as session:
            # Проверяем, является ли пользователь горячим
            query = text("SELECT is_hot_user FROM users WHERE id = :user_id")
            result = await session.execute(query, {"user_id": user_id})
            is_hot = result.scalar_one_or_none()
            
            if not is_hot:
                logger.warning(f"User {user_id} is not marked as hot")
                stats["status"] = "failed"
                stats["reason"] = "User is not marked as hot"
                return stats
            
            # Получаем список постов пользователя из обычной таблицы
            query = text("""
            SELECT id, text, author_user_id, created_at
            FROM posts
            WHERE author_user_id = :user_id
            """)
            
            result = await session.execute(query, {"user_id": user_id})
            posts = result.fetchall()
            
            # Мигрируем посты
            for post in posts:
                post_id, text, author_id, created_at = post
                
                # Вычисляем time_bucket
                time_bucket = int(created_at.year * 100 + created_at.month)
                
                try:
                    # Добавляем пост в таблицу для горячих пользователей
                    insert_query = text("""
                    INSERT INTO posts_hot_users (id, text, author_user_id, created_at, time_bucket)
                    VALUES (:id, :text, :author_id, :created_at, :time_bucket)
                    """)
                    
                    await session.execute(
                        insert_query,
                        {
                            "id": post_id,
                            "text": text,
                            "author_id": author_id,
                            "created_at": created_at,
                            "time_bucket": time_bucket
                        }
                    )
                    
                    # Удаляем пост из обычной таблицы
                    delete_query = text("DELETE FROM posts WHERE id = :id")
                    await session.execute(delete_query, {"id": post_id})
                    
                    stats["migrated"] += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating post {post_id}: {e}")
                    stats["errors"] += 1
            
            await session.commit()
            
            logger.info(f"Migrated {stats['migrated']} posts for user {user_id}")
            return stats
            
    except Exception as e:
        logger.error(f"Error migrating posts for user {user_id}: {e}")
        stats["status"] = "failed"
        stats["reason"] = str(e)
        return stats

async def detect_hot_users(threshold: int = None) -> List[Dict[str, Any]]:
    """
    Обнаруживает горячих пользователей на основе количества постов
    
    Args:
        threshold: Порог количества постов для отметки пользователя как горячего
        
    Returns:
        Список пользователей, помеченных как горячие
    """
    if not CITUS_ENABLED:
        logger.warning("Citus is not enabled, cannot detect hot users")
        return []
    
    if threshold is None:
        threshold = HOT_USER_THRESHOLD
    
    detected_users = []
    
    try:
        async with get_session() as session:
            # Находим пользователей с большим количеством постов, которые еще не отмечены как горячие
            query = text("""
            SELECT u.id, u.first_name, u.second_name, COUNT(p.id) as post_count
            FROM users u
            JOIN posts p ON u.id = p.author_user_id
            WHERE u.is_hot_user = false
            GROUP BY u.id, u.first_name, u.second_name
            HAVING COUNT(p.id) >= :threshold
            """)
            
            result = await session.execute(query, {"threshold": threshold})
            users = result.fetchall()
            
            # Отмечаем пользователей как горячих и мигрируем их посты
            for user in users:
                user_id, first_name, second_name, post_count = user
                user_id = str(user_id)
                
                # Отмечаем пользователя как горячего
                await mark_hot_user(user_id, True)
                
                # Мигрируем посты
                migration_result = await migrate_hot_user_posts(user_id)
                
                detected_users.append({
                    "id": user_id,
                    "first_name": first_name,
                    "second_name": second_name,
                    "post_count": post_count,
                    "migrated_posts": migration_result["migrated"]
                })
            
            logger.info(f"Detected {len(detected_users)} new hot users")
            return detected_users
            
    except Exception as e:
        logger.error(f"Error detecting hot users: {e}")
        return []

async def rebalance_shards() -> Dict[str, Any]:
    """
    Запускает перебалансировку шардов в кластере Citus
    
    Returns:
        Результат операции
    """
    if not CITUS_ENABLED:
        logger.warning("Citus is not enabled, cannot rebalance shards")
        return {"status": "failed", "reason": "Citus not enabled"}
    
    try:
        async with get_session() as session:
            # Проверяем, есть ли активная перебалансировка
            query = text("SELECT citus_rebalance_status()")
            result = await session.execute(query)
            status = result.scalar_one()
            
            if status and "rebalance in progress" in status.lower():
                return {"status": "in_progress", "details": status}
            
            # Запускаем перебалансировку
            query = text("SELECT citus_rebalance_start()")
            await session.execute(query)
            
            return {"status": "started"}
            
    except Exception as e:
        logger.error(f"Error rebalancing shards: {e}")
        return {"status": "failed", "reason": str(e)}

async def get_shards_distribution() -> Dict[str, Any]:
    """
    Получает информацию о распределении шардов в кластере
    
    Returns:
        Статистика распределения шардов
    """
    if not CITUS_ENABLED:
        logger.warning("Citus is not enabled, cannot get shard distribution")
        return {"citus_enabled": False}
    
    try:
        async with get_session() as session:
            # Получаем распределение шардов по узлам
            query = text("""
            SELECT 
                nodename, 
                logicalrelid::text as table_name, 
                COUNT(*) as shard_count
            FROM pg_dist_placement p
            JOIN pg_dist_shard s ON p.shardid = s.shardid
            GROUP BY nodename, logicalrelid
            ORDER BY nodename, logicalrelid
            """)
            
            result = await session.execute(query)
            distribution = {}
            
            for row in result.fetchall():
                node_name, table_name, shard_count = row
                
                if node_name not in distribution:
                    distribution[node_name] = {}
                    
                distribution[node_name][table_name] = shard_count
            
            # Получаем общую информацию о шардах
            query = text("""
            SELECT 
                logicalrelid::text as table_name, 
                COUNT(*) as total_shards
            FROM pg_dist_shard
            GROUP BY logicalrelid
            """)
            
            result = await session.execute(query)
            totals = {table_name: total_shards for table_name, total_shards in result.fetchall()}
            
            return {
                "citus_enabled": True,
                "distribution": distribution,
                "totals": totals
            }
            
    except Exception as e:
        logger.error(f"Error getting shard distribution: {e}")
        return {"citus_enabled": True, "status": "error", "reason": str(e)}

async def setup_scheduled_tasks():
    """
    Настраивает регулярные задачи для обслуживания кластера Citus
    """
    if not CITUS_ENABLED:
        logger.info("Citus is not enabled, not setting up scheduled tasks")
        return
    
    async def scheduled_hot_user_detection():
        """Регулярно проверяет наличие новых горячих пользователей"""
        while True:
            try:
                logger.info("Running scheduled hot user detection")
                await detect_hot_users()
            except Exception as e:
                logger.error(f"Error in scheduled hot user detection: {e}")
            
            # Запускаем каждые 6 часов
            await asyncio.sleep(6 * 60 * 60)
    
    # Запускаем задачи в фоновом режиме
    asyncio.create_task(scheduled_hot_user_detection()) 