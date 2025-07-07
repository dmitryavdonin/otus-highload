#!/bin/bash

# Скрипт для тестирования Dialog Service
set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Переменные
BASE_URL="http://localhost"
MONOLITH_URL="http://localhost:8000"
DIALOG_SERVICE_URL="http://localhost:8002"
REQUEST_ID=$(uuidgen 2>/dev/null || echo "test-$(date +%s)")

# Проверка доступности сервисов
check_service() {
    local url=$1
    local name=$2
    
    print_info "Проверка доступности $name..."
    
    if curl -s -f "$url" > /dev/null; then
        print_success "$name доступен"
        return 0
    else
        print_error "$name недоступен"
        return 1
    fi
}

# Проверка health check
check_health() {
    local url=$1
    local name=$2
    
    print_info "Проверка health check для $name..."
    
    response=$(curl -s "$url/health" 2>/dev/null || echo '{"status":"error"}')
    status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    
    if [ "$status" = "healthy" ]; then
        print_success "$name в здоровом состоянии"
        return 0
    else
        print_warning "$name health check: $status"
        return 1
    fi
}

# Регистрация тестового пользователя
register_user() {
    local user_suffix=$1
    print_info "Регистрация пользователя $user_suffix..." >&2
    
    response=$(curl -s -X POST "$MONOLITH_URL/user/register" \
        -H "Content-Type: application/json" \
        -H "x-request-id: $REQUEST_ID" \
        -d "{
            \"first_name\": \"Test\",
            \"second_name\": \"User$user_suffix\",
            \"birthdate\": \"1990-01-01T00:00:00\",
            \"biography\": \"Test user for dialog service\",
            \"city\": \"Test City\",
            \"password\": \"testpassword123\"
        }" 2>/dev/null || echo '{"error":"registration failed"}')
    
    if echo "$response" | grep -q '"id"'; then
        user_id=$(echo "$response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4 2>/dev/null)
        print_success "Пользователь $user_suffix зарегистрирован с ID: $user_id" >&2
        echo "$user_id"
        return 0
    else
        print_warning "Пользователь $user_suffix возможно уже существует" >&2
        return 1
    fi
}

# Авторизация пользователя
login_user() {
    local user_id=$1
    print_info "Авторизация пользователя $user_id..." >&2
    
    response=$(curl -s -X POST "$MONOLITH_URL/user/login" \
        -H "Content-Type: application/json" \
        -H "x-request-id: $REQUEST_ID" \
        -d "{
            \"id\": \"$user_id\",
            \"password\": \"testpassword123\"
        }" 2>/dev/null || echo '{"error":"login failed"}')
    
    token=$(echo "$response" | grep -o '"token":"[^"]*"' | cut -d'"' -f4 2>/dev/null)
    
    if [ -n "$token" ]; then
        print_success "Пользователь $user_id авторизован" >&2
        echo "$token"
        return 0
    else
        print_error "Ошибка авторизации пользователя $user_id" >&2
        echo "$response" >&2
        return 1
    fi
}


# Тестирование v2 API через Nginx -> Dialog Service
test_v2_api() {
    local token=$1
    local from_user_id=$2
    local to_user_id=$3
    
    print_info "Тестирование v2 API (новые клиенты) через Nginx -> Dialog Service..."
    
    # Отправка нескольких сообщений через v2 API для реалистичного тестирования
    local messages=(
        "Привет! Как дела?"
        "Тестирую новый Dialog Service"
        "Это сообщение через v2 API"
        "Проверяю функциональность диалогов"
        "Надеюсь, всё работает корректно!"
    )
    
    local sent_count=0
    for message in "${messages[@]}"; do
        response=$(curl -s --max-time 30 -X POST "$BASE_URL/v2/dialog/send" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -H "x-request-id: $REQUEST_ID" \
            -d "{
                \"to_user_id\": \"$to_user_id\",
                \"text\": \"$message\"
            }" 2>/dev/null || echo '{"error":"v2 send failed"}')
        
        if echo "$response" | grep -q '"message_id"'; then
            message_id=$(echo "$response" | grep -o '"message_id":"[^"]*"' | cut -d'"' -f4 2>/dev/null)
            sent_count=$((sent_count + 1))
            sleep 0.1  # Небольшая пауза между сообщениями
        else
            print_error "Ошибка отправки сообщения через v2 API: $message"
            echo "$response"
            return 1
        fi
    done
    
    print_success "Отправлено $sent_count сообщений через v2 API"
    
    print_info "Тестирование получения сообщений через v2 API..."
    
    # Получение сообщений через v2 API
    response=$(curl -s --max-time 30 -X GET "$BASE_URL/v2/dialog/$to_user_id/messages?offset=0&limit=5" \
        -H "Authorization: Bearer $token" \
        -H "x-request-id: $REQUEST_ID" \
        2>/dev/null || echo '{"error":"v2 get failed"}')
    
    if echo "$response" | grep -q '\['; then
        message_count=$(echo "$response" | grep -o '"from_user_id"' | wc -l)
        print_success "Получено сообщений через v2 API: $message_count"
    else
        print_error "Ошибка получения сообщений через v2 API"
        echo "$response"
        return 1
    fi
    
    print_info "Тестирование статистики через v2 API..."
    
    # Получение статистики через v2 API
    response=$(curl -s -X GET "$BASE_URL/v2/dialog/stats" \
        -H "Authorization: Bearer $token" \
        -H "x-request-id: $REQUEST_ID" \
        2>/dev/null || echo '{"error":"v2 stats failed"}')
    
    if echo "$response" | grep -q '"total_dialogs"'; then
        total_dialogs=$(echo "$response" | grep -o '"total_dialogs":[0-9]*' | cut -d':' -f2 2>/dev/null)
        print_success "Статистика через v2 API - диалоги: $total_dialogs"
    else
        print_error "Ошибка получения статистики через v2 API"
        echo "$response"
        return 1
    fi
    
    print_success "Тестирование v2 API завершено успешно! ✅"
}

# Тестирование v1 API через Nginx -> Монолит (legacy клиенты)
test_v1_api() {
    local token=$1
    local from_user_id=$2
    local to_user_id=$3
    
    print_info "Тестирование v1 API (legacy клиенты) через Nginx -> Монолит..."
    
    # Отправка нескольких сообщений через v1 API для реалистичного тестирования
    local sent_count=0
    
    # Отправляем сообщения по одному с явным указанием текста
    response=$(curl -s --max-time 30 -X POST "$BASE_URL/v1/dialog/$to_user_id/send" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "x-request-id: $REQUEST_ID" \
        -d '{"text": "Привет из legacy клиента!"}' 2>/dev/null || echo '{"error":"v1 send failed"}')
    
    if echo "$response" | grep -q '"status":"success"'; then
        sent_count=$((sent_count + 1))
    else
        print_error "Ошибка отправки сообщения через v1 API: Привет из legacy клиента!"
        echo "$response"
        return 1
    fi
    sleep 0.1
    
    response=$(curl -s --max-time 30 -X POST "$BASE_URL/v1/dialog/$to_user_id/send" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "x-request-id: $REQUEST_ID" \
        -d '{"text": "Тестирую v1 API через монолит"}' 2>/dev/null || echo '{"error":"v1 send failed"}')
    
    if echo "$response" | grep -q '"status":"success"'; then
        sent_count=$((sent_count + 1))
    else
        print_error "Ошибка отправки сообщения через v1 API: Тестирую v1 API через монолит"
        echo "$response"
        return 1
    fi
    sleep 0.1
    
    response=$(curl -s --max-time 30 -X POST "$BASE_URL/v1/dialog/$to_user_id/send" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "x-request-id: $REQUEST_ID" \
        -d '{"text": "Проверяю обратную совместимость"}' 2>/dev/null || echo '{"error":"v1 send failed"}')
    
    if echo "$response" | grep -q '"status":"success"'; then
        sent_count=$((sent_count + 1))
    else
        print_error "Ошибка отправки сообщения через v1 API: Проверяю обратную совместимость"
        echo "$response"
        return 1
    fi
    sleep 0.1
    
    response=$(curl -s --max-time 30 -X POST "$BASE_URL/v1/dialog/$to_user_id/send" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "x-request-id: $REQUEST_ID" \
        -d '{"text": "Legacy системы должны работать"}' 2>/dev/null || echo '{"error":"v1 send failed"}')
    
    if echo "$response" | grep -q '"status":"success"'; then
        sent_count=$((sent_count + 1))
    else
        print_error "Ошибка отправки сообщения через v1 API: Legacy системы должны работать"
        echo "$response"
        return 1
    fi
    sleep 0.1
    
    response=$(curl -s --max-time 30 -X POST "$BASE_URL/v1/dialog/$to_user_id/send" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "x-request-id: $REQUEST_ID" \
        -d '{"text": "Всё отлично работает!"}' 2>/dev/null || echo '{"error":"v1 send failed"}')
    
    if echo "$response" | grep -q '"status":"success"'; then
        sent_count=$((sent_count + 1))
    else
        print_error "Ошибка отправки сообщения через v1 API: Всё отлично работает!"
        echo "$response"
        return 1
    fi
    
    print_success "Отправлено $sent_count сообщений через v1 API"
    
    sleep 1
    
    print_info "Тестирование получения сообщений через v1 API..."
    
    # Получение сообщений через v1 API
    response=$(curl -s --max-time 30 -X GET "$BASE_URL/v1/dialog/$to_user_id/list" \
        -H "Authorization: Bearer $token" \
        -H "x-request-id: $REQUEST_ID" \
        2>/dev/null || echo '{"error":"v1 get failed"}')
    
    if echo "$response" | grep -q '\['; then
        message_count=$(echo "$response" | grep -o '"from_user_id"' | wc -l)
        print_success "Получено сообщений через v1 API: $message_count"
    else
        print_error "Ошибка получения сообщений через v1 API"
        echo "$response"
        return 1
    fi
    
    print_info "Тестирование статистики через v1 API..."
    
    # Получение статистики через v1 API
    response=$(curl -s -X GET "$BASE_URL/v1/dialog/stats" \
        -H "Authorization: Bearer $token" \
        -H "x-request-id: $REQUEST_ID" \
        2>/dev/null || echo '{"error":"v1 stats failed"}')
    
    if echo "$response" | grep -q '"total_dialogs"\|"total_messages"'; then
        total_dialogs=$(echo "$response" | grep -o '"total_dialogs":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "N/A")
        total_messages=$(echo "$response" | grep -o '"total_messages":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "N/A")
        print_success "Статистика через v1 API - диалоги: $total_dialogs, сообщения: $total_messages"
    else
        print_error "Ошибка получения статистики через v1 API"
        echo "$response"
        return 1
    fi
    
    print_success "Тестирование v1 API завершено успешно! ✅"
}

# Тестирование двунаправленного диалога
test_bidirectional_dialog() {
    local token1=$1
    local token2=$2
    local user1_id=$3
    local user2_id=$4
    
    print_info "Тестирование двунаправленного диалога между пользователями..."
    
    # Диалог между пользователями через разные API версии
    local conversation=(
        "1:v2:Привет! Как дела?"
        "2:v1:Привет! Всё отлично, а у тебя?"
        "1:v2:Тоже хорошо! Тестирую новый Dialog Service"
        "2:v1:Круто! Как тебе новая архитектура?"
        "1:v2:Отлично работает! Очень быстро"
        "2:v1:Рад слышать! Версионирование API супер!"
    )
    
    local sent_count=0
    for entry in "${conversation[@]}"; do
        local sender=$(echo "$entry" | cut -d':' -f1)
        local api_version=$(echo "$entry" | cut -d':' -f2)
        local message=$(echo "$entry" | cut -d':' -f3-)
        
        if [ "$sender" = "1" ]; then
            local from_token="$token1"
            local to_user_id="$user2_id"
        else
            local from_token="$token2"
            local to_user_id="$user1_id"
        fi
        
        if [ "$api_version" = "v1" ]; then
            response=$(curl -s -X POST "$BASE_URL/v1/dialog/$to_user_id/send" \
                -H "Authorization: Bearer $from_token" \
                -H "Content-Type: application/json" \
                -H "x-request-id: $REQUEST_ID" \
                -d "{
                    \"text\": \"$message\"
                }" 2>/dev/null || echo '{"error":"send failed"}')
            
            if echo "$response" | grep -q '"status":"success"'; then
                sent_count=$((sent_count + 1))
            else
                print_error "Ошибка отправки через v1 API: $message"
                return 1
            fi
        else
            response=$(curl -s -X POST "$BASE_URL/v2/dialog/send" \
                -H "Authorization: Bearer $from_token" \
                -H "Content-Type: application/json" \
                -H "x-request-id: $REQUEST_ID" \
                -d "{
                    \"to_user_id\": \"$to_user_id\",
                    \"text\": \"$message\"
                }" 2>/dev/null || echo '{"error":"send failed"}')
            
            if echo "$response" | grep -q '"message_id"'; then
                sent_count=$((sent_count + 1))
            else
                print_error "Ошибка отправки через v2 API: $message"
                return 1
            fi
        fi
        
        sleep 0.3  # Пауза между сообщениями для реалистичности
    done
    
    print_success "Отправлено $sent_count сообщений в двунаправленном диалоге"
    
    # Проверка получения сообщений обеими пользователями
    sleep 2
    
    print_info "Проверка получения сообщений пользователем 1..."
    response=$(curl -s -X GET "$BASE_URL/v2/dialog/$user2_id/messages?offset=0&limit=20" \
        -H "Authorization: Bearer $token1" \
        -H "x-request-id: $REQUEST_ID" \
        2>/dev/null || echo '{"error":"get failed"}')
    
    if echo "$response" | grep -q '\['; then
        message_count=$(echo "$response" | grep -o '"from_user_id"' | wc -l)
        print_success "Пользователь 1 получил $message_count сообщений"
    else
        print_error "Ошибка получения сообщений пользователем 1"
        return 1
    fi
    
    print_info "Проверка получения сообщений пользователем 2..."
    response=$(curl -s -X GET "$BASE_URL/v1/dialog/$user1_id/list" \
        -H "Authorization: Bearer $token2" \
        -H "x-request-id: $REQUEST_ID" \
        2>/dev/null || echo '{"error":"get failed"}')
    
    if echo "$response" | grep -q '\['; then
        message_count=$(echo "$response" | grep -o '"from_user_id"' | wc -l)
        print_success "Пользователь 2 получил $message_count сообщений"
    else
        print_error "Ошибка получения сообщений пользователем 2"
        return 1
    fi
    
    print_success "Двунаправленный диалог работает корректно! ✅"
}

# Тест fallback механизма
test_fallback() {
    print_info "Тестирование fallback механизма..."
    
    # Останавливаем dialog-service
    print_info "Остановка dialog-service для тестирования fallback..."
    docker-compose stop dialog-service >/dev/null 2>&1 || true
    
    sleep 5
    
    # Пытаемся отправить сообщение (должен сработать fallback)
    print_info "Отправка сообщения с fallback..."
    
    # Здесь нужен токен, используем первый полученный
    if [ -n "$USER1_TOKEN" ]; then
        response=$(curl -s -X POST "$BASE_URL/v1/dialog/send" \
            -H "Authorization: Bearer $USER1_TOKEN" \
            -H "Content-Type: application/json" \
            -H "x-request-id: $REQUEST_ID" \
            -d '{
                "from_user_id": 1,
                "to_user_id": 2,
                "text": "Fallback test message"
            }' 2>/dev/null || echo '{"error":"fallback failed"}')
        
        if echo "$response" | grep -q '"fallback":true'; then
            print_success "Fallback механизм работает!"
        else
            print_warning "Fallback может не работать или dialog-service всё ещё доступен"
        fi
    fi
    
    # Запускаем dialog-service обратно
    print_info "Запуск dialog-service..."
    docker-compose start dialog-service >/dev/null 2>&1 || true
    
    sleep 10
}

# Основная функция тестирования
main() {
    print_info "Начало тестирования Dialog Service..."
    print_info "Request ID: $REQUEST_ID"
    echo
    
    # Проверка доступности всех сервисов
    print_info "=== Проверка доступности сервисов ==="
    check_service "$BASE_URL" "Nginx (порт 80)" || exit 1
    check_service "$MONOLITH_URL" "Монолит (порт 8000)" || exit 1
    check_service "$DIALOG_SERVICE_URL" "Dialog Service (порт 8002)" || exit 1
    echo
    
    # Проверка health checks
    print_info "=== Проверка health checks ==="
    check_health "$MONOLITH_URL" "Монолит"
    check_health "$DIALOG_SERVICE_URL" "Dialog Service"
    echo
    
    # Создание тестовых пользователей
    print_info "=== Подготовка тестовых данных ==="
    USER1_SUFFIX=$(uuidgen 2>/dev/null || echo "test-user-1-$(date +%s)")
    USER2_SUFFIX=$(uuidgen 2>/dev/null || echo "test-user-2-$(date +%s)")
    
    USER1_ID=$(register_user "$USER1_SUFFIX")
    USER2_ID=$(register_user "$USER2_SUFFIX")
    
    if [ -z "$USER1_ID" ] || [ -z "$USER2_ID" ]; then
        print_error "Не удалось зарегистрировать пользователей"
        exit 1
    fi
    echo
    
    # Авторизация пользователей
    print_info "=== Авторизация пользователей ==="
    USER1_TOKEN=$(login_user "$USER1_ID")
    USER2_TOKEN=$(login_user "$USER2_ID")
    

    
    if [ -z "$USER1_TOKEN" ] || [ -z "$USER2_TOKEN" ]; then
        print_error "Не удалось авторизовать пользователей"
        exit 1
    fi
    
    echo
    
    # Тестирование Dialog API
    print_info "=== Тестирование Dialog API ==="
    
    # Тестирование v1 API (legacy клиенты через Nginx -> Монолит)
    print_info "Тестирование v1 API (legacy клиенты)..."
    test_v1_api "$USER1_TOKEN" "$USER1_ID" "$USER2_ID"
    
    sleep 1
    
    # Тестирование v2 API (новые клиенты через Nginx -> Dialog Service)
    print_info "Тестирование v2 API (новые клиенты)..."
    test_v2_api "$USER1_TOKEN" "$USER1_ID" "$USER2_ID"
    
    sleep 1
    
    # Тестирование двунаправленного диалога
    print_info "=== Тестирование двунаправленного диалога ==="
    test_bidirectional_dialog "$USER1_TOKEN" "$USER2_TOKEN" "$USER1_ID" "$USER2_ID"
    
    sleep 1
    
    # Тест fallback (если указан параметр)
    if [ "$1" = "--test-fallback" ]; then
        print_info "=== Тестирование fallback механизма ==="
        test_fallback
        echo
    fi
    
    print_success "Все тесты завершены успешно!"
    print_info "Для просмотра логов используйте:"
    print_info "  docker-compose logs -f dialog-service"
    print_info "  docker-compose logs -f monolith"
    print_info "Для поиска по request ID: $REQUEST_ID"
}

# Справка
show_help() {
    echo "Использование: $0 [ОПЦИИ]"
    echo ""
    echo "Опции:"
    echo "  --test-fallback    Включить тестирование fallback механизма"
    echo "  --help             Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0                 # Обычное тестирование"
    echo "  $0 --test-fallback # Тестирование с fallback"
}

# Обработка аргументов командной строки
case "$1" in
    --help)
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac 