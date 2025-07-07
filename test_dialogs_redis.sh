#!/bin/bash

# ==============================================================================
# Комплексный скрипт для тестирования Dialog Service с бэкендом Redis (ДЗ-8)
#
# Что делает скрипт:
# 1. Запускает всю систему (monolith, dialog-service, db) с Redis-бэкендом.
# 2. Проводит функциональное тестирование (регистрация, авторизация, сообщения).
# 3. Останавливает и очищает систему после тестов.
# ==============================================================================

set -eo pipefail

# -- Переменные и настройки --
# Цвета для красивого вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# URL-адреса сервисов
MONOLITH_URL="http://localhost:8000"
DIALOG_SERVICE_URL="http://localhost:8002/api/v1/dialogs"

# -- Функции --

# Вывод сообщений
function print_info { echo -e "${BLUE}[INFO] $1${NC}"; }
function print_success { echo -e "${GREEN}[SUCCESS] $1${NC}"; }
function print_warning { echo -e "${YELLOW}[WARNING] $1${NC}"; }
function print_error { echo -e "${RED}[ERROR] $1${NC}"; }
function print_header { echo -e "\n${YELLOW}==================================================${NC}"; echo -e "${YELLOW}$1${NC}"; echo -e "${YELLOW}==================================================${NC}"; }

# Функция для выхода и очистки
function cleanup_and_exit {
    print_header "🛑 Завершение работы и очистка"
    ./stop_service.sh
    exit 1
}

# -- Основная логика --

# 1. Запуск системы с Redis бэкендом
print_header "🚀 Этап 1: Запуск системы с бэкендом Redis"
./start_service.sh --backend redis
if [ $? -ne 0 ]; then
    print_error "Не удалось запустить систему. Прерывание теста."
    exit 1
fi

# Устанавливаем обработчик для выхода (если что-то пойдет не так)
trap cleanup_and_exit SIGINT SIGTERM

# 2. Функциональное тестирование
print_header "🧪 Этап 2: Функциональное тестирование"

# Регистрация пользователей
print_info "Регистрация двух тестовых пользователей..."
USER1_SUFFIX=$(uuidgen | head -c 8)
USER2_SUFFIX=$(uuidgen | head -c 8)

USER1_ID=$(curl -s -X POST "${MONOLITH_URL}/user/register" -H "Content-Type: application/json" -d "{\"first_name\":\"Test1\",\"second_name\":\"User${USER1_SUFFIX}\",\"birthdate\":\"2000-01-01T00:00:00\",\"age\":30,\"city\":\"Moscow\",\"password\":\"test\"}" | jq -r .id)
USER2_ID=$(curl -s -X POST "${MONOLITH_URL}/user/register" -H "Content-Type: application/json" -d "{\"first_name\":\"Test2\",\"second_name\":\"User${USER2_SUFFIX}\",\"birthdate\":\"2000-01-01T00:00:00\",\"age\":30,\"city\":\"Moscow\",\"password\":\"test\"}" | jq -r .id)

if [ -z "$USER1_ID" ] || [ -z "$USER2_ID" ] || [ "$USER1_ID" == "null" ] || [ "$USER2_ID" == "null" ]; then
    print_error "Не удалось зарегистрировать пользователей."
    cleanup_and_exit
fi
print_success "Пользователи зарегистрированы: USER1_ID=$USER1_ID, USER2_ID=$USER2_ID"

# Авторизация
print_info "Авторизация первого пользователя..."
TOKEN1=$(curl -s -X POST "${MONOLITH_URL}/user/login" -H "Content-Type: application/json" -d "{\"id\":\"${USER1_ID}\",\"password\":\"test\"}" | jq -r .token)
if [ -z "$TOKEN1" ] || [ "$TOKEN1" == "null" ]; then
    print_error "Не удалось авторизовать пользователя 1."
    cleanup_and_exit
fi
print_success "Пользователь 1 успешно авторизован."

# Отправка сообщений через Dialog Service
print_info "Отправка 3 сообщений от USER1 к USER2..."
for i in {1..3}; do
    curl -s -X POST "${DIALOG_SERVICE_URL}/send" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${TOKEN1}" \
        -d "{\"to_user_id\":\"${USER2_ID}\",\"text\":\"Привет от User1, сообщение #${i}\"}"
done
print_success "Сообщения успешно отправлены."

# Получение диалога
print_info "Получение диалога между пользователями..."
MESSAGES=$(curl -s -X GET "${DIALOG_SERVICE_URL}/${USER2_ID}/messages" \
    -H "Authorization: Bearer ${TOKEN1}")

MESSAGE_COUNT=$(echo "$MESSAGES" | jq '. | length')

if [ "$MESSAGE_COUNT" -eq 3 ]; then
    print_success "Диалог получен, количество сообщений: $MESSAGE_COUNT. Тест пройден!"
else
    print_error "Ожидалось 3 сообщения, но получено $MESSAGE_COUNT."
    echo "Ответ сервера:"
    echo "$MESSAGES" | jq
    cleanup_and_exit
fi

# 3. Остановка системы
print_header "🎉 Этап 3: Тестирование завершено успешно. Остановка системы"
./stop_service.sh

print_success "Все тесты пройдены!"
exit 0 