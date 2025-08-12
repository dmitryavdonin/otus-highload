#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from config import config

print("=== ТЕСТ КОНФИГУРАЦИИ ДИАЛОГОВ ===")
print(f"DIALOG_BACKEND env var: {os.getenv('DIALOG_BACKEND', 'НЕ УСТАНОВЛЕНА')}")
print(f"config.DIALOG_BACKEND: {config.DIALOG_BACKEND}")
print(f"config.is_redis_backend(): {config.is_redis_backend()}")
print(f"config.is_postgresql_backend(): {config.is_postgresql_backend()}")
print(f"config.get_redis_url(): {config.get_redis_url()}")
print("=====================================") 