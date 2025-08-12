#!/usr/bin/env python
import uuid
import hashlib
import random
from datetime import datetime, timedelta
import sys
import psycopg2
import time
import signal
import threading
from contextlib import contextmanager

# Database connection parameters
DB_HOST = "localhost"  # Will be overridden by command line argument
DB_PORT = "5432"
DB_NAME = "social_network"
DB_USER = "postgres"
DB_PASSWORD = "postgres"

# Global variables for tracking
running = True
successful_inserts = 0
failed_inserts = 0
lock = threading.Lock()

@contextmanager
def get_db_connection(host=DB_HOST):
    """
    Context manager for database connection
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=host,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        yield conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()

def get_password_hash(password: str) -> str:
    """
    Generate a hash for the given password
    """
    return hashlib.sha256(password.encode()).hexdigest()

def generate_random_date(start_year=1950, end_year=2005):
    """
    Generate a random date between start_year and end_year
    """
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)
    
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    
    random_date = start_date + timedelta(days=random_number_of_days)
    return random_date.strftime('%Y-%m-%d')

def signal_handler(sig, frame):
    """
    Handle Ctrl+C to gracefully stop the load test
    """
    global running
    print("\nStopping load test...")
    running = False

def print_stats():
    """
    Print current statistics
    """
    global successful_inserts, failed_inserts
    while running:
        with lock:
            current_successful = successful_inserts
            current_failed = failed_inserts
        
        print(f"Stats: {current_successful} successful inserts, {current_failed} failed inserts")
        time.sleep(2)

def generate_load(host, num_users=1000000, batch_size=100):
    """
    Generate and import a specified number of users to the database
    """
    global running, successful_inserts, failed_inserts
    
    print(f"Starting load test on {host} with target of {num_users} users...")
    
    # Lists for random data generation
    first_names = [
        "Александр", "Алексей", "Анатолий", "Андрей", "Антон", "Аркадий", "Артем", "Борис", 
        "Вадим", "Валентин", "Валерий", "Василий", "Виктор", "Виталий", "Владимир", "Владислав", 
        "Геннадий", "Георгий", "Григорий", "Даниил", "Денис", "Дмитрий", "Евгений", "Егор", 
        "Иван", "Игорь", "Илья", "Кирилл", "Константин", "Леонид", "Максим", "Михаил", 
        "Никита", "Николай", "Олег", "Павел", "Петр", "Роман", "Руслан", "Сергей", 
        "Станислав", "Степан", "Тимофей", "Федор", "Юрий", "Ярослав",
        "Анна", "Алена", "Алина", "Алиса", "Анастасия", "Валентина", "Валерия", "Вера", 
        "Виктория", "Галина", "Дарья", "Диана", "Евгения", "Екатерина", "Елена", "Елизавета", 
        "Инна", "Ирина", "Карина", "Кристина", "Ксения", "Лариса", "Любовь", "Людмила", 
        "Маргарита", "Марина", "Мария", "Надежда", "Наталья", "Нина", "Оксана", "Ольга", 
        "Полина", "Светлана", "София", "Татьяна", "Ульяна", "Юлия", "Яна"
    ]
    
    last_names = [
        "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", 
        "Новиков", "Федоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семенов", "Егоров", 
        "Павлов", "Козлов", "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Никитин", 
        "Захаров", "Зайцев", "Соловьев", "Борисов", "Яковлев", "Григорьев", "Романов", "Воробьев", 
        "Сергеев", "Кузьмин", "Фролов", "Александров", "Дмитриев", "Королев", "Гусев", "Киселев",
        "Иванова", "Смирнова", "Кузнецова", "Попова", "Васильева", "Петрова", "Соколова", "Михайлова", 
        "Новикова", "Федорова", "Морозова", "Волкова", "Алексеева", "Лебедева", "Семенова", "Егорова", 
        "Павлова", "Козлова", "Степанова", "Николаева", "Орлова", "Андреева", "Макарова", "Никитина", 
        "Захарова", "Зайцева", "Соловьева", "Борисова", "Яковлева", "Григорьева", "Романова", "Воробьева", 
        "Сергеева", "Кузьмина", "Фролова", "Александрова", "Дмитриева", "Королева", "Гусева", "Киселева"
    ]
    
    cities = [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Нижний Новгород", 
        "Казань", "Челябинск", "Омск", "Самара", "Ростов-на-Дону", "Уфа", "Красноярск", 
        "Пермь", "Воронеж", "Волгоград", "Краснодар", "Саратов", "Тюмень", "Тольятти", 
        "Ижевск", "Барнаул", "Ульяновск", "Иркутск", "Хабаровск", "Ярославль", "Владивосток", 
        "Махачкала", "Томск", "Оренбург", "Кемерово", "Новокузнецк", "Рязань", "Астрахань", 
        "Набережные Челны", "Пенза", "Липецк", "Киров", "Чебоксары", "Тула", "Калининград"
    ]
    
    # Default password hash (using '12345' as default password)
    default_password = get_password_hash('12345')
    
    # Default biography
    default_biography = "Пользователь не заполнил информацию о себе"
    
    try:
        with get_db_connection(host) as conn:
            cursor = conn.cursor()
            
            # Prepare insert query
            insert_query = """
            INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """
            
            batch = []
            count = 0
            
            while running and count < num_users:
                # Generate random user data
                first_name = random.choice(first_names)
                second_name = random.choice(last_names)
                birthdate = generate_random_date()
                city = random.choice(cities)
                user_id = str(uuid.uuid4())
                
                # Add data to batch
                batch.append((
                    user_id, 
                    first_name, 
                    second_name, 
                    birthdate, 
                    default_biography, 
                    city, 
                    default_password
                ))
                
                count += 1
                
                # If batch reaches desired size, insert it into database
                if len(batch) >= batch_size:
                    try:
                        cursor.executemany(insert_query, batch)
                        conn.commit()
                        with lock:
                            successful_inserts += len(batch)
                    except Exception as e:
                        print(f"Error during batch insert: {e}")
                        with lock:
                            failed_inserts += len(batch)
                    
                    batch = []
            
            # Insert remaining data
            if batch and running:
                try:
                    cursor.executemany(insert_query, batch)
                    conn.commit()
                    with lock:
                        successful_inserts += len(batch)
                except Exception as e:
                    print(f"Error during final batch insert: {e}")
                    with lock:
                        failed_inserts += len(batch)
    
    except Exception as e:
        print(f"Error during load test: {e}")
    
    print(f"Load test completed. Total successful inserts: {successful_inserts}, failed: {failed_inserts}")

def count_users_in_db(host):
    """
    Count the number of users in the database
    """
    try:
        with get_db_connection(host) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        print(f"Error counting users: {e}")
        return -1

def main():
    if len(sys.argv) < 2:
        print("Usage: python load_test_replication.py <db_host> [num_users]")
        sys.exit(1)
    
    host = sys.argv[1]
    num_users = int(sys.argv[2]) if len(sys.argv) > 2 else 1000000
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start stats printing thread
    stats_thread = threading.Thread(target=print_stats)
    stats_thread.daemon = True
    stats_thread.start()
    
    # Count users before test
    users_before = count_users_in_db(host)
    print(f"Users in database before test: {users_before}")
    
    # Run the load test
    start_time = time.time()
    generate_load(host, num_users)
    end_time = time.time()
    
    # Count users after test
    users_after = count_users_in_db(host)
    print(f"Users in database after test: {users_after}")
    print(f"Users added: {users_after - users_before}")
    print(f"Time elapsed: {end_time - start_time:.2f} seconds")
    print(f"Final stats: {successful_inserts} successful inserts, {failed_inserts} failed inserts")

if __name__ == "__main__":
    main()
