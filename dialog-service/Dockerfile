FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости включая curl для healthcheck
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения, включая Lua-скрипты
COPY app/ ./app/

# Создаем не-рутового пользователя для безопасности
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

USER appuser

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открытие порта
EXPOSE 8002

# Команда запуска
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"] 