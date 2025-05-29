#!/usr/bin/env python3
import asyncio
import re
import requests
from cache import RedisCache

API_BASE_URL = "http://localhost:9000"

async def main():
    # Читаем отчет и извлекаем ID пользователей
    with open('lesson-06/test_report.html', 'r') as f:
        content = f.read()
    
    user_ids = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', content)
    
    if len(user_ids) >= 2:
        user1_id = user_ids[0]  # Алексей
        user2_id = user_ids[1]  # Мария
        
        print(f"User1 (Алексей) ID: {user1_id}")
        print(f"User2 (Мария) ID: {user2_id}")
        
        # Создаем экземпляр кэша
        cache = RedisCache()
        
        # Проверяем кэшированные ленты
        user1_cached_feed = await cache.get_feed(user1_id, 0, 10)
        user2_cached_feed = await cache.get_feed(user2_id, 0, 10)
        
        print(f"\n=== КЭШИРОВАННЫЕ ЛЕНТЫ ===")
        print(f"User1 cached feed: {len(user1_cached_feed)} posts")
        for i, post in enumerate(user1_cached_feed):
            author = post.get('author_user_id', 'unknown')
            text = post.get('text', 'no text')[:50]
            is_own = "🔴 СВОЙ ПОСТ" if author == user1_id else "✅ пост друга"
            print(f"  {i+1}. {is_own} - author={author[:8]}... text='{text}...'")
        
        print(f"\nUser2 cached feed: {len(user2_cached_feed)} posts")
        for i, post in enumerate(user2_cached_feed):
            author = post.get('author_user_id', 'unknown')
            text = post.get('text', 'no text')[:50]
            is_own = "🔴 СВОЙ ПОСТ" if author == user2_id else "✅ пост друга"
            print(f"  {i+1}. {is_own} - author={author[:8]}... text='{text}...'")
        
        # Проверяем, что возвращает API напрямую
        print(f"\n=== ПРЯМЫЕ ЗАПРОСЫ К API ===")
        
        # Нужно получить токены пользователей из логов или создать новые
        print("Для полной проверки нужны токены пользователей...")
        print("Проверим только кэш и базу данных.")
        
        await cache.close()
    else:
        print("Not enough user IDs found")

if __name__ == "__main__":
    asyncio.run(main()) 