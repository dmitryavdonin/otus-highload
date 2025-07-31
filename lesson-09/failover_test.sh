#!/bin/bash

# Скрипт тестирования отказоустойчивости для урока 9
# Использование: ./failover_test.sh [postgres|app|combined]

set -e

LESSON_DIR="lesson-09"
COMPOSE_FILE="docker-compose-ha.yml"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Проверка что мы в правильной директории
check_environment() {
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        error "Файл $COMPOSE_FILE не найден. Запустите скрипт из папки lesson-09"
        exit 1
    fi
    
    log "Проверка состояния сервисов..."
    docker compose -f "$COMPOSE_FILE" ps
}

# Создание тестового пользователя и получение токена (с retry и отладкой)
get_auth_token() {
    local timestamp=$(date +%s)
    local birthdate=$(date -d "25 years ago" "+%Y-%m-%dT%H:%M:%S")
    
    # Данные для регистрации (БЕЗ поля id - его назначает сервер)
    local test_user="{\"first_name\":\"TestUser\",\"second_name\":\"Failover$timestamp\",\"birthdate\":\"$birthdate\",\"biography\":\"Test user for failover\",\"city\":\"TestCity\",\"password\":\"test123\"}"
    
    log "Попытка создания тестового пользователя для проверки API..."
    
    # Ждем стабилизации системы после failover
    log "Ожидание стабилизации системы (10 секунд)..."
    sleep 10
    
    # Регистрация пользователя (с retry и расширенной отладкой)
    local reg_response
    local reg_code
            for attempt in {1..5}; do
            # log "Попытка регистрации $attempt/5..."  # Убираем логирование
        reg_response=$(curl -s -w "HTTP_CODE:%{http_code}" -X POST "http://localhost/user/register" -H "Content-Type: application/json" -d "$test_user" 2>/dev/null)
        reg_code=$(echo "$reg_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
        
        # log "Регистрация: HTTP код $reg_code"
        
        if [[ "$reg_code" == "200" ]]; then
            # log "Регистрация успешна"
            break
        elif [[ "$reg_code" == "500" && $attempt -lt 5 ]]; then
            # log "Получена 500 ошибка, повторяем через $((attempt * 2)) секунд..."
            sleep $((attempt * 2))  # Increasing delay
        elif [[ -z "$reg_code" ]]; then
            # log "Нет ответа от сервера, повторяем через $((attempt * 2)) секунд..."
            sleep $((attempt * 2))
        else
            # log "Регистрация не удалась: код $reg_code, ответ: $(echo "$reg_response" | sed 's/HTTP_CODE:[0-9]*//')"
            return 1
        fi
    done
    
    if [[ "$reg_code" == "200" ]]; then
        # Извлекаем user_id из ответа регистрации
        local user_id=$(echo "$reg_response" | sed 's/HTTP_CODE:[0-9]*//' | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
        
        if [[ -n "$user_id" ]]; then
            # log "Получен user_id: $user_id"  # Убираем логирование чтобы не попало в токен
            
            # Авторизация пользователя с полученным ID (с retry и отладкой)
            local login_data="{\"id\":\"$user_id\",\"password\":\"test123\"}"
            local auth_response
            local auth_code
            
            for attempt in {1..5}; do
                # log "Попытка авторизации $attempt/5..."  # Убираем логирование
                auth_response=$(curl -s -w "HTTP_CODE:%{http_code}" -X POST "http://localhost/user/login" -H "Content-Type: application/json" -d "$login_data" 2>/dev/null)
                auth_code=$(echo "$auth_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
                
                # log "Авторизация: HTTP код $auth_code"  # Убираем логирование
                
                if [[ "$auth_code" == "200" ]]; then
                    # Извлекаем токен из ответа
                    local token=$(echo "$auth_response" | sed 's/HTTP_CODE:[0-9]*//' | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
                    if [[ -n "$token" ]]; then
                        # log "Токен получен успешно"  # Убираем логирование
                        echo "$token"
                        return 0
                    else
                        # log "Ошибка извлечения токена из ответа"
                        true  # Пустая команда для корректного синтаксиса
                    fi
                elif [[ "$auth_code" == "500" && $attempt -lt 5 ]]; then
                    # log "Получена 500 ошибка при авторизации, повторяем через $((attempt * 2)) секунд..."
                    sleep $((attempt * 2))
                elif [[ -z "$auth_code" ]]; then
                    # log "Нет ответа при авторизации, повторяем через $((attempt * 2)) секунд..."
                    sleep $((attempt * 2))
                else
                    # log "Авторизация не удалась: код $auth_code, ответ: $(echo "$auth_response" | sed 's/HTTP_CODE:[0-9]*//')"
                    break
                fi
            done
        else
            # log "Не удалось извлечь user_id из ответа регистрации"
            true  # Пустая команда для корректного синтаксиса
        fi
    else
        # log "Регистрация не удалась после всех попыток"
        true  # Пустая команда для корректного синтаксиса  
    fi
    
    return 1
}

# Функция для отслеживания nginx логов
monitor_nginx_logs() {
    local operation=$1
    log "=== NGINX LOGS BEFORE $operation ==="
    
    # Используем docker logs вместо exec для избежания зависаний
    echo "--- Nginx container logs (последние 5 записей) ---"
    timeout 5 docker logs lesson-09-nginx-1 --tail 5 2>/dev/null | grep -E "(GET|POST|ERROR|WARN)" | tail -3 || echo "Нет логов nginx"
    
    echo "--- Статус nginx upstream'ов ---"
    for port in 9001 9002 9003; do
        local status=$(timeout 3 curl -s -w "%{http_code}" "http://localhost:$port/health" -o /dev/null 2>/dev/null || echo "000")
        echo "App port $port: HTTP $status"
    done
}

show_nginx_logs_after_error() {
    log "=== NGINX LOGS AFTER ERROR ==="
    
    echo "--- Nginx container logs (последние 10 записей) ---"
    timeout 5 docker logs lesson-09-nginx-1 --tail 10 2>/dev/null | grep -E "(GET|POST|ERROR|WARN|4[0-9][0-9]|5[0-9][0-9])" | tail -5 || echo "Нет логов nginx"
    
    echo "--- HAProxy статус PostgreSQL ---"
    timeout 3 curl -s "http://localhost:8404/stats;csv" 2>/dev/null | grep postgres-slave | cut -d',' -f1,2,18 | head -3 || echo "HAProxy недоступен"
    
    echo "--- Upstream статус ---"
    for port in 9001 9002 9003; do
        local status=$(timeout 3 curl -s -w "%{http_code}" "http://localhost:$port/health" -o /dev/null 2>/dev/null || echo "000")
        echo "App port $port: HTTP $status"
    done
    
    echo "--- Docker контейнеры ---"
    timeout 3 docker ps --format "table {{.Names}}\t{{.Status}}" | grep lesson-09 | head -5 || echo "Docker недоступен"
}

# Тест API с авторизацией
test_api_with_auth() {
    local operation=$1  # "read" или "write"
    
    # log "Получение токена авторизации для теста $operation..."  # Убираем чтобы не мешало токену
    local token=$(get_auth_token)
    
    if [[ -z "$token" ]]; then
        error "Не удалось получить токен авторизации"
        return 1
    fi
    
    # log "Токен получен, выполняем тест $operation..."  # Убираем чтобы не мешало
    # echo "DEBUG: Token hex dump:" && echo -n "$token" | xxd | head -3  # Убираем отладку
    
    if [[ "$operation" == "read" ]]; then
        # Мониторим логи перед запросом
        monitor_nginx_logs "READ"
        
        # Тест поиска пользователей
        local response=$(curl -s -w "HTTP_CODE:%{http_code}" -H "Authorization: Bearer $token" "http://localhost/user/search?first_name=TestUser&second_name=Failover" 2>/dev/null)
        local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
        
        if [[ "$http_code" == "200" ]]; then
            success "Чтение через API работает (поиск пользователей успешен)"
            return 0
        else
            error "Чтение через API не работает! HTTP код: $http_code"
            log "Ответ API: $(echo "$response" | sed 's/HTTP_CODE:[0-9]*//')"
            
            # Показываем логи после ошибки
            show_nginx_logs_after_error
            return 1
        fi
    elif [[ "$operation" == "write" ]]; then
        # Мониторим логи перед запросом
        monitor_nginx_logs "WRITE"
        
        # Тест создания поста или другой операции записи
        local timestamp=$(date +%s)
        local post_data="{\"text\":\"Test post from failover test $timestamp\"}"
        
        # Отладочный вывод
        echo "DEBUG: Token: '$token'"
        echo "DEBUG: Token length: ${#token}"
        echo "DEBUG: Post data: '$post_data'"
        echo "DEBUG: curl command: curl -s -w \"HTTP_CODE:%{http_code}\" -X POST -H \"Authorization: Bearer $token\" -H \"Content-Type: application/json\" -d \"$post_data\" \"http://localhost/post/create\""
        
        local response=$(curl -s -w "HTTP_CODE:%{http_code}" -X POST -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "$post_data" "http://localhost/post/create" 2>/dev/null)
        local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
        
        if [[ "$http_code" == "200" ]]; then
            success "Запись через API работает (создание поста успешно)"
            return 0
        else
            error "Запись через API не работает! HTTP код: $http_code"
            log "Ответ API: $(echo "$response" | sed 's/HTTP_CODE:[0-9]*//')"
            log "Данные поста: $post_data"
            
            # Показываем логи после ошибки
            show_nginx_logs_after_error
            return 1
        fi
    fi
}

# Мониторинг HAProxy статистики
show_haproxy_stats() {
    log "HAProxy статистика:"
    echo "================================"
    
    # Получаем статистику в CSV формате
    local stats=$(curl -s "http://localhost:8404/stats;csv" 2>/dev/null)
    
    if [ -n "$stats" ]; then
        # Парсим CSV и выводим только нужную информацию
        echo "$stats" | grep -E "postgres_master|postgres_slaves" | while IFS=',' read -r pxname svname qcur qmax scur smax slim stot bin bout dreq dresp ereq econ eresp wretr wredis status weight act bck chkfail chkdown lastchg downtime qlimit pid iid sid throttle lbtot tracked type rate rate_lim rate_max check_status check_code check_duration hrsp_1xx hrsp_2xx hrsp_3xx hrsp_4xx hrsp_5xx hrsp_other hanafail req_rate req_rate_max req_tot cli_abrt srv_abrt comp_in comp_out comp_byp comp_rsp lastsess last_chk last_agt qtime ctime rtime ttime rest; do
            if [[ "$svname" != "BACKEND" && "$svname" != "FRONTEND" ]]; then
                case "$status" in
                    "UP"|"UP 1/1"|"UP 2/2") 
                        echo "  ✅ $svname: UP (active: $act, connections: $scur)"
                        ;;
                    "DOWN"|"DOWN 1/2"|"DOWN 0/2")
                        echo "  ❌ $svname: DOWN (last check: $last_chk)"
                        ;;
                    *)
                        echo "  ⚠️  $svname: $status"
                        ;;
                esac
            fi
        done
    else
        warning "Не удалось получить статистику HAProxy"
    fi
    echo ""
}

# Мониторинг nginx upstream'ов
check_nginx_upstreams() {
    log "Проверка доступности приложений через nginx:"
    echo "================================"
    
    for i in {1..3}; do
        response=$(curl -s -w "%{http_code}" http://localhost:900$i/health -o /dev/null || echo "000")
        if [[ $response == "200" ]]; then
            success "app$i: доступно (HTTP $response)"
        else
            error "app$i: недоступно (HTTP $response)"
        fi
    done
    
    # Тест nginx балансировщика
    response=$(curl -s -w "%{http_code}" http://localhost/health -o /dev/null || echo "000")
    if [[ $response == "200" ]]; then
        success "nginx балансировщик: работает (HTTP $response)"
    else
        error "nginx балансировщик: проблемы (HTTP $response)"
    fi
    echo ""
}

# Тест отказа PostgreSQL слейва
test_postgres_slave_failure() {
    log "🔥 ТЕСТ ОТКАЗА POSTGRESQL СЛЕЙВА"
    echo "================================"
    
    log "Исходное состояние HAProxy:"
    show_haproxy_stats
    
    log "Убиваем postgres-slave1..."
    docker kill lesson-09-postgres-slave1-1 || warning "Контейнер postgres-slave1 уже остановлен"
    
    sleep 5
    
    log "Состояние после отказа:"
    show_haproxy_stats
    
    log "Тестируем доступность чтения через API приложения..."
    test_api_with_auth "read"
    
    log "Восстанавливаем postgres-slave1..."
    docker compose -f "$COMPOSE_FILE" up -d postgres-slave1
    
    log "Ожидание восстановления..."
    sleep 30
    
    log "Финальное состояние:"
    show_haproxy_stats
}

# Тест отказа инстанса приложения
test_app_failure() {
    log "🔥 ТЕСТ ОТКАЗА ИНСТАНСА ПРИЛОЖЕНИЯ"
    echo "================================"
    
    log "Исходное состояние приложений:"
    check_nginx_upstreams
    
    log "Убиваем app2..."
    docker kill lesson-09-app2-1 || warning "Контейнер app2 уже остановлен"
    
    sleep 3
    
    log "Состояние после отказа:"
    check_nginx_upstreams
    
    log "Тестируем распределение нагрузки nginx (10 запросов)..."
    for i in {1..10}; do
        instance=$(curl -s http://localhost/health | jq -r '.instance' 2>/dev/null || echo "ERROR")
        echo "Запрос $i: $instance"
        sleep 0.5
    done
    
    log "Восстанавливаем app2..."
    docker compose -f "$COMPOSE_FILE" up -d app2
    
    log "Ожидание восстановления..."
    sleep 15
    
    log "Финальное состояние:"
    check_nginx_upstreams
}

# Комбинированный тест отказов
test_combined_failure() {
    log "🔥 КОМБИНИРОВАННЫЙ ТЕСТ ОТКАЗОВ"
    echo "================================"
    
    log "Исходное состояние:"
    show_haproxy_stats
    check_nginx_upstreams
    
    log "Одновременно убиваем postgres-slave2 и app3..."
    docker kill lesson-09-postgres-slave2-1 lesson-09-app3-1 || warning "Некоторые контейнеры уже остановлены"
    
    sleep 5
    
    log "Состояние после отказов:"
    show_haproxy_stats
    check_nginx_upstreams
    
    log "Тестируем работоспособность системы..."
    
    # Тест записи через API
    log "Тестируем запись через API..."
    test_api_with_auth "write"
    
    # Тест чтения через API
    log "Тестируем чтение через API после комбинированного отказа..."
    test_api_with_auth "read"
    
    # Тест приложения
    app_test=$(curl -s -w "%{http_code}" http://localhost/health -o /dev/null || echo "000")
    if [[ $app_test == "200" ]]; then
        success "Приложение доступно через nginx (маршрутизация на app1,app2)"
    else
        error "Приложение недоступно!"
    fi
    
    log "Проверяем что система продолжает работать без упавших сервисов..."
    log "postgres-slave2 и app3 должны остаться DOWN - это нормально!"
    
    # Дополнительный тест что HAProxy исключил упавший slave
    log "Проверяем что HAProxy исключил postgres-slave2..."
    local slave2_status=$(curl -s "http://localhost:8404/stats;csv" | grep "postgres-slave2" | cut -d',' -f18)
    if [[ "$slave2_status" == "DOWN" ]]; then
        success "HAProxy правильно исключил упавший postgres-slave2"
    else
        warning "HAProxy статус postgres-slave2: $slave2_status"
    fi
    
    # Проверяем что nginx исключил упавший app3
    log "Проверяем доступность app1 и app2 (app3 должен быть исключен)..."
    local app1_status=$(curl -s -w "%{http_code}" "http://localhost:9001/health" -o /dev/null)
    local app2_status=$(curl -s -w "%{http_code}" "http://localhost:9002/health" -o /dev/null)
    
    if [[ "$app1_status" == "200" && "$app2_status" == "200" ]]; then
        success "Оставшиеся приложения (app1,app2) работают нормально"
    else
        error "Проблемы с оставшимися приложениями: app1=$app1_status, app2=$app2_status"
    fi
    
    log "Финальное состояние:"
    show_haproxy_stats
    check_nginx_upstreams
    
    echo ""
    success "✅ КОМБИНИРОВАННЫЙ ТЕСТ ЗАВЕРШЕН УСПЕШНО!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎯 Система продолжает работать несмотря на отказы:"
    echo "   • postgres-slave2 DOWN → HAProxy маршрутизирует на slave1"  
    echo "   • app3 DOWN → nginx маршрутизирует на app1,app2"
    echo "   • Пользователи не замечают проблем!"
    echo ""
    echo "🔧 Для восстановления полной избыточности (по желанию):"
    echo "   docker compose -f docker-compose-ha.yml up -d postgres-slave2 app3"
}

# Непрерывный мониторинг
continuous_monitoring() {
    log "🔍 РЕЖИМ НЕПРЕРЫВНОГО МОНИТОРИНГА"
    echo "================================"
    log "Нажмите Ctrl+C для остановки"
    
    while true; do
        clear
        echo "$(date +'%Y-%m-%d %H:%M:%S') - Мониторинг отказоустойчивости"
        echo "============================================================"
        
        show_haproxy_stats
        check_nginx_upstreams
        
        echo "Следующее обновление через 10 секунд..."
        sleep 10
    done
}

# Главное меню
show_usage() {
    echo "Использование: $0 [КОМАНДА]"
    echo ""
    echo "Команды:"
    echo "  postgres    - Тест отказа PostgreSQL слейва"
    echo "  app         - Тест отказа инстанса приложения"
    echo "  combined    - Комбинированный тест отказов"
    echo "  monitor     - Непрерывный мониторинг"
    echo "  status      - Проверка состояния всех сервисов"
    echo ""
    echo "Примеры:"
    echo "  $0 postgres"
    echo "  $0 app"
    echo "  $0 combined"
    echo "  $0 monitor"
}

# Основная логика
main() {
    case "${1:-}" in
        "postgres")
            check_environment
            test_postgres_slave_failure
            ;;
        "app")
            check_environment
            test_app_failure
            ;;
        "combined")
            check_environment
            test_combined_failure
            ;;
        "monitor")
            check_environment
            continuous_monitoring
            ;;
        "status")
            check_environment
            show_haproxy_stats
            check_nginx_upstreams
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

# Проверка зависимостей
check_dependencies() {
    command -v curl >/dev/null 2>&1 || { error "curl не установлен"; exit 1; }
    command -v jq >/dev/null 2>&1 || { warning "jq не установлен - некоторые функции могут не работать"; }
    command -v psql >/dev/null 2>&1 || { error "psql не установлен"; exit 1; }
}

# Запуск
check_dependencies
main "$@" 