#!/usr/bin/env python3
import asyncio
import re
import sys
sys.path.append('.')
from db import get_slave_session, get_user_friends
from models import Post, Friendship
from sqlalchemy import select

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
        
        # Проверяем дружеские связи
        user1_friends = await get_user_friends(user1_id)
        user2_friends = await get_user_friends(user2_id)
        
        print(f"\nUser1 friends: {user1_friends}")
        print(f"User2 friends: {user2_friends}")
        
        # Проверяем все посты в базе данных
        async with get_slave_session() as session:
            result = await session.execute(
                select(Post).order_by(Post.created_at.desc())
            )
            all_posts = result.scalars().all()
            
            print(f"\n=== ВСЕ ПОСТЫ В БД ===")
            for i, post in enumerate(all_posts):
                author_name = "Алексей" if str(post.author_user_id) == user1_id else "Мария"
                print(f"{i+1}. {author_name} ({str(post.author_user_id)[:8]}...): {post.text[:50]}...")
        
        # Проверяем, что должно быть в ленте User1 (Алексея)
        print(f"\n=== ЛЕНТА USER1 (АЛЕКСЕЙ) - ДОЛЖНА СОДЕРЖАТЬ ПОСТЫ МАРИИ ===")
        async with get_slave_session() as session:
            # Подзапрос для получения всех friend_id, установленных User1
            subq = select(Friendship.friend_id).where(Friendship.user_id == user1_id).subquery()
            
            # Получаем посты, где автор является одним из друзей User1
            query = (
                select(Post)
                .where(Post.author_user_id.in_(subq))
                .order_by(Post.created_at.desc())
            )
            result = await session.execute(query)
            user1_feed_posts = result.scalars().all()
            
            print(f"Найдено {len(user1_feed_posts)} постов для ленты User1:")
            for i, post in enumerate(user1_feed_posts):
                author_name = "Алексей" if str(post.author_user_id) == user1_id else "Мария"
                is_own = "🔴 СВОЙ ПОСТ!" if str(post.author_user_id) == user1_id else "✅ пост друга"
                print(f"  {i+1}. {is_own} {author_name}: {post.text[:50]}...")
        
        # Проверяем, что должно быть в ленте User2 (Марии)
        print(f"\n=== ЛЕНТА USER2 (МАРИЯ) - ДОЛЖНА СОДЕРЖАТЬ ПОСТЫ АЛЕКСЕЯ ===")
        async with get_slave_session() as session:
            # Подзапрос для получения всех friend_id, установленных User2
            subq = select(Friendship.friend_id).where(Friendship.user_id == user2_id).subquery()
            
            # Получаем посты, где автор является одним из друзей User2
            query = (
                select(Post)
                .where(Post.author_user_id.in_(subq))
                .order_by(Post.created_at.desc())
            )
            result = await session.execute(query)
            user2_feed_posts = result.scalars().all()
            
            print(f"Найдено {len(user2_feed_posts)} постов для ленты User2:")
            for i, post in enumerate(user2_feed_posts):
                author_name = "Алексей" if str(post.author_user_id) == user1_id else "Мария"
                is_own = "🔴 СВОЙ ПОСТ!" if str(post.author_user_id) == user2_id else "✅ пост друга"
                print(f"  {i+1}. {is_own} {author_name}: {post.text[:50]}...")
        
    else:
        print("Not enough user IDs found")

if __name__ == "__main__":
    asyncio.run(main()) 