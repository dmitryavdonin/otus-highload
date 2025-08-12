# Lesson 10 - Counter Service (SAGA)

Запуск (локально):

```
./lessons/lesson-10/start_service.sh
```

Остановка:

```
./lessons/lesson-10/stop_service.sh
```

Основные эндпоинты:
- /api/v1/dialogs/{peer_id}/mark_read (API)
- /api/v1/counters/{user_id} (Counter Service)
- /api/v1/counters/{user_id}/peer/{peer_id} (Counter Service)

