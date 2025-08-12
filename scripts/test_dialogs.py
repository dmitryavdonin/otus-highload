#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import requests
import time
import random
from datetime import datetime, timedelta
from pprint import pprint

# URL API сервера
API_URL = "http://localhost:9000"

# Проверка доступности сервиса
def check_service_availability():
    try:
        # Проверяем доступность сервиса через запрос к API без аутентификации
        response = requests.get(f"{API_URL}/docs", timeout=5)
        return True
    except requests.exceptions.RequestException as e:
        print(f"Ошибка подключения к сервису: {e}")
        print(f"Проверьте, что сервис запущен по адресу {API_URL}")
        print("Для запуска сервиса выполните команду: ./start_services.sh")
        return False

# Диагностика API запроса
def print_request_debug_info(response, error=None):
    print("=" * 50)
    print("ДИАГНОСТИКА ЗАПРОСА:")
    print(f"URL: {response.request.url}")
    print(f"Метод: {response.request.method}")
    print(f"Заголовки запроса: {response.request.headers}")
    
    try:
        body = response.request.body.decode('utf-8') if response.request.body else "Нет тела запроса"
        print(f"Тело запроса: {body}")
    except:
        print(f"Тело запроса: {response.request.body}")
    
    print(f"Код ответа: {response.status_code}")
    print(f"Заголовки ответа: {response.headers}")
    
    try:
        print(f"Тело ответа: {response.text}")
    except:
        print("Не удалось получить тело ответа")
    
    if error:
        print(f"Ошибка: {error}")
    
    print("=" * 50)

# Функция для получения имени пользователя по ID из словаря
def get_user_name_by_id(user_id, user_info):
    if user_id in user_info:
        return f"{user_info[user_id]['second_name']} {user_info[user_id]['first_name']}"
    return user_id

# Функция для регистрации пользователя
def register_user(first_name, second_name, password):
    url = f"{API_URL}/user/register"
    
    # Данные пользователя
    data = {
        "first_name": first_name,
        "second_name": second_name,
        "birthdate": (datetime.now() - timedelta(days=365 * 25)).strftime("%Y-%m-%d"),
        "biography": f"Биография пользователя {first_name} {second_name}",
        "city": "Москва",
        "password": password
    }
    
    # Отправляем запрос на регистрацию
    try:
        response = requests.post(url, json=data)
        
        user_name = f"{second_name} {first_name}"
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"Пользователь {user_name} успешно зарегистрирован с ID: {user_data['id']}")
            return user_data['id']
        else:
            print(f"Ошибка при регистрации пользователя {user_name}: {response.status_code}")
            try:
                print(response.json())
            except json.JSONDecodeError:
                print(f"Не удалось декодировать JSON ответа: {response.text}")
                print_request_debug_info(response)
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при регистрации пользователя {second_name} {first_name}: {e}")
        return None

# Функция для получения информации о пользователе
def get_user_info(token, user_id):
    url = f"{API_URL}/user/get/{user_id}"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка при получении информации о пользователе: {response.status_code}")
            try:
                print(response.json())
            except json.JSONDecodeError:
                print(f"Не удалось декодировать JSON ответа: {response.text}")
                print_request_debug_info(response)
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при получении информации о пользователе: {e}")
        return None

# Функция для авторизации пользователя
def login_user(user_id, password, user_name=""):
    url = f"{API_URL}/user/login"
    
    data = {
        "id": user_id,
        "password": password
    }
    
    try:
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            token = response.json()["token"]
            print(f"Пользователь {user_name} успешно авторизован")
            return token
        else:
            print(f"Ошибка при авторизации пользователя {user_name}: {response.status_code}")
            try:
                print(response.json())
            except json.JSONDecodeError:
                print(f"Не удалось декодировать JSON ответа: {response.text}")
                print_request_debug_info(response)
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при авторизации пользователя {user_name}: {e}")
        return None

# Функция для добавления друга
def add_friend(token, friend_id, friend_name=""):
    url = f"{API_URL}/friend/set/{friend_id}"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.put(url, headers=headers)
        
        if response.status_code == 200:
            print(f"Пользователь {friend_name} добавлен в друзья")
            return True
        else:
            print(f"Ошибка при добавлении друга {friend_name}: {response.status_code}")
            try:
                print(response.json())
            except json.JSONDecodeError:
                print(f"Не удалось декодировать JSON ответа: {response.text}")
                print_request_debug_info(response)
            return False
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при добавлении друга {friend_name}: {e}")
        return False

# Функция для отправки сообщения
def send_message(token, recipient_id, message_text, recipient_name=""):
    url = f"{API_URL}/dialog/{recipient_id}/send"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # Данные сообщения
    data = {
        "text": message_text
    }
    
    try:
        # Используем встроенный в requests функционал для работы с JSON
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            print(f"Сообщение успешно отправлено пользователю {recipient_name}")
            return True
        else:
            print(f"Ошибка при отправке сообщения пользователю {recipient_name}: {response.status_code}")
            
            # Попытка прочитать тело ответа как JSON
            try:
                error_details = response.json()
                print(f"Ошибка от сервера: {error_details}")
            except json.JSONDecodeError:
                print(f"Не удалось получить детали ошибки из ответа: {response.text}")
                print_request_debug_info(response)
            
            return False
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при отправке сообщения пользователю {recipient_name}: {e}")
        return False

# Функция для получения списка сообщений
def get_messages(token, interlocutor_id, interlocutor_name=""):
    url = f"{API_URL}/dialog/{interlocutor_id}/list"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            messages = response.json()
            print(f"Получены сообщения с пользователем {interlocutor_name}, всего сообщений: {len(messages)}")
            return messages
        else:
            print(f"Ошибка при получении списка сообщений от пользователя {interlocutor_name}: {response.status_code}")
            try:
                print(response.json())
            except json.JSONDecodeError:
                print(f"Не удалось декодировать JSON ответа: {response.text}")
                print_request_debug_info(response)
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при получении списка сообщений от пользователя {interlocutor_name}: {e}")
        return None

def print_messages(messages, user_info):
    if not messages:
        print("Нет сообщений")
        return
    
    print("\n" + "=" * 80)
    print("Список сообщений:")
    print("=" * 80)
    
    for i, msg in enumerate(messages, 1):
        from_user_id = msg['from_user_id']
        to_user_id = msg['to_user_id']
        
        from_user_name = f"{user_info.get(from_user_id, {}).get('second_name', '')} {user_info.get(from_user_id, {}).get('first_name', '')}" if from_user_id in user_info else from_user_id
        to_user_name = f"{user_info.get(to_user_id, {}).get('second_name', '')} {user_info.get(to_user_id, {}).get('first_name', '')}" if to_user_id in user_info else to_user_id
        
        print(f"{i}. От: {from_user_name} -> Кому: {to_user_name}")
        print(f"   Текст: {msg['text']}")
        print(f"   Дата: {msg['created_at']}")
        print("-" * 80)

def main():
    print("Тестирование функциональности диалогов")
    print("=" * 80)
    
    # Проверяем доступность сервиса
    if not check_service_availability():
        return
    
    # 1. Регистрация двух пользователей
    print("\nШаг 1: Регистрация пользователей")
    password1 = "password123"
    password2 = "password456"
    
    user1_first_name = "Иван"
    user1_second_name = "Иванов"
    user2_first_name = "Петр"
    user2_second_name = "Петров"
    
    user1_id = register_user(user1_first_name, user1_second_name, password1)
    user2_id = register_user(user2_first_name, user2_second_name, password2)
    
    if not user1_id or not user2_id:
        print("Ошибка при регистрации пользователей. Завершение тестирования.")
        return
    
    # Создаем словарь информации о пользователях
    user_info = {
        user1_id: {
            "first_name": user1_first_name,
            "second_name": user1_second_name
        },
        user2_id: {
            "first_name": user2_first_name,
            "second_name": user2_second_name
        }
    }
    
    user1_name = f"{user1_second_name} {user1_first_name}"
    user2_name = f"{user2_second_name} {user2_first_name}"
    
    # 2. Пользователь 1 логинится и добавляет пользователя 2 в друзья
    print(f"\nШаг 2: {user1_name} логинится и добавляет {user2_name} в друзья")
    user1_token = login_user(user1_id, password1, user1_name)
    
    if not user1_token:
        print(f"Ошибка при авторизации пользователя {user1_name}. Завершение тестирования.")
        return
    
    if not add_friend(user1_token, user2_id, user2_name):
        print(f"Ошибка при добавлении друга пользователем {user1_name}. Завершение тестирования.")
        return
    
    # 3. Пользователь 1 отправляет пользователю 2 100 сообщений
    print(f"\nШаг 3: {user1_name} отправляет {user2_name} 100 сообщений")
    
    # Проверим сразу один тестовый запрос с детальной диагностикой
    test_message = "Тестовое сообщение для диагностики"
    print(f"Отправляем тестовое сообщение для диагностики: '{test_message}'")
    sent = send_message(user1_token, user2_id, test_message, user2_name)
    
    if not sent:
        print("Тестовая отправка сообщения не удалась. Хотите продолжить отправку других сообщений? (y/n)")
        response = input()
        if response.lower() != 'y':
            print("Завершение тестирования.")
            return
    
    # Продолжаем с обычными сообщениями
    for i in range(1, 101):
        message_text = f"Сообщение #{i} от {user1_name} пользователю {user2_name}"
        if not send_message(user1_token, user2_id, message_text, user2_name):
            print(f"Ошибка при отправке сообщения #{i}. Продолжение...")
        time.sleep(0.1)  # Небольшая задержка между сообщениями
    
    # 4. Пользователь 2 логинится и добавляет пользователя 1 в друзья
    print(f"\nШаг 4: {user2_name} логинится и добавляет {user1_name} в друзья")
    user2_token = login_user(user2_id, password2, user2_name)
    
    if not user2_token:
        print(f"Ошибка при авторизации пользователя {user2_name}. Завершение тестирования.")
        return
    
    if not add_friend(user2_token, user1_id, user1_name):
        print(f"Ошибка при добавлении друга пользователем {user2_name}. Завершение тестирования.")
        return
    
    # 5. Пользователь 2 выводит список сообщений, полученных от пользователя 1
    print(f"\nШаг 5: {user2_name} выводит список сообщений, полученных от {user1_name}")
    messages_from_user1 = get_messages(user2_token, user1_id, user1_name)
    print_messages(messages_from_user1, user_info)
    
    # 6. Пользователь 2 отправляет 100 сообщений пользователю 1
    print(f"\nШаг 6: {user2_name} отправляет 100 сообщений {user1_name}")
    
    for i in range(1, 101):
        message_text = f"Сообщение #{i} от {user2_name} пользователю {user1_name}"
        if not send_message(user2_token, user1_id, message_text, user1_name):
            print(f"Ошибка при отправке сообщения #{i}. Продолжение...")
        time.sleep(0.1)  # Небольшая задержка между сообщениями
    
    # 7. Пользователь 1 выводит список сообщений, полученных от пользователя 2
    print(f"\nШаг 7: {user1_name} выводит список сообщений, полученных от {user2_name}")
    messages_from_user2 = get_messages(user1_token, user2_id, user2_name)
    print_messages(messages_from_user2, user_info)
    
    print("\n" + "=" * 80)
    print("Тестирование завершено")
    print("=" * 80)

if __name__ == "__main__":
    main() 