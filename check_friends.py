#!/usr/bin/env python3
import asyncio
import re
import sys
sys.path.append('.')
from db import get_user_friends

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
        
        user1_friends = await get_user_friends(user1_id)
        user2_friends = await get_user_friends(user2_id)
        
        print(f"\nUser1 (Алексей) friends: {user1_friends}")
        print(f"User2 (Мария) friends: {user2_friends}")
        
        print(f"\nUser1 has User2 as friend: {user2_id in user1_friends}")
        print(f"User2 has User1 as friend: {user1_id in user2_friends}")
        
        print(f"\nUser1 has themselves as friend: {user1_id in user1_friends}")
        print(f"User2 has themselves as friend: {user2_id in user2_friends}")
        
        print(f"\nUsers are mutual friends: {user2_id in user1_friends and user1_id in user2_friends}")
        
        # Объяснение логики лент
        print("\n" + "="*60)
        print("ЛОГИКА ЛЕНТ:")
        print("="*60)
        print("1. Алексей добавил Марию в друзья → Алексей видит посты Марии")
        print("2. Мария добавила Алексея в друзья → Мария видит посты Алексея")
        print("3. Поэтому ленты выглядят одинаково - каждый видит посты друга!")
        print("4. Это корректное поведение для социальной сети с взаимной дружбой.")
        
    else:
        print("Not enough user IDs found")

if __name__ == "__main__":
    asyncio.run(main()) 