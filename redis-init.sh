#!/bin/sh

# Запускаем Redis сервер в фоне
redis-server /usr/local/etc/redis/redis.conf &

# Ждем, пока Redis запустится
echo "Ожидание запуска Redis..."
sleep 5

# Проверяем доступность Redis
until redis-cli ping > /dev/null 2>&1; do
    echo "Redis еще не готов, ждем..."
    sleep 2
done

echo "Redis запущен, загружаем UDF функции..."

# Загружаем UDF функции
redis-cli FUNCTION LOAD "$(cat /usr/local/etc/redis/redis_udf.lua)"

if [ $? -eq 0 ]; then
    echo "✅ UDF функции успешно загружены"
    # Проверяем загруженные функции
    echo "Список загруженных функций:"
    redis-cli FUNCTION LIST
else
    echo "❌ Ошибка загрузки UDF функций"
    exit 1
fi

# Переводим Redis в foreground режим
wait 