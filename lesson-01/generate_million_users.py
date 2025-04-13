#!/usr/bin/env python
import uuid
import hashlib
import random
from datetime import datetime, timedelta
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Database connection parameters for Docker
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "social_network"
DB_USER = "postgres"
DB_PASSWORD = "postgres"

@contextmanager
def get_db_connection():
    """
    Context manager for database connection
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
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

def generate_and_import_users(num_users=1000000, batch_size=10000):
    """
    Generate and import a specified number of users to the database
    """
    print(f"Starting generation and import of {num_users} users...")
    
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
    
    # Counter for progress reporting
    total_imported = 0
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Prepare insert query
            insert_query = """
            INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """
            
            batch = []
            
            for _ in range(num_users):
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
                
                # If batch reaches desired size, insert it into database
                if len(batch) >= batch_size:
                    cursor.executemany(insert_query, batch)
                    conn.commit()
                    total_imported += len(batch)
                    print(f"Imported {total_imported} users")
                    batch = []
            
            # Insert remaining data
            if batch:
                cursor.executemany(insert_query, batch)
                conn.commit()
                total_imported += len(batch)
                print(f"Imported {total_imported} users")
    
    except Exception as e:
        print(f"Error during import: {e}")
        return
    
    print(f"Import completed. Total imported: {total_imported}")

if __name__ == "__main__":
    # Get number of users to generate from command line argument or use default
    num_users = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
    
    # Run the generation and import
    generate_and_import_users(num_users)
