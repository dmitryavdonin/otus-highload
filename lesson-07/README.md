# Тестирование производительности диалогов: PostgreSQL vs Redis UDF

Данная инструкция описывает пошаговый процесс тестирования производительности операций с диалогами для сравнения PostgreSQL и Redis UDF.

### Шаг 1: Подготовка окружения

```bash
# Перейдите в корневую директорию проекта
cd /path/to/otus-highload

# Убедитесь, что все скрипты исполняемые
chmod +x *.sh
```

### Шаг 2: Тестирование PostgreSQL

```bash
# 3.1 Запустите сервисы с PostgreSQL
./start_service.sh --backend postgresql

# Дождитесь полного запуска всех сервисов (около 30-60 секунд)
# Проверьте доступность: curl http://localhost:9000/health

# 3.2 Запустите тест PostgreSQL
./test_dialogs_postgres.sh

# Результат будет сохранен в: lesson-07/dialog_metrics_postgresql.json
```

### Шаг 3: Переключение на Redis UDF

```bash
# 4.1 Остановите текущие сервисы
./stop_service.sh

# 4.2 Запустите сервисы с Redis UDF
./start_service.sh --backend redis

# Дождитесь полного запуска всех сервисов (около 30-60 секунд)
```

### Шаг 4: Тестирование Redis UDF

```bash
# Запустите тест Redis UDF
./test_dialogs_redis.sh

# Результат будет сохранен в: lesson-07/dialog_metrics_redis_udf.json
```

### Шаг 5: Генерация отчета

```bash
# Сгенерируйте HTML отчет сравнения
python3 dialog_comparison_report.py

# Отчет будет создан: lesson-07/dialog_performance_comparison.html
```

## 📊 Параметры тестирования

По умолчанию тестирование выполняется со следующими параметрами:

- **Пользователи**: 40
- **Сообщений в диалоге**: 20  
- **Диалогов на пользователя**: 10
- **Общее количество сообщений**: 8,000
- **Общее количество операций чтения**: 400

## 📁 Структура результатов

После выполнения всех тестов в папке `lesson-07/` будут созданы:

```
lesson-07/
├── dialog_metrics_postgresql.json    # Метрики PostgreSQL
├── dialog_metrics_redis_udf.json     # Метрики Redis UDF  
├── dialog_performance_comparison.html # HTML отчет
└── README.md                         # Данная инструкция
```