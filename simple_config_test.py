#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from enum import Enum

class DialogBackend(Enum):
    """Типы бэкендов для диалогов"""
    POSTGRESQL = "postgresql"
    REDIS = "redis"

# Прямая проверка переменной окружения
dialog_backend_str = os.getenv("DIALOG_BACKEND", "postgresql")
print(f"DIALOG_BACKEND env var: {dialog_backend_str}")

try:
    dialog_backend = DialogBackend(dialog_backend_str)
    print(f"DialogBackend enum: {dialog_backend}")
    print(f"Is Redis backend: {dialog_backend == DialogBackend.REDIS}")
    print(f"Is PostgreSQL backend: {dialog_backend == DialogBackend.POSTGRESQL}")
except ValueError as e:
    print(f"Ошибка создания enum: {e}")

print("=====================================") 