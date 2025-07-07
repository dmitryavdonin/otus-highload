# Домашнее задание №8 - Разделение монолита на сервисы

## Описание

Данное домашнее задание демонстрирует вынос системы диалогов из монолитного приложения в отдельный микросервис с обеспечением:

- REST API для работы с диалогами
- Сквозного логирования (x-request-id)
- Обратной совместимости с существующими клиентами
- Версионирования API (v1 - legacy, v2 - новый)
- Использования Redis UDF для хранения данных

## Архитектура

### Исходная архитектура (Монолит)
```
Client App → Monolith App → PostgreSQL + Redis
```

### Новая архитектура (Микросервисы)

**Потоки запросов:**

- **v1 API (Legacy):** `Client → Nginx → Monolith → Dialog Wrapper → Dialog Service → Redis UDF`
- **v2 API (Modern):** `Client → Nginx → Dialog Service → Redis UDF`  
- **Other APIs:** `Client → Nginx → Monolith → PostgreSQL`

**Компоненты:**
- **Nginx (Port 80)** - точка входа и маршрутизация
- **Monolith (Port 8000)** - основное приложение + Dialog Wrapper
- **Dialog Service (Port 8002)** - микросервис диалогов
- **Redis** - хранилище диалогов с UDF
- **PostgreSQL** - основная база данных

## Компоненты

- **Nginx** - обратный прокси для маршрутизации запросов
- **Monolith** - основное приложение с legacy функциями
- **Dialog Service** - выделенный микросервис диалогов
- **Dialog Wrapper** - прокси-компонент в монолите
- **Redis UDF** - хранилище диалогов с Lua-скриптами
- **PostgreSQL** - основная база данных

## Быстрый старт

### 1. Запуск системы
```bash
# Запуск всех сервисов
./start_service.sh

# Проверка, что все сервисы запущены
docker-compose ps
```

### 2. Тестирование
```bash
# Комплексное тестирование v1 и v2 API
./test_dialog_service.sh
```

### 3. Остановка
```bash
# Остановка всех сервисов
./stop_service.sh
```

## Детальные инструкции

### Запуск системы

1. **Убедитесь, что Docker и Docker Compose установлены**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Запустите все сервисы**
   ```bash
   ./start_service.sh
   ```
   
   Скрипт автоматически:
   - Остановит существующие контейнеры
   - Соберет Docker образы
   - Запустит PostgreSQL, Redis, Dialog Service, Monolith, Nginx
   - Дождется готовности всех сервисов

3. **Проверьте доступность сервисов**
   ```bash
   # Nginx
   curl http://localhost:80/health
   
   # Monolith
   curl http://localhost:8000/health
   
   # Dialog Service
   curl http://localhost:8002/health
   ```

### Тестирование API

#### Автоматическое тестирование
```bash
./test_dialog_service.sh
```

Скрипт выполняет:
- Проверку доступности всех сервисов
- Регистрацию тестовых пользователей
- Авторизацию
- Тестирование v1 API (legacy)
- Тестирование v2 API (modern)
- Проверку статистики

#### Ручное тестирование

1. **Регистрация пользователя**
   ```bash
   curl -X POST http://localhost:80/user/register \
     -H "Content-Type: application/json" \
     -d '{
       "first_name": "Test",
       "second_name": "User",
       "birthdate": "1990-01-01T00:00:00",
       "city": "Moscow",
       "password": "password123"
     }'
   ```

2. **Авторизация**
   ```bash
   curl -X POST http://localhost:80/user/login \
     -H "Content-Type: application/json" \
     -d '{
       "id": "USER_ID",
       "password": "password123"
     }'
   ```

3. **Отправка сообщения через v1 API (legacy)**
   ```bash
   curl -X POST http://localhost:80/v1/dialog/USER_ID/send \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer TOKEN" \
     -d '{"text": "Hello from v1 API!"}'
   ```

4. **Отправка сообщения через v2 API (modern)**
   ```bash
   curl -X POST http://localhost:80/v2/dialog/send \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer TOKEN" \
     -d '{
       "to_user_id": "USER_ID",
       "text": "Hello from v2 API!"
     }'
   ```

5. **Получение сообщений через v1 API**
   ```bash
   curl -X GET http://localhost:80/v1/dialog/USER_ID/list \
     -H "Authorization: Bearer TOKEN"
   ```

6. **Получение сообщений через v2 API**
   ```bash
   curl -X GET http://localhost:80/v2/dialog/USER_ID/messages \
     -H "Authorization: Bearer TOKEN"
   ```

### Мониторинг и логи

#### Просмотр логов
```bash
# Логи всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f dialog-service
docker-compose logs -f monolith
docker-compose logs -f nginx
```

#### Поиск по request-id
```bash
# Поиск логов по конкретному request-id
docker-compose logs | grep "REQUEST_ID"
```

#### Статистика Redis
```bash
# Подключение к Redis
docker-compose exec redis redis-cli

# Просмотр ключей диалогов
KEYS dialog:*

# Статистика диалогов
GET dialog_stats
```

## Структура файлов

```
otus-highload/
├── lesson-08/
│   ├── homework_report.html           # Отчет о выполнении
│   └── README.md                      # Данная инструкция
├── dialog-service/                    # Микросервис диалогов
│   ├── app/
│   │   ├── main.py                   # FastAPI приложение
│   │   ├── api/dialogs.py            # API эндпоинты
│   │   ├── services/
│   │   │   ├── dialog_service.py     # Бизнес-логика
│   │   │   └── redis_adapter.py      # Redis UDF интеграция
│   │   └── middleware/
│   │       └── request_id.py         # Middleware для трассировки
│   ├── Dockerfile                    # Docker образ сервиса
│   └── requirements.txt              # Зависимости
├── services/
│   └── dialog_wrapper.py             # Прокси в монолите
├── clients/
│   └── dialog_service_client.py      # HTTP клиент
├── middleware/
│   └── request_id_middleware.py      # Middleware для монолита
├── nginx.conf                        # Конфигурация Nginx
├── docker-compose.yml               # Оркестрация сервисов
├── start_service.sh                 # Скрипт запуска
├── stop_service.sh                  # Скрипт остановки
└── test_dialog_service.sh           # Скрипт тестирования
```

## API Endpoints

### v1 API (Legacy)

- `POST /v1/dialog/{user_id}/send` - отправка сообщения
- `GET /v1/dialog/{user_id}/list` - получение сообщений
- `GET /v1/dialog/stats` - статистика диалогов

### v2 API (Modern)

- `POST /v2/dialog/send` - отправка сообщения
- `GET /v2/dialog/{user_id}/messages` - получение сообщений
- `GET /v2/dialog/stats` - статистика диалогов

## Архитектурные принципы

### Strangler Fig Pattern
- Legacy клиенты продолжают работать через v1 API
- Новые клиенты используют v2 API
- Вся логика диалогов физически находится в Dialog Service
- Монолит только проксирует запросы

### Fail Fast
- При недоступности Dialog Service возвращается ошибка
- Нет дублирования логики в монолите
- Проблемы с сервисом видны сразу
- Упрощение архитектуры и отладки

### Сквозное логирование
- x-request-id проходит через всю цепочку запросов
- Структурированные логи во всех компонентах
- Возможность трассировки запросов

## Устранение неполадок

### Сервисы не запускаются
```bash
# Проверьте статус контейнеров
docker-compose ps

# Проверьте логи
docker-compose logs

# Перезапустите с пересборкой
./stop_service.sh
docker-compose build --no-cache
./start_service.sh
```

### Проблемы с подключением
```bash
# Проверьте сетевые настройки
docker network ls
docker network inspect otus-highload_default

# Проверьте порты
netstat -tulpn | grep -E '80|8000|8002'
```

### Проблемы с Redis UDF
```bash
# Подключитесь к Redis
docker-compose exec redis redis-cli

# Проверьте загруженные скрипты
SCRIPT LIST

# Проверьте логи Dialog Service
docker-compose logs dialog-service | grep -i lua
```

## Результаты

✅ **Все требования выполнены:**
- Диалоги вынесены в отдельный сервис
- REST API реализован
- Сквозное логирование настроено
- Обратная совместимость обеспечена
- Версионирование API реализовано

✅ **Тестирование прошло успешно:**
- v1 API: отправка и получение сообщений
- v2 API: отправка и получение сообщений
- Сквозная трассировка запросов
- Корректная статистика диалогов

## Контакты

Если у вас возникли вопросы по выполнению домашнего задания, обратитесь к отчету `homework_report.html` для получения детальной информации о реализации. 