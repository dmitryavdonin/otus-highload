-- Создание обычных B-tree индексов
CREATE INDEX IF NOT EXISTS idx_users_first_name ON users(first_name);
CREATE INDEX IF NOT EXISTS idx_users_second_name ON users(second_name);

-- Создание индексов с оператором pattern_ops для поиска с LIKE 'текст%'
CREATE INDEX IF NOT EXISTS idx_users_first_name_pattern ON users(first_name varchar_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_users_second_name_pattern ON users(second_name varchar_pattern_ops);

-- Создание триграммных индексов для поиска с LIKE '%текст%'
-- Сначала нужно включить расширение pg_trgm, если оно еще не включено
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Затем создаем триграммные индексы
CREATE INDEX IF NOT EXISTS idx_users_first_name_trgm ON users USING gin (first_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_users_second_name_trgm ON users USING gin (second_name gin_trgm_ops);

-- Создание составного индекса для обоих полей
CREATE INDEX IF NOT EXISTS idx_users_names_combined ON users(first_name, second_name);

-- Проверка созданных индексов
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users';