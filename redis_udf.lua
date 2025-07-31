#!lua name=dialog_functions

-- Функция для сохранения сообщения в диалог
local function save_message(keys, args)
    local dialog_key = keys[1]
    local message_data = args[1]
    local timestamp = tonumber(args[2])
    local ttl_seconds = tonumber(args[3]) or (30 * 24 * 60 * 60) -- 30 дней по умолчанию
    
    -- Добавляем сообщение в sorted set
    redis.call('ZADD', dialog_key, timestamp, message_data)
    
    -- Устанавливаем TTL только если ключ новый (не существовал)
    local exists = redis.call('EXISTS', dialog_key)
    if exists == 0 then
        redis.call('EXPIRE', dialog_key, ttl_seconds)
    end
    
    return 'OK'
end

-- Функция для получения сообщений с пагинацией
local function get_messages(keys, args)
    local dialog_key = keys[1]
    local offset = tonumber(args[1]) or 0
    local limit = tonumber(args[2]) or 100
    
    -- Получаем сообщения из sorted set
    local messages = redis.call('ZRANGE', dialog_key, offset, offset + limit - 1)
    
    return messages
end

-- Функция для получения последних сообщений
local function get_recent_messages(keys, args)
    local dialog_key = keys[1]
    local limit = tonumber(args[1]) or 50
    
    -- Получаем последние сообщения
    local messages = redis.call('ZRANGE', dialog_key, -limit, -1)
    
    return messages
end

-- Функция для получения количества сообщений в диалоге
local function get_message_count(keys, args)
    local dialog_key = keys[1]
    
    return redis.call('ZCARD', dialog_key)
end

-- Функция для получения статистики по всем диалогам
local function get_dialog_stats(keys, args)
    local pattern = args[1] or 'dialog:*'
    
    -- Получаем все ключи диалогов
    local dialog_keys = redis.call('KEYS', pattern)
    local total_dialogs = #dialog_keys
    local total_messages = 0
    
    -- Подсчитываем общее количество сообщений
    for i = 1, total_dialogs do
        local count = redis.call('ZCARD', dialog_keys[i])
        total_messages = total_messages + count
    end
    
    local avg_messages = 0
    if total_dialogs > 0 then
        avg_messages = total_messages / total_dialogs
    end
    
    return {total_dialogs, total_messages, avg_messages}
end

-- Функция для удаления диалога
local function delete_dialog(keys, args)
    local dialog_key = keys[1]
    
    return redis.call('DEL', dialog_key)
end

-- Функция для батчевого сохранения сообщений (оптимизация)
local function save_messages_batch(keys, args)
    local dialog_key = keys[1]
    local ttl_seconds = tonumber(args[1]) or (30 * 24 * 60 * 60)
    
    -- Проверяем существование ключа до операций
    local key_exists = redis.call('EXISTS', dialog_key)
    
    -- Обрабатываем пары (message_data, timestamp)
    local zadd_args = {dialog_key}
    for i = 2, #args, 2 do
        local timestamp = tonumber(args[i])
        local message_data = args[i + 1]
        table.insert(zadd_args, timestamp)
        table.insert(zadd_args, message_data)
    end
    
    -- Выполняем батчевое добавление
    if #zadd_args > 1 then
        redis.call('ZADD', unpack(zadd_args))
    end
    
    -- Устанавливаем TTL только для нового ключа
    if key_exists == 0 then
        redis.call('EXPIRE', dialog_key, ttl_seconds)
    end
    
    return (#args - 1) / 2 -- возвращаем количество добавленных сообщений
end

-- Регистрируем функции
redis.register_function('save_message', save_message)
redis.register_function('get_messages', get_messages)
redis.register_function('get_recent_messages', get_recent_messages)
redis.register_function('get_message_count', get_message_count)
redis.register_function('get_dialog_stats', get_dialog_stats)
redis.register_function('delete_dialog', delete_dialog)
redis.register_function('save_messages_batch', save_messages_batch) 