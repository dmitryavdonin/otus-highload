#!/bin/bash

# Скрипт для запуска тестов WebSocket сервера

echo "🧪 Запуск тестов WebSocket сервера..."

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено"
    echo "💡 Запустите сначала: ./start_service.sh"
    exit 1
fi

# Активируем виртуальное окружение
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Проверяем наличие необходимых модулей
echo "📦 Проверка зависимостей..."
python -c "import websockets, aiohttp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Отсутствуют необходимые модули"
    echo "📚 Установка зависимостей..."
    pip install websockets aiohttp
fi

# Запускаем тесты
echo "🚀 Запуск тестов..."
python test_websocket_simple.py

echo "✅ Тесты завершены" 