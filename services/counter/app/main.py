from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import os
import uuid
import asyncio
import redis.asyncio as redis
import json
import logging

logger = logging.getLogger(__name__)


class CounterService:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_counters: Optional[redis.Redis] = None
        # Отдельное подключение к Redis, где лежат диалоги (для сверки)
        self.redis_dialogs: Optional[redis.Redis] = None
        self.reconcile_task: Optional[asyncio.Task] = None

    async def connect(self):
        self.redis_counters = redis.from_url(self.redis_url, decode_responses=True)
        await self.redis_counters.ping()
        dialog_url = os.getenv("REDIS_DIALOG_URL", "redis://redis:6379/1")
        self.redis_dialogs = redis.from_url(dialog_url, decode_responses=True)
        await self.redis_dialogs.ping()
        # Запускаем периодическую сверку, если включено
        if os.getenv("RECONCILIATION_ENABLED", "true").lower() == "true":
            self.reconcile_task = asyncio.create_task(self._reconcile_loop())

    async def close(self):
        if self.reconcile_task and not self.reconcile_task.done():
            self.reconcile_task.cancel()
            try:
                await self.reconcile_task
            except Exception:
                pass
        if self.redis_counters:
            await self.redis_counters.close()
        if self.redis_dialogs:
            await self.redis_dialogs.close()

    def _key_total(self, user_id: str) -> str:
        return f"user:{user_id}:unread_total"

    def _key_by_peer(self, user_id: str) -> str:
        return f"user:{user_id}:unread_by_peer"

    def _key_last_read(self, user_id: str, peer_id: str) -> str:
        return f"user:{user_id}:last_read:{peer_id}"

    def _key_dedup(self, event_id: str) -> str:
        return f"event_dedup:{event_id}"

    def _dialog_key(self, user_id1: str, user_id2: str) -> str:
        # такой же алгоритм, как в dialog_service: отсортированные ID
        ids = sorted([str(user_id1), str(user_id2)])
        return f"dialog:{ids[0]}:{ids[1]}"

    async def get_counters(self, user_id: str) -> Dict:
        total = await self.redis_counters.get(self._key_total(user_id))
        by_peer = await self.redis_counters.hgetall(self._key_by_peer(user_id))
        return {
            "user_id": user_id,
            "total_unread": int(total) if total is not None else 0,
            "by_peer": {k: int(v) for k, v in by_peer.items()},
        }

    async def get_counter_for_peer(self, user_id: str, peer_id: str) -> Dict:
        count = await self.redis_counters.hget(self._key_by_peer(user_id), peer_id)
        last_read = await self.redis_counters.get(self._key_last_read(user_id, peer_id))
        return {
            "user_id": user_id,
            "peer_user_id": peer_id,
            "unread": int(count) if count is not None else 0,
            "last_read_ts": float(last_read) if last_read is not None else None,
        }

    async def apply_message_sent(self, event_id: str, to_user_id: str, from_user_id: str) -> bool:
        # идемпотентность
        if await self.redis_counters.setnx(self._key_dedup(event_id), "1"):
            await self.redis_counters.expire(self._key_dedup(event_id), 24 * 3600)
        else:
            return False
        pipe = self.redis_counters.pipeline()
        pipe.incr(self._key_total(to_user_id))
        pipe.hincrby(self._key_by_peer(to_user_id), from_user_id, 1)
        await pipe.execute()
        return True

    async def apply_messages_read(self, event_id: str, user_id: str, peer_id: str, delta: int, last_read_ts: Optional[float]) -> bool:
        if await self.redis_counters.setnx(self._key_dedup(event_id), "1"):
            await self.redis_counters.expire(self._key_dedup(event_id), 24 * 3600)
        else:
            return False
        # корректный декремент без ухода в минус
        by_peer_key = self._key_by_peer(user_id)
        total_key = self._key_total(user_id)
        current_peer = await self.redis_counters.hget(by_peer_key, peer_id)
        current_total = await self.redis_counters.get(total_key)
        peer_val = max(0, (int(current_peer) if current_peer else 0) - max(0, delta))
        total_val = max(0, (int(current_total) if current_total else 0) - max(0, delta))
        pipe = self.redis_counters.pipeline()
        pipe.hset(by_peer_key, peer_id, peer_val)
        pipe.set(total_key, total_val)
        if last_read_ts is not None:
            pipe.set(self._key_last_read(user_id, peer_id), last_read_ts)
        await pipe.execute()
        return True

    async def _reconcile_loop(self):
        interval = int(os.getenv("RECONCILIATION_INTERVAL_SEC", "60"))
        while True:
            try:
                await self.reconcile_all()
            except Exception:
                pass
            await asyncio.sleep(interval)

    async def reconcile_all(self):
        """Сверка счетчиков для всех пользователей, у кого есть hash unread_by_peer."""
        # Ищем ключи вида user:*:unread_by_peer
        cursor = 0
        pattern = "user:*:unread_by_peer"
        users_pairs = []
        while True:
            cursor, keys = await self.redis_counters.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                # key = user:{uid}:unread_by_peer
                try:
                    user_id = key.split(":")[1]
                except Exception:
                    continue
                users_pairs.append((user_id, key))
            if cursor == 0:
                break
        # Для каждого пользователя сверяем по собеседникам
        for user_id, by_peer_key in users_pairs:
            by_peer = await self.redis_counters.hgetall(by_peer_key)
            corrected_by_peer: Dict[str, int] = {}
            for peer_id, current_count_str in by_peer.items():
                try:
                    last_read = await self.redis_counters.get(self._key_last_read(user_id, peer_id))
                    last_ts = float(last_read) if last_read is not None else 0.0
                    dialog_key = self._dialog_key(user_id, peer_id)
                    # Получаем все сообщения после last_ts и фильтруем по to_user_id == user_id
                    raw_msgs = await self.redis_dialogs.zrangebyscore(dialog_key, min=last_ts, max="+inf")
                    cnt = 0
                    for m in raw_msgs:
                        try:
                            obj = json.loads(m)
                            if str(obj.get("to_user_id")) == str(user_id):
                                cnt += 1
                        except Exception:
                            continue
                    corrected_by_peer[peer_id] = cnt
                except Exception:
                    # В случае ошибки оставляем текущее значение
                    try:
                        corrected_by_peer[peer_id] = int(current_count_str)
                    except Exception:
                        corrected_by_peer[peer_id] = 0
            # Обновляем hash и total
            pipe = self.redis_counters.pipeline()
            total_val = sum(corrected_by_peer.values())
            if corrected_by_peer:
                pipe.hset(by_peer_key, mapping={k: str(v) for k, v in corrected_by_peer.items()})
            pipe.set(self._key_total(user_id), total_val)
            await pipe.execute()


class MarkReadRequest(BaseModel):
    user_id: str
    peer_user_id: str
    delta: int
    last_read_ts: Optional[float] = None
    idempotency_key: Optional[str] = None


app = FastAPI(title="Counter Service", version="0.1.0")
service: Optional[CounterService] = None

# Alias for use in RabbitMQ consumer
counter_service = service


@app.on_event("startup")
async def on_startup():
    global service, counter_service
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/2")
    service = CounterService(redis_url)
    counter_service = service  # Update alias
    await service.connect()
    
    # Initialize RabbitMQ consumer if configured
    events_transport = os.getenv('EVENTS_TRANSPORT', 'http').lower()
    if events_transport == 'rabbitmq':
        logger.info("Initializing RabbitMQ consumer")
        try:
            from .rabbitmq_consumer import init_rabbitmq_consumer
            await init_rabbitmq_consumer()
        except Exception as e:
            logger.error(f"Failed to initialize RabbitMQ consumer: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    # Close RabbitMQ consumer if it was initialized
    events_transport = os.getenv('EVENTS_TRANSPORT', 'http').lower()
    if events_transport == 'rabbitmq':
        logger.info("Closing RabbitMQ consumer")
        try:
            from .rabbitmq_consumer import close_rabbitmq_consumer
            await close_rabbitmq_consumer()
        except Exception as e:
            logger.error(f"Error closing RabbitMQ consumer: {e}")
    
    if service:
        await service.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/counters/{user_id}")
async def get_counters(user_id: str):
    return await service.get_counters(user_id)


@app.get("/api/v1/counters/{user_id}/peer/{peer_id}")
async def get_counter_for_peer(user_id: str, peer_id: str):
    return await service.get_counter_for_peer(user_id, peer_id)


@app.post("/api/v1/counters/mark_read")
async def mark_read(req: MarkReadRequest):
    event_id = req.idempotency_key or str(uuid.uuid4())
    ok = await service.apply_messages_read(event_id, req.user_id, req.peer_user_id, req.delta, req.last_read_ts)
    return {"applied": ok, "event_id": event_id}


class MessageSentEvent(BaseModel):
    event_id: str
    from_user_id: str
    to_user_id: str


@app.post("/internal/events/message_sent")
async def message_sent(event: MessageSentEvent):
    ok = await service.apply_message_sent(event.event_id, event.to_user_id, event.from_user_id)
    return {"applied": ok}


class MessagesReadEvent(BaseModel):
    event_id: str
    user_id: str
    peer_user_id: str
    delta: int
    last_read_ts: Optional[float] = None


@app.post("/internal/events/messages_read")
async def messages_read(event: MessagesReadEvent):
    ok = await service.apply_messages_read(event.event_id, event.user_id, event.peer_user_id, event.delta, event.last_read_ts)
    return {"applied": ok}


