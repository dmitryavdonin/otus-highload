# PostgreSQL Кворумная Синхронная Репликация - Руководство

Это руководство описывает настройку кворумной синхронной репликации PostgreSQL с одним мастером и тремя репликами, а также процедуру восстановления при отказе.

## Архитектура

- 1 мастер (pg-master)
- 3 слейва (pg-slave1, pg-slave2, pg-slave3)
- Кворумная синхронная репликация (требуется подтверждение от любых 2 из 3 слейвов)

## Файлы конфигурации

### docker-compose-quorum-simple.yml

Файл Docker Compose для запуска кластера PostgreSQL с одним мастером и тремя слейвами:

```yaml
version: '3'

services:
  master:
    image: postgres:15
    container_name: pg-master
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: testdb
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - "5432:5432"
    volumes:
      - ./pg-master-data:/var/lib/postgresql/data
      - ./init-master.sh:/docker-entrypoint-initdb.d/init-master.sh
    networks:
      - postgres-network

  slave1:
    image: postgres:15
    container_name: pg-slave1
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: testdb
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - "5433:5432"
    volumes:
      - ./pg-slave1-data:/var/lib/postgresql/data
      - ./init-slave1.sh:/docker-entrypoint-initdb.d/init-slave1.sh
    depends_on:
      - master
    networks:
      - postgres-network

  slave2:
    image: postgres:15
    container_name: pg-slave2
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: testdb
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - "5434:5432"
    volumes:
      - ./pg-slave2-data:/var/lib/postgresql/data
      - ./init-slave2.sh:/docker-entrypoint-initdb.d/init-slave2.sh
    depends_on:
      - master
    networks:
      - postgres-network

  slave3:
    image: postgres:15
    container_name: pg-slave3
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: testdb
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - "5435:5432"
    volumes:
      - ./pg-slave3-data:/var/lib/postgresql/data
      - ./init-slave3.sh:/docker-entrypoint-initdb.d/init-slave3.sh
    depends_on:
      - master
    networks:
      - postgres-network

networks:
  postgres-network:
    driver: bridge
```

### init-master.sh

Скрипт инициализации мастера:

```bash
#!/bin/bash
set -e

# Настройка PostgreSQL для прослушивания всех интерфейсов
cat >> /var/lib/postgresql/data/postgresql.conf << EOF
listen_addresses = '*'
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
synchronous_commit = on
synchronous_standby_names = 'ANY 2 (slave1, slave2, slave3)'
EOF

# Настройка доступа для репликации
cat >> /var/lib/postgresql/data/pg_hba.conf << EOF
host replication postgres all md5
host all postgres all md5
EOF

# Создание тестовой таблицы
psql -U postgres -d testdb << EOF
CREATE TABLE test_table (id SERIAL PRIMARY KEY, data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
EOF

# Создание слотов репликации
psql -U postgres << EOF
SELECT pg_create_physical_replication_slot('slave1_slot');
SELECT pg_create_physical_replication_slot('slave2_slot');
SELECT pg_create_physical_replication_slot('slave3_slot');
EOF
```

### init-slave1.sh (аналогично для init-slave2.sh и init-slave3.sh)

Скрипт инициализации слейва:

```bash
#!/bin/bash
set -e

# Ожидание доступности мастера
until pg_isready -h master -p 5432 -U postgres; do
    echo "Waiting for master to be ready..."
    sleep 1
done

# Остановка PostgreSQL
pg_ctl -D /var/lib/postgresql/data -m fast -w stop

# Очистка директории данных
rm -rf /var/lib/postgresql/data/*

# Создание базового бэкапа
pg_basebackup -h master -p 5432 -U postgres -D /var/lib/postgresql/data -P -R -X stream -S slave1_slot

# Настройка репликации
cat > /var/lib/postgresql/data/postgresql.auto.conf << EOF
primary_conninfo = 'host=master port=5432 user=postgres password=postgres application_name=slave1'
primary_slot_name = 'slave1_slot'
EOF

# Создание файла standby.signal
touch /var/lib/postgresql/data/standby.signal

# Запуск PostgreSQL
pg_ctl -D /var/lib/postgresql/data -w start
```

## Запуск кластера

```bash
# Удаление старых контейнеров и данных
docker rm -f pg-master pg-slave1 pg-slave2 pg-slave3
rm -rf pg-master-data pg-slave1-data pg-slave2-data pg-slave3-data

# Запуск кластера
docker-compose -f docker-compose-quorum-simple.yml down -v
docker-compose -f docker-compose-quorum-simple.yml up -d
```

## Проверка статуса репликации

```bash
docker exec pg-master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"
```

Ожидаемый результат:
```
 application_name | sync_state | sync_priority
-----------------+------------+---------------
 slave1          | quorum     |             1
 slave2          | quorum     |             1
 slave3          | quorum     |             1
```

## Тестирование отказоустойчивости

### Сценарий 1: Отказ одного слейва

1. Проверка начального состояния:
   ```bash
   docker exec pg-master psql -U postgres -d testdb -c "SELECT COUNT(*) FROM test_table;"
   ```

2. Остановка одного слейва:
   ```bash
   docker stop pg-slave3
   ```

3. Проверка статуса репликации:
   ```bash
   docker exec pg-master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"
   ```

4. Вставка новых данных:
   ```bash
   docker exec pg-master psql -U postgres -d testdb -c "INSERT INTO test_table (data) SELECT 'test data ' || generate_series(101, 200);"
   ```

5. Проверка количества записей:
   ```bash
   docker exec pg-master psql -U postgres -d testdb -c "SELECT COUNT(*) FROM test_table;"
   ```

### Сценарий 2: Отказ мастера

1. Остановка мастера:
   ```bash
   docker stop pg-master
   ```

2. Проверка LSN на оставшихся слейвах:
   ```bash
   docker exec pg-slave1 psql -U postgres -c "SELECT pg_last_wal_receive_lsn();"
   docker exec pg-slave2 psql -U postgres -c "SELECT pg_last_wal_receive_lsn();"
   ```

3. Промоут одного из слейвов до мастера:
   ```bash
   docker exec -u postgres pg-slave1 pg_ctl promote -D /var/lib/postgresql/data
   ```

4. Настройка оставшегося слейва для подключения к новому мастеру:
   ```bash
   docker exec -u postgres pg-slave2 psql -c "ALTER SYSTEM SET primary_conninfo = 'host=pg-slave1 port=5432 user=postgres password=postgres application_name=slave2';"
   docker exec -u postgres pg-slave2 pg_ctl reload -D /var/lib/postgresql/data
   ```

5. Создание слота репликации на новом мастере:
   ```bash
   docker exec pg-slave1 psql -U postgres -c "SELECT * FROM pg_create_physical_replication_slot('slave2_slot');"
   ```

6. Перезапуск слейва:
   ```bash
   docker restart pg-slave2
   ```

7. Проверка статуса репликации на новом мастере:
   ```bash
   docker exec pg-slave1 psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"
   ```

8. Проверка данных на новом мастере и слейве:
   ```bash
   docker exec pg-slave1 psql -U postgres -d testdb -c "SELECT COUNT(*) FROM test_table;"
   docker exec pg-slave2 psql -U postgres -d testdb -c "SELECT COUNT(*) FROM test_table;"
   ```

## Восстановление полного кластера

После отказа мастера и промоута одного из слейвов, для восстановления полного кластера с тремя слейвами необходимо:

1. Восстановить старый мастер как слейв нового мастера:
   ```bash
   # Запуск старого мастера
   docker start pg-master
   
   # Остановка PostgreSQL на старом мастере
   docker exec -u postgres pg-master pg_ctl -D /var/lib/postgresql/data -m fast -w stop
   
   # Очистка директории данных
   docker exec -u postgres pg-master rm -rf /var/lib/postgresql/data/*
   
   # Создание базового бэкапа с нового мастера
   docker exec -u postgres pg-master pg_basebackup -h pg-slave1 -p 5432 -U postgres -D /var/lib/postgresql/data -P -R -X stream -S master_slot
   
   # Настройка репликации
   docker exec -u postgres pg-master bash -c "cat > /var/lib/postgresql/data/postgresql.auto.conf << EOF
   primary_conninfo = 'host=pg-slave1 port=5432 user=postgres password=postgres application_name=master'
   primary_slot_name = 'master_slot'
   EOF"
   
   # Создание файла standby.signal
   docker exec -u postgres pg-master touch /var/lib/postgresql/data/standby.signal
   
   # Запуск PostgreSQL
   docker exec -u postgres pg-master pg_ctl -D /var/lib/postgresql/data -w start
   ```

2. Восстановить третий слейв:
   ```bash
   # Запуск третьего слейва
   docker start pg-slave3
   
   # Остановка PostgreSQL на третьем слейве
   docker exec -u postgres pg-slave3 pg_ctl -D /var/lib/postgresql/data -m fast -w stop
   
   # Очистка директории данных
   docker exec -u postgres pg-slave3 rm -rf /var/lib/postgresql/data/*
   
   # Создание базового бэкапа с нового мастера
   docker exec -u postgres pg-slave3 pg_basebackup -h pg-slave1 -p 5432 -U postgres -D /var/lib/postgresql/data -P -R -X stream -S slave3_slot
   
   # Настройка репликации
   docker exec -u postgres pg-slave3 bash -c "cat > /var/lib/postgresql/data/postgresql.auto.conf << EOF
   primary_conninfo = 'host=pg-slave1 port=5432 user=postgres password=postgres application_name=slave3'
   primary_slot_name = 'slave3_slot'
   EOF"
   
   # Создание файла standby.signal
   docker exec -u postgres pg-slave3 touch /var/lib/postgresql/data/standby.signal
   
   # Запуск PostgreSQL
   docker exec -u postgres pg-slave3 pg_ctl -D /var/lib/postgresql/data -w start
   ```

3. Настройка кворумной репликации на новом мастере:
   ```bash
   docker exec -u postgres pg-slave1 psql -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 2 (master, slave2, slave3)';"
   docker exec -u postgres pg-slave1 pg_ctl reload -D /var/lib/postgresql/data
   ```

4. Проверка статуса репликации:
   ```bash
   docker exec pg-slave1 psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"
   ```

## Заключение

Кворумная синхронная репликация PostgreSQL обеспечивает высокую доступность и надежность данных. При настройке `synchronous_standby_names = 'ANY 2 (slave1, slave2, slave3)'` транзакция считается подтвержденной, когда она записана на диск мастера и подтверждена любыми двумя из трех слейвов.

Это позволяет:
1. Продолжать работу при отказе одного слейва
2. Гарантировать отсутствие потери данных при отказе мастера
3. Обеспечивать высокую доступность системы

При отказе мастера один из слейвов может быть промоутирован до мастера, а остальные слейвы переключены на него, что обеспечивает непрерывность работы системы.
