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