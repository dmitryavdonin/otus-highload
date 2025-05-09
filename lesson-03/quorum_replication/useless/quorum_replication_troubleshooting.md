# Устранение неполадок при кворумной репликации PostgreSQL

## Проблема: Зависание вставки данных после промоута слейва до мастера

### Симптомы
После промоута слейва до мастера (например, pg-slave1) и переключения оставшегося слейва (pg-slave2) на новый мастер, попытки вставить данные в таблицу на новом мастере зависают и не завершаются.

### Причина
Основная причина проблемы заключается в настройке `synchronous_standby_names` на новом мастере. После промоута слейва до мастера, эта настройка остается прежней - `ANY 2 (slave1, slave2, slave3)`. Однако, поскольку slave1 теперь является мастером, а не слейвом, PostgreSQL ждет подтверждения от двух из трех слейвов, но один из них (slave1) больше не является слейвом.

В результате, PostgreSQL ждет подтверждения от двух слейвов, но подключен только один (slave2), поэтому транзакция зависает.

### Решение

После промоута слейва до мастера необходимо обновить настройку `synchronous_standby_names` на новом мастере, чтобы она соответствовала текущей конфигурации кластера.

Например, если slave1 был промоутирован до мастера, и к нему подключен только slave2, то настройка должна быть изменена на:

```sql
ALTER SYSTEM SET synchronous_standby_names = 'ANY 1 (slave2)';
```

Если slave2 был промоутирован до мастера, и к нему подключен только slave1, то настройка должна быть изменена на:

```sql
ALTER SYSTEM SET synchronous_standby_names = 'ANY 1 (slave1)';
```

После изменения настройки необходимо перезагрузить конфигурацию PostgreSQL:

```bash
pg_ctl reload -D /var/lib/postgresql/data
```

### Проверка

Чтобы убедиться, что настройка применилась, можно выполнить:

```sql
SHOW synchronous_standby_names;
```

Чтобы проверить статус репликации:

```sql
SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;
```

## Рекомендации для предотвращения проблемы

1. Всегда обновляйте настройку `synchronous_standby_names` после промоута слейва до мастера.
2. Включите в скрипт автоматического переключения шаг для обновления этой настройки.
3. Мониторьте статус репликации после переключения, чтобы убедиться, что все работает корректно.
4. Тестируйте процедуру переключения регулярно, чтобы быть уверенным, что она работает правильно.

## Пример обновленного скрипта переключения

```bash
# Промоут слейва до мастера
docker exec -u postgres pg-slave1 pg_ctl promote -D /var/lib/postgresql/data

# Ожидание завершения промоута
sleep 5

# Обновление настройки синхронной репликации на новом мастере
docker exec -u postgres pg-slave1 psql -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 1 (slave2)';"
docker exec -u postgres pg-slave1 pg_ctl reload -D /var/lib/postgresql/data

# Переключение оставшегося слейва на новый мастер
docker exec -u postgres pg-slave2 psql -c "ALTER SYSTEM SET primary_conninfo = 'host=pg-slave1 port=5432 user=postgres password=postgres application_name=slave2';"
docker exec -u postgres pg-slave2 pg_ctl reload -D /var/lib/postgresql/data
```

## Восстановление полного кластера

При восстановлении полного кластера (с тремя слейвами) после переключения, необходимо обновить настройку `synchronous_standby_names` на новом мастере, чтобы она включала всех слейвов:

```sql
ALTER SYSTEM SET synchronous_standby_names = 'ANY 2 (master, slave2, slave3)';
```

Где `master` - это имя приложения для старого мастера, который теперь является слейвом нового мастера.
