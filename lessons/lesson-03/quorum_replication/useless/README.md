# Кворумная репликация PostgreSQL

Этот каталог содержит все артефакты, связанные с настройкой и тестированием кворумной репликации PostgreSQL.

## Содержимое

### Конфигурационные файлы
- `docker-compose-quorum.yml` - Docker Compose файл для запуска кластера PostgreSQL с кворумной репликацией
- `docker-compose-quorum-simple.yml` - Упрощенная версия Docker Compose файла
- `init-master-quorum.sh` - Скрипт инициализации мастер-узла
- `init-slave-quorum.sh` - Скрипт инициализации слейв-узлов

### Скрипты тестирования
- `test_quorum_sync.sh` - Тестирование синхронной кворумной репликации
- `test_quorum_replication.sh` - Базовое тестирование кворумной репликации
- `test_quorum_replication_improved.sh` - Улучшенная версия тестирования кворумной репликации
- `test_quorum_failover.sh` - Тестирование отказоустойчивости при переключении мастера
- `test_pg_quorum_replication.sh` - Тестирование нативной кворумной репликации PostgreSQL
- `load_test_quorum.py` - Python-скрипт для нагрузочного тестирования

### Документация
- `quorum_replication_guide.md` - Руководство по настройке кворумной репликации
- `quorum_sync_replication_guide.md` - Руководство по настройке синхронной кворумной репликации
- `quorum_replication_troubleshooting.md` - Руководство по устранению неполадок
- `quorum_replication_report.html` - Отчет о тестировании кворумной репликации

## Использование

Для запуска кластера с кворумной репликацией:

```bash
docker-compose -f docker-compose-quorum.yml down -v
docker-compose -f docker-compose-quorum.yml up -d
```

Для тестирования кворумной репликации:

```bash
./test_quorum_replication.sh
```

Для тестирования отказоустойчивости:

```bash
./test_quorum_failover.sh
```

## Особенности кворумной репликации

Кворумная репликация в PostgreSQL позволяет настроить синхронную репликацию с подтверждением от определенного количества слейвов. Это обеспечивает баланс между надежностью и производительностью.

Ключевая настройка: `synchronous_standby_names = 'ANY 2 (slave1, slave2, slave3)'`

Эта настройка требует подтверждения от любых двух из трех слейвов, что позволяет кластеру продолжать работать даже при отказе одного из слейвов.
