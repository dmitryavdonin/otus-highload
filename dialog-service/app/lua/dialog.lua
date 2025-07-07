-- /dialog-service/app/lua/dialog.lua

-- Этот скрипт содержит UDF (User Defined Functions) для атомарной работы
-- с диалогами в Redis.

-- Диспетчер команд: вызывает нужную функцию на основе первого аргумента.
local command = ARGV[1]

---
-- Команда 'save_message'
-- Атомарно сохраняет сообщение в Sorted Set и обновляет TTL диалога.
--
-- @param KEYS[1]   - ключ диалога (например, 'dialog:user1:user2')
-- @param ARGV[2]   - данные сообщения в формате JSON
-- @param ARGV[3]   - score (timestamp) для сортировки сообщений
-- @param ARGV[4]   - время жизни ключа в секундах (TTL)
-- @return 'OK'
---
if command == 'save_message' then
    local dialog_key = KEYS[1]
    local message_data = ARGV[2]
    local score = ARGV[3]
    local ttl = ARGV[4]

    -- Добавляем сообщение в отсортированное множество
    redis.call('ZADD', dialog_key, score, message_data)
    
    -- Устанавливаем или обновляем время жизни для всего диалога
    redis.call('EXPIRE', dialog_key, ttl)
    
    return 'OK'
end

---
-- Команда 'get_messages'
-- Атомарно получает сообщения из диалога с пагинацией.
--
-- @param KEYS[1]   - ключ диалога
-- @param ARGV[2]   - смещение (offset) для пагинации
-- @param ARGV[3]   - лимит (limit) на количество сообщений
-- @return table    - список сообщений в формате JSON
---
if command == 'get_messages' then
    local dialog_key = KEYS[1]
    local offset = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    
    -- Конечный индекс для команды ZRANGE (включительно)
    local end_index = offset + limit - 1

    -- Получаем сообщения из Sorted Set в указанном диапазоне
    return redis.call('ZRANGE', dialog_key, offset, end_index)
end

-- Если команда не найдена, возвращаем ошибку
return redis.error_reply("Unknown command: " .. tostring(command)) 