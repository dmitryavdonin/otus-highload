"""
Redis адаптер для диалогов с использованием UDF (User Defined Functions)
Оптимизированная версия с серверными функциями Redis
"""

import json
import uuid
import traceback
from datetime import datetime
from typing import List, Dict, Optional
import redis.asyncio as redis
from packages.common.models import DialogMessageResponse


class RedisDialogAdapterUDF:
    """
    Адаптер для работы с диалогами в Redis с использованием UDF функций
    """
    
    def __init__(self, redis_url: str):
        """
        Инициализация адаптера
        
        Args:
            redis_url: URL для подключения к Redis
        """
        print(f"🔧 Инициализация Redis UDF адаптера с URL: {redis_url}")
        self.redis_url = redis_url
        self.redis_client = None
        
    async def connect(self):
        """Подключение к Redis"""
        print(f"🔗 Подключение к Redis: {self.redis_url}")
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        
        # Проверяем подключение
        await self.redis_client.ping()
        print("✅ Подключение к Redis установлено")
        
        # Проверяем наличие UDF функций
        await self._verify_udf_functions()
        
    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print("🔌 Соединение с Redis закрыто")
    
    async def _verify_udf_functions(self):
        """Проверка наличия UDF функций"""
        try:
            functions = await self.redis_client.function_list()
            print(f"🔍 Отладка: function_list() вернул: {functions}")
            
            if not functions:
                raise Exception("UDF функции не загружены в Redis")
            
            # Проверяем наличие нужных функций
            required_functions = [
                'save_message', 'get_messages', 'get_recent_messages',
                'get_message_count', 'get_dialog_stats', 'delete_dialog'
            ]
            
            loaded_functions = []
            
            # Обрабатываем результат function_list
            # Формат: [['library_name', 'dialog_functions', 'engine', 'LUA', 'functions', [функции...]]]
            if isinstance(functions, list) and len(functions) > 0:
                for lib_data in functions:
                    print(f"🔍 Отладка: обрабатываем библиотеку: {lib_data}")
                    if isinstance(lib_data, list) and len(lib_data) >= 6:
                        # Ищем индекс 'functions' в списке
                        try:
                            functions_index = lib_data.index('functions')
                            if functions_index + 1 < len(lib_data):
                                functions_list = lib_data[functions_index + 1]
                                print(f"🔍 Отладка: список функций: {functions_list}")
                                
                                if isinstance(functions_list, list):
                                    for func_data in functions_list:
                                        if isinstance(func_data, list) and len(func_data) >= 2:
                                            # Ищем индекс 'name' в списке функции
                                            try:
                                                name_index = func_data.index('name')
                                                if name_index + 1 < len(func_data):
                                                    func_name = func_data[name_index + 1]
                                                    loaded_functions.append(func_name)
                                                    print(f"🔍 Найдена функция: {func_name}")
                                            except ValueError:
                                                continue
                        except ValueError:
                            continue
            
            print(f"🔍 Отладка: найденные функции: {loaded_functions}")
            
            missing_functions = [f for f in required_functions if f not in loaded_functions]
            if missing_functions:
                raise Exception(f"Отсутствуют UDF функции: {missing_functions}")
                
            print(f"✅ UDF функции проверены: {loaded_functions}")
            
        except Exception as e:
            print(f"❌ Ошибка проверки UDF функций: {e}")
            import traceback
            print(f"🔍 Трассировка: {traceback.format_exc()}")
            raise
    
    def _get_dialog_key(self, user_id1: str, user_id2: str) -> str:
        """
        Генерация ключа диалога. Всегда в одном порядке для консистентности.
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            Ключ диалога в формате dialog:{smaller_id}:{larger_id}
        """
        # Преобразуем в строки для обработки UUID объектов из PostgreSQL
        id1_str = str(user_id1)
        id2_str = str(user_id2)
        
        print(f"🔍 DEBUG: _get_dialog_key вызван с user_id1={user_id1} (тип: {type(user_id1)}), user_id2={user_id2} (тип: {type(user_id2)})")
        print(f"🔍 DEBUG: Преобразованы в строки: id1_str={id1_str}, id2_str={id2_str}")
        
        # Сортируем ID для консистентности ключей
        ids = sorted([id1_str, id2_str])
        dialog_key = f"dialog:{ids[0]}:{ids[1]}"
        
        print(f"🔍 DEBUG: Сгенерированный ключ диалога: {dialog_key}")
        return dialog_key
    
    def _message_to_dict(self, message_id: str, from_user_id: str, to_user_id: str, 
                        text: str, created_at: datetime) -> Dict:
        """Преобразование сообщения в словарь для хранения в Redis"""
        return {
            "id": message_id,
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "text": text,
            "created_at": created_at.isoformat()
        }
    
    def _dict_to_message_response(self, message_dict: Dict) -> DialogMessageResponse:
        """Преобразование словаря из Redis в объект ответа"""
        return DialogMessageResponse(
            from_user_id=message_dict["from_user_id"],
            to_user_id=message_dict["to_user_id"],
            text=message_dict["text"],
            created_at=datetime.fromisoformat(message_dict["created_at"])
        )
    
    async def save_dialog_message(self, from_user_id: str, to_user_id: str, text: str) -> str:
        """
        Сохранение сообщения в Redis с использованием UDF
        
        Args:
            from_user_id: ID отправителя
            to_user_id: ID получателя
            text: Текст сообщения
            
        Returns:
            ID созданного сообщения
        """
        message_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        # Создаем объект сообщения
        message_data = self._message_to_dict(
            message_id, from_user_id, to_user_id, text, created_at
        )
        
        # Получаем ключ диалога
        dialog_key = self._get_dialog_key(from_user_id, to_user_id)
        
        # Используем timestamp как score для автоматической сортировки
        timestamp_score = created_at.timestamp()
        
        # Вызываем UDF функцию для сохранения
        await self.redis_client.fcall(
            'save_message',
            1,  # количество ключей
            dialog_key,  # ключ
            json.dumps(message_data),  # данные сообщения
            str(timestamp_score),  # timestamp как score
            str(30 * 24 * 60 * 60)  # TTL в секундах (30 дней)
        )
        
        return message_id
    
    async def get_dialog_messages(self, user_id1: str, user_id2: str, 
                                 limit: int = 100, offset: int = 0) -> List[DialogMessageResponse]:
        """
        Получение сообщений диалога из Redis с использованием UDF
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            limit: Максимальное количество сообщений
            offset: Смещение для пагинации
            
        Returns:
            Список сообщений диалога
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        
        # Вызываем UDF функцию для получения сообщений
        messages_data = await self.redis_client.fcall(
            'get_messages',
            1,  # количество ключей
            dialog_key,  # ключ
            str(offset),  # смещение
            str(limit)   # лимит
        )
        
        # Преобразуем JSON-строки обратно в объекты
        messages = []
        for message_json in messages_data:
            try:
                message_dict = json.loads(message_json)
                message_response = self._dict_to_message_response(message_dict)
                messages.append(message_response)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Ошибка парсинга сообщения: {e}")
                continue
        
        return messages
    
    async def get_dialog_messages_count(self, user_id1: str, user_id2: str) -> int:
        """
        Получение количества сообщений в диалоге с использованием UDF
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            Количество сообщений в диалоге
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        
        # Вызываем UDF функцию
        count = await self.redis_client.fcall(
            'get_message_count',
            1,  # количество ключей
            dialog_key  # ключ
        )
        
        return int(count)
    
    async def get_recent_dialog_messages(self, user_id1: str, user_id2: str, 
                                       limit: int = 50) -> List[DialogMessageResponse]:
        """
        Получение последних сообщений диалога с использованием UDF
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            limit: Количество последних сообщений
            
        Returns:
            Список последних сообщений
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        
        # Вызываем UDF функцию
        messages_data = await self.redis_client.fcall(
            'get_recent_messages',
            1,  # количество ключей
            dialog_key,  # ключ
            str(limit)   # лимит
        )
        
        # Преобразуем в объекты ответа
        messages = []
        for message_json in messages_data:
            try:
                message_dict = json.loads(message_json)
                message_response = self._dict_to_message_response(message_dict)
                messages.append(message_response)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Ошибка парсинга сообщения: {e}")
                continue
        
        return messages
    
    async def delete_dialog(self, user_id1: str, user_id2: str) -> bool:
        """
        Удаление всего диалога с использованием UDF
        
        Args:
            user_id1: ID первого пользователя
            user_id2: ID второго пользователя
            
        Returns:
            True если диалог был удален, False если диалога не было
        """
        dialog_key = self._get_dialog_key(user_id1, user_id2)
        
        # Вызываем UDF функцию
        deleted_count = await self.redis_client.fcall(
            'delete_dialog',
            1,  # количество ключей
            dialog_key  # ключ
        )
        
        return int(deleted_count) > 0
    
    async def get_dialog_stats(self) -> Dict:
        """
        Получение статистики по диалогам в Redis с использованием UDF
        
        Returns:
            Словарь со статистикой
        """
        # Вызываем UDF функцию
        stats = await self.redis_client.fcall(
            'get_dialog_stats',
            0,  # количество ключей
            'dialog:*'  # паттерн для поиска
        )
        
        return {
            "total_dialogs": int(stats[0]),
            "total_messages": int(stats[1]),
            "avg_messages_per_dialog": float(stats[2])
        }


# Глобальный экземпляр адаптера
redis_dialog_adapter_udf = None


def get_redis_dialog_adapter_udf():
    """Получение глобального экземпляра UDF адаптера"""
    global redis_dialog_adapter_udf
    print(f"🔍 DEBUG: get_redis_dialog_adapter_udf() вызван")
    print(f"🔍 DEBUG: Значение redis_dialog_adapter_udf: {redis_dialog_adapter_udf}")
    print(f"🔍 DEBUG: Тип redis_dialog_adapter_udf: {type(redis_dialog_adapter_udf)}")
    
    if redis_dialog_adapter_udf is None:
        print(f"❌ DEBUG: Redis UDF adapter не инициализирован!")
        raise Exception("Redis UDF adapter не инициализирован")
    
    print(f"✅ DEBUG: Возвращаем адаптер: {redis_dialog_adapter_udf}")
    return redis_dialog_adapter_udf


async def init_redis_adapter_udf(redis_url: str):
    """Инициализация Redis UDF адаптера"""
    print(f"🔍 ОТЛАДКА: init_redis_adapter_udf() вызван с redis_url={redis_url}")
    print(f"🔍 СТЕК ВЫЗОВОВ:\n{''.join(traceback.format_stack())}")
    
    global redis_dialog_adapter_udf
    print(f"🔧 Инициализация Redis UDF адаптера с URL: {redis_url}")
    print(f"🔍 Отладка: переданный redis_url = {redis_url}")
    print(f"🔍 DEBUG: Значение redis_dialog_adapter_udf ДО инициализации: {redis_dialog_adapter_udf}")
    
    redis_dialog_adapter_udf = RedisDialogAdapterUDF(redis_url)
    print(f"🔍 DEBUG: Создан объект адаптера: {redis_dialog_adapter_udf}")
    
    await redis_dialog_adapter_udf.connect()
    print(f"🔍 DEBUG: Адаптер подключен к Redis")
    print(f"🔍 DEBUG: Значение redis_dialog_adapter_udf ПОСЛЕ инициализации: {redis_dialog_adapter_udf}")
    print(f"✅ Redis UDF адаптер инициализирован с URL: {redis_url}")


async def close_redis_adapter_udf():
    """Закрытие соединения с Redis UDF адаптером"""
    global redis_dialog_adapter_udf
    if redis_dialog_adapter_udf:
        await redis_dialog_adapter_udf.disconnect() 