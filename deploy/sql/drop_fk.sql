-- Удаляем внешние ключи для возможности распределения таблиц
ALTER TABLE auth_tokens DROP CONSTRAINT auth_tokens_user_id_fkey;
ALTER TABLE friends DROP CONSTRAINT friends_user_id_fkey;
ALTER TABLE friends DROP CONSTRAINT friends_friend_id_fkey;
ALTER TABLE posts DROP CONSTRAINT posts_author_user_id_fkey;
ALTER TABLE posts_hot_users DROP CONSTRAINT posts_hot_users_author_user_id_fkey;
ALTER TABLE dialog_messages DROP CONSTRAINT dialog_messages_from_user_id_fkey;
ALTER TABLE dialog_messages DROP CONSTRAINT dialog_messages_to_user_id_fkey; 