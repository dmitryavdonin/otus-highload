#!/usr/bin/env python3
import psycopg2
import time
import random
import string
import signal
import sys
import threading
from datetime import datetime

# Параметры подключения к базе данных
DB_HOST = "localhost"  # Будет переопределено аргументом командной строки
DB_PORT = "5432"       # Будет переопределено аргументом командной строки
DB_NAME = "social_network"
DB_USER = "postgres"
DB_PASSWORD = "postgres"

# Глобальные переменные для отслеживания
running = True
successful_inserts = 0
failed_inserts = 0
lock = threading.Lock()

def signal_handler(sig, frame):
    """Обработчик сигнала для корректного завершения"""
    global running
    print("\nОстановка теста...")
    running = False

def generate_random_string(length=10):
    """Генерация случайной строки"""
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

def print_stats():
    """Вывод статистики"""
    global successful_inserts, failed_inserts
    while running:
        with lock:
            current_successful = successful_inserts
            current_failed = failed_inserts
        
        print(f"Статистика: {current_successful} успешных вставок, {current_failed} неудачных вставок")
        time.sleep(2)

def run_load_test(host, port, num_records=10000, batch_size=100):
    """Запуск нагрузочного теста"""
    global running, successful_inserts, failed_inserts
    
    print(f"Запуск нагрузочного теста на {host}:{port} с целью {num_records} записей...")
    
    conn = None
    try:
        # Подключение к базе данных
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Подготовка запроса для вставки
        insert_query = """
        INSERT INTO test_replication (data)
        VALUES (%s)
        """
        
        batch = []
        count = 0
        
        start_time = time.time()
        
        while running and count < num_records:
            # Генерация случайных данных
            data = generate_random_string(50)
            
            # Добавление данных в пакет
            batch.append((data,))
            
            count += 1
            
            # Если пакет достиг нужного размера, вставляем его в базу
            if len(batch) >= batch_size:
                try:
                    cursor.executemany(insert_query, batch)
                    conn.commit()
                    with lock:
                        successful_inserts += len(batch)
                except Exception as e:
                    print(f"Ошибка при вставке пакета: {e}")
                    conn.rollback()
                    with lock:
                        failed_inserts += len(batch)
                
                batch = []
        
        # Вставка оставшихся данных
        if batch and running:
            try:
                cursor.executemany(insert_query, batch)
                conn.commit()
                with lock:
                    successful_inserts += len(batch)
            except Exception as e:
                print(f"Ошибка при вставке финального пакета: {e}")
                conn.rollback()
                with lock:
                    failed_inserts += len(batch)
        
        end_time = time.time()
        
        print(f"Тест завершен. Время выполнения: {end_time - start_time:.2f} секунд")
        print(f"Успешно вставлено: {successful_inserts}, неудачно: {failed_inserts}")
        
    except Exception as e:
        print(f"Ошибка при выполнении теста: {e}")
    finally:
        if conn:
            conn.close()

def count_records(host, port):
    """Подсчет количества записей в таблице"""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM test_replication")
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    except Exception as e:
        print(f"Ошибка при подсчете записей: {e}")
        return -1

def main():
    if len(sys.argv) < 3:
        print("Использование: python load_test_quorum.py <host> <port> [num_records]")
        sys.exit(1)
    
    host = sys.argv[1]
    port = sys.argv[2]
    num_records = int(sys.argv[3]) if len(sys.argv) > 3 else 10000
    
    # Регистрация обработчика сигнала для корректного завершения
    signal.signal(signal.SIGINT, signal_handler)
    
    # Запуск потока для вывода статистики
    stats_thread = threading.Thread(target=print_stats)
    stats_thread.daemon = True
    stats_thread.start()
    
    # Подсчет записей до теста
    records_before = count_records(host, port)
    print(f"Записей в таблице до теста: {records_before}")
    
    # Запуск нагрузочного теста
    run_load_test(host, port, num_records)
    
    # Подсчет записей после теста
    records_after = count_records(host, port)
    print(f"Записей в таблице после теста: {records_after}")
    print(f"Добавлено записей: {records_after - records_before}")

if __name__ == "__main__":
    main()
