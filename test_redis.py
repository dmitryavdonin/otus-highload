#!/usr/bin/env python3
import asyncio
import redis.asyncio as redis

async def test_redis():
    try:
        r = redis.from_url('redis://redis:6379/0')
        await r.ping()
        print('✅ Redis подключение работает')
        await r.close()
        return True
    except Exception as e:
        print(f'❌ Ошибка Redis: {e}')
        return False

if __name__ == "__main__":
    asyncio.run(test_redis()) 