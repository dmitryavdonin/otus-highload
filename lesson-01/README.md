# Инструкция по запуску социальной сети

## Запуск с использованием Docker

### Предварительные требования
- Установленный Docker и Docker Compose
- Git для клонирования репозитория

### Шаги по запуску
1. Клонируйте репозиторий:
   ```bash
   git clone <URL репозитория>
   cd otus-highload/lesson-01
   ```

2. Запустите приложение с помощью Docker Compose:
   ```bash
   docker-compose up -d
   ```

3. Проверьте, что контейнеры запущены:
   ```bash
   docker-compose ps
   ```

4. API будет доступно по адресу: http://localhost:8000
5. Документация API (Swagger UI): http://localhost:8000/docs

## Запуск без Docker

### Предварительные требования
- Python 3.11 или выше
- PostgreSQL 15
- Git для клонирования репозитория

### Шаги по запуску

1. Клонируйте репозиторий:
   ```bash
   git clone <URL репозитория>
   cd otus-highload/lesson-01
   ```

2. Создайте и активируйте виртуальное окружение:
   ```bash
   python -m venv venv
   # Для Windows
   venv\Scripts\activate
   # Для Linux/Mac
   source venv/bin/activate
   ```

3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

4. Создайте базу данных в PostgreSQL:
   ```bash
   createdb social_network
   ```

5. Примените схему базы данных:
   ```bash
   psql -d social_network -f schema.sql
   ```

6. Настройте переменные окружения (опционально):
   ```bash
   # Для Windows
   set DB_HOST=localhost
   set DB_PORT=5432
   set DB_NAME=social_network
   set DB_USER=postgres
   set DB_PASSWORD=postgres
   
   # Для Linux/Mac
   export DB_HOST=localhost
   export DB_PORT=5432
   export DB_NAME=social_network
   export DB_USER=postgres
   export DB_PASSWORD=postgres
   ```

7. Запустите приложение:
   ```bash
   uvicorn main:app --reload
   ```

8. API будет доступно по адресу: http://localhost:8000
9. Документация API (Swagger UI): http://localhost:8000/docs

## Тестирование API с помощью Postman

1. Импортируйте коллекцию из файла `postman/social_network_api.json` в Postman
2. Создайте окружение в Postman с переменными:
   - `token` (будет заполняться автоматически после авторизации)
   - `user_id` (будет заполняться автоматически после регистрации)
3. Выполните запросы в следующем порядке:
   - Регистрация пользователя
   - Авторизация
   - Получение анкеты пользователя

## Тестирование API с помощью newman

1. Установите пакет newman:
   ```bash
   npm install -g newman
   ```
2. Выполните запуск тестов с помощью newman:
   ```bash
   newman run ./"postman/Social Network API.postman_collection.json"
   ```

## Примечания

- Для упрощения в данной реализации не используются индексы, репликация, шардирование и кэширование
- Приложение представляет монолит без использования ORM
- Для хранения паролей используется простое хеширование SHA-256