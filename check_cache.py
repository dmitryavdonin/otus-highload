#!/usr/bin/env python3
import asyncio
import re
from cache import RedisCache

async def main():
    # Читаем отчет и извлекаем ID пользователей
    with open('lesson-06/test_report.html', 'r') as f:
        content = f.read()
    
    user_ids = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', content)
    
    if len(user_ids) >= 2:
        user1_id = user_ids[0]
        user2_id = user_ids[1]
        
        print(f"User1 ID: {user1_id}")
        print(f"User2 ID: {user2_id}")
        
        # Создаем экземпляр кэша
        cache = RedisCache()
        
        user1_feed = await cache.get_feed(user1_id, 0, 10)
        user2_feed = await cache.get_feed(user2_id, 0, 10)
        
        print(f"\nUser1 cached feed: {len(user1_feed)} posts")
        for i, post in enumerate(user1_feed):
            author = post.get('author_user_id', 'unknown')
            text = post.get('text', 'no text')[:50]
            print(f"  Post {i+1}: author={author[:8]}... text='{text}...'")
        
        print(f"\nUser2 cached feed: {len(user2_feed)} posts")
        for i, post in enumerate(user2_feed):
            author = post.get('author_user_id', 'unknown')
            text = post.get('text', 'no text')[:50]
            print(f"  Post {i+1}: author={author[:8]}... text='{text}...'")
        
        # Проверяем, есть ли собственные посты в лентах
        user1_own_posts = [p for p in user1_feed if p.get('author_user_id') == user1_id]
        user2_own_posts = [p for p in user2_feed if p.get('author_user_id') == user2_id]
        
        print(f"\nUser1 has {len(user1_own_posts)} own posts in feed")
        print(f"User2 has {len(user2_own_posts)} own posts in feed")
        
        await cache.close()
    else:
        print("Not enough user IDs found")

if __name__ == "__main__":
    asyncio.run(main()) 