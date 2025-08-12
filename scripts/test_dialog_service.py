#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import sys

# Добавляем текущую директорию в путь
sys.path.insert(0, '/app')

async def test_dialog_service():
    print("=== ТЕСТ СЕРВИСА ДИАЛОГОВ ===")
    print(f"DIALOG_BACKEND: {os.getenv('DIALOG_BACKEND', 'НЕ УСТАНОВЛЕНА')}")
    
    try:
        # Импортируем конфигурацию
        from config import config
        print(f"config.DIALOG_BACKEND: {config.DIALOG_BACKEND}")
        print(f"config.is_redis_backend(): {config.is_redis_backend()}")
        
        # Импортируем и инициализируем сервис диалогов
        from dialog_service import dialog_service
        print("Сервис диалогов импортирован успешно")
        
        # Инициализируем сервис
        print("Инициализация сервиса диалогов...")
        await dialog_service.init()
        print("Сервис диалогов инициализирован успешно")
        
        # Закрываем соединения
        await dialog_service.close()
        print("Соединения закрыты")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("===========================")

if __name__ == "__main__":
    asyncio.run(test_dialog_service()) 