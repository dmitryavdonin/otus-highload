# Социальная сеть с распределенной базой данных Citus

Данный проект представляет собой социальную сеть с использованием распределенной базы данных Citus для горизонтального масштабирования.

## Требования

- Docker
- Docker Compose

## Особенности проекта

- Использование Citus для шардирования данных
- Разделение таблиц для "горячих" и обычных пользователей
- Распределенные запросы к базе данных
- Кэширование в Redis

## Архитектура системы

Проект состоит из следующих компонентов:

1. Приложение на FastAPI
2. Координатор Citus (citus-coordinator)
3. Рабочие узлы Citus:
   - citus-worker-1
   - citus-worker-2
   - citus-worker-hot (для "горячих" пользователей)
4. Redis для кэширования

## Установка и запуск

Для автоматической установки и запуска проекта выполните:

```bash
./setup.sh
```

Скрипт выполнит следующие действия:
1. Проверит наличие необходимых зависимостей
2. Запустит скрипт очистки системы (cleanup.sh)
3. Создаст/обновит все необходимые файлы конфигурации
4. Соберет и запустит Docker-контейнеры
5. Инициализирует базу данных и распределит таблицы
6. Настроит рабочие узлы Citus

### Очистка системы

Если вы хотите только очистить систему без установки, вы можете использовать скрипт:

```bash
./cleanup.sh
```

Этот скрипт:
1. Остановит и удалит все контейнеры, связанные с проектом
2. Удалит Docker-сети
3. Удалит Docker-тома

После успешного запуска приложение будет доступно по адресу: http://localhost:9000

## Ручная установка

Если вы хотите выполнить установку вручную, следуйте этим шагам:

1. Клонируйте репозиторий:
```bash
git clone <URL_репозитория>
cd <имя_директории>
```

2. Соберите и запустите контейнеры:
```bash
docker-compose build app
docker-compose up -d
```

3. Проверьте, что координатор и рабочие узлы запущены:
```bash
docker-compose ps
```

4. Добавьте рабочие узлы вручную (если автоматическое добавление не сработало):
```bash
docker exec citus-coordinator psql -U postgres -d social_network -c "SELECT master_add_node('citus-worker-1', 5432);"
docker exec citus-coordinator psql -U postgres -d social_network -c "SELECT master_add_node('citus-worker-2', 5432);"
docker exec citus-coordinator psql -U postgres -d social_network -c "SELECT master_add_node('citus-worker-hot', 5432);"
```

5. Перезапустите приложение:
```bash
docker-compose restart app
```

## Использование API

### Регистрация пользователя

```bash
curl -X POST http://localhost:9000/user/register -H "Content-Type: application/json" -d '{"first_name":"Тестовый", "second_name":"Пользователь", "birthdate":"1990-01-01", "email":"test@example.com", "password":"password123", "gender":"male", "city":"Москва", "interests":"тест"}'
```

### Авторизация

```bash
curl -X POST http://localhost:9000/user/login -H "Content-Type: application/json" -d '{"id":"<ID_пользователя>", "password":"password123"}'
```

### Получение информации о пользователе

```bash
curl http://localhost:9000/user/get/<ID_пользователя> -H "Authorization: Bearer <токен>"
```

### Создание поста

```bash
curl -X POST http://localhost:9000/post/create -H "Content-Type: application/json" -H "Authorization: Bearer <токен>" -d '{"text":"Мой первый пост в этой социальной сети!"}'
```

### Получение ленты

```bash
curl http://localhost:9000/post/feed -H "Authorization: Bearer <токен>"
```

## Проверка статуса кластера

```bash
curl http://localhost:9000/admin/cluster/status -H "Authorization: Bearer <токен>"
```

## Устранение неполадок

### Проблема: Координатор Citus не запускается

Проверьте логи:
```bash
docker-compose logs citus-coordinator
```

Попробуйте запустить вручную:
```bash
docker start citus-coordinator
```

### Проблема: Рабочие узлы не подключаются

Проверьте, что все контейнеры находятся в одной сети:
```bash
docker network inspect otus-highload_postgres_net
```

Добавьте узлы вручную (как описано в разделе "Ручная установка").

### Проблема: Приложение не может подключиться к базе данных

Проверьте, что переменные окружения правильно установлены:
```bash
docker exec otus-highload-app-1 env | grep DB_
```

## Автор

[Ваше имя] - [контактная информация]

# WebSocket Server для Real-time обновлений социальной сети

Этот сервер обеспечивает real-time обновления для социальной сети с поддержкой "эффекта Леди Гаги" - оптимизированной обработки постов от популярных пользователей.

## Быстрый старт

### 1. Запуск всех сервисов одной командой

```bash
./start_service.sh
```

Этот скрипт автоматически:
- Проверит наличие Docker и Docker Compose
- Запустит необходимые сервисы (PostgreSQL, Redis, RabbitMQ)
- Дождется их готовности
- Создаст виртуальное окружение Python
- Установит зависимости
- Запустит WebSocket сервер

### 2. Тестирование сервера

```bash
# Простой тест WebSocket соединения
./test_websocket_simple.py

# Расширенный тест с несколькими клиентами
python test_client.py --mode multi --clients 5 --duration 30
```

### 3. Остановка всех сервисов

```bash
./stop_service.sh
```

## Особенности

- **WebSocket соединения** для real-time обновлений
- **Обработка "эффекта Леди Гаги"** - батчевая отправка уведомлений для популярных пользователей
- **Интеграция с RabbitMQ** для надежной доставки сообщений
- **Кэширование в Redis** для быстрого доступа к данным
- **Масштабируемая архитектура** с поддержкой множественных соединений
- **Мониторинг и статистика** в реальном времени

## Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │  WebSocket       │    │   RabbitMQ      │
│   (React/Vue)   │◄──►│   Server         │◄──►│   Message       │
│                 │    │  (FastAPI)       │    │   Queue         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Celebrity       │    │   PostgreSQL    │
                       │  Handler         │◄──►│   Database      │
                       │  (Batch)         │    │   (Master/Slave)│
                       └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │     Redis        │
                       │    Cache         │
                       └──────────────────┘
```

## Установка и запуск

### Требования

- Python 3.8+
- PostgreSQL
- Redis
- RabbitMQ

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Настройка окружения

1. Скопируйте файл с примером переменных окружения:
```bash
cp .env.example .env
```

2. Отредактируйте `.env` файл с вашими настройками:
```bash
# Настройки базы данных
DATABASE_URL=postgresql+asyncpg://user:password@localhost/social_network

# Настройки Redis
REDIS_URL=redis://localhost:6379/0

# Настройки RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

### Запуск сервера

```bash
python websocket_server.py
```

Или с помощью uvicorn:
```bash
uvicorn websocket_server:app --host 0.0.0.0 --port 8001 --reload
```

## API Endpoints

### WebSocket

- `ws://localhost:8001/ws/{user_id}?token={jwt_token}` - WebSocket соединение для пользователя

### HTTP API

- `GET /health` - Проверка здоровья сервера
- `GET /stats` - Статистика сервера
- `GET /celebrity-stats` - Статистика знаменитостей
- `POST /celebrity-settings` - Обновление настроек обработчика знаменитостей
- `POST /test-post` - Тестовая отправка уведомления о посте

## Использование WebSocket

### Подключение

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/user123?token=your_jwt_token');

ws.onopen = function(event) {
    console.log('Connected to WebSocket');
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('Received:', message);
};
```

### Типы сообщений

#### От сервера к клиенту:

1. **Системные сообщения**:
```json
{
    "type": "system",
    "data": {
        "message": "Connected successfully",
        "timestamp": "2024-01-01T12:00:00Z"
    }
}
```

2. **Уведомления о новых постах**:
```json
{
    "type": "post_created",
    "data": {
        "post_id": "123",
        "author_user_id": "456",
        "post_text": "Hello world!",
        "created_at": "2024-01-01T12:00:00Z"
    }
}
```

#### От клиента к серверу:

1. **Ping**:
```json
{
    "type": "ping",
    "data": {}
}
```

2. **Запрос статистики**:
```json
{
    "type": "get_stats",
    "data": {}
}
```

## Эффект Леди Гаги

Сервер автоматически определяет популярных пользователей (знаменитостей) по количеству друзей и применяет специальную обработку их постов:

### Настройки

- `CELEBRITY_THRESHOLD` - порог количества друзей (по умолчанию: 1000)
- `CELEBRITY_BATCH_SIZE` - размер батча для обработки (по умолчанию: 100)
- `CELEBRITY_BATCH_DELAY` - задержка между батчами в секундах (по умолчанию: 0.1)

### Алгоритм обработки

1. **Обычные пользователи**: Мгновенная отправка уведомлений всем подключенным друзьям
2. **Знаменитости**: Батчевая отправка с задержками для снижения нагрузки на сервер

## Мониторинг

### Статистика WebSocket соединений

```bash
curl http://localhost:8001/stats
```

Ответ:
```json
{
    "websocket": {
        "total_connections": 150,
        "active_users": 145,
        "connections_per_user": {...}
    },
    "feed_processor": {
        "is_running": true,
        "rabbitmq_connected": true
    },
    "celebrity_handler": {
        "threshold": 1000,
        "batch_size": 100,
        "total_celebrities": 5
    }
}
```

### Статистика знаменитостей

```bash
curl http://localhost:8001/celebrity-stats
```

## Тестирование

### Отправка тестового поста

```bash
curl -X POST "http://localhost:8001/test-post" \
     -H "Content-Type: application/json" \
     -d '{
         "post_id": "test_123",
         "author_user_id": "user_456",
         "post_text": "Test post message"
     }'
```

### Обновление настроек знаменитостей

```bash
curl -X POST "http://localhost:8001/celebrity-settings" \
     -H "Content-Type: application/json" \
     -d '{
         "celebrity_threshold": 500,
         "batch_size": 50,
         "batch_delay": 0.2
     }'
```

## Структура проекта

```
websocket_server/
├── websocket_server.py      # Основной сервер
├── websocket_manager.py     # Менеджер WebSocket соединений
├── feed_processor.py        # Процессор событий ленты
├── celebrity_handler.py     # Обработчик знаменитостей
├── rabbitmq_client.py       # Клиент RabbitMQ
├── models.py               # Модели данных
├── config.py               # Конфигурация
├── auth.py                 # Аутентификация
├── db.py                   # Подключение к БД
├── requirements.txt        # Зависимости
├── .env.example           # Пример переменных окружения
└── README.md              # Документация
```

## Производительность

### Рекомендации по масштабированию

1. **Горизонтальное масштабирование**: Запуск нескольких экземпляров сервера за load balancer
2. **Redis Cluster**: Для кэширования при высокой нагрузке
3. **RabbitMQ Cluster**: Для надежности очередей сообщений
4. **Database sharding**: Разделение пользователей по серверам БД

### Оптимизация для знаменитостей

- Настройка размера батча в зависимости от нагрузки
- Использование отдельных очередей для знаменитостей
- Кэширование списков друзей в Redis
- Асинхронная обработка с приоритетами

## Безопасность

- JWT аутентификация для WebSocket соединений
- Валидация всех входящих сообщений
- Rate limiting для предотвращения спама
- CORS настройки для веб-клиентов

## Логирование

Сервер ведет подробные логи всех операций:

- Подключения/отключения пользователей
- Обработка сообщений из очередей
- Статистика отправки уведомлений
- Ошибки и исключения

Уровень логирования настраивается через переменную `LOG_LEVEL` в `.env` файле.

## Troubleshooting

### Частые проблемы

1. **WebSocket соединение не устанавливается**:
   - Проверьте правильность JWT токена
   - Убедитесь, что сервер запущен на правильном порту

2. **Уведомления не приходят**:
   - Проверьте подключение к RabbitMQ
   - Убедитесь, что feed_processor запущен

3. **Высокая нагрузка от знаменитостей**:
   - Увеличьте `CELEBRITY_BATCH_DELAY`
   - Уменьшите `CELEBRITY_BATCH_SIZE`
   - Рассмотрите использование отдельных серверов

### Логи для диагностики

```bash
# Просмотр логов в реальном времени
tail -f websocket_server.log

# Поиск ошибок
grep ERROR websocket_server.log

# Статистика по знаменитостям
grep "Celebrity" websocket_server.log
``` 