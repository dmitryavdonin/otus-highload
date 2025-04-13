import csv
import os
import subprocess
import tempfile

def create_import_script(csv_file, batch_size=1000):
    """
    Создает SQL скрипт для импорта данных из CSV файла в таблицу users.
    
    Args:
        csv_file: Путь к CSV файлу
        batch_size: Размер пакета для вставки
    
    Returns:
        Путь к созданному SQL файлу
    """
    # Создаем временный файл для SQL скрипта
    with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as tmp:
        tmp_path = tmp.name
    
    # Пробуем разные кодировки для чтения CSV файла
    encodings = ['utf-8', 'cp1251', 'latin1', 'windows-1251']
    success = False
    
    for encoding in encodings:
        try:
            print(f"Trying encoding: {encoding}")
            
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                with open(tmp_path, 'w', encoding='utf-8') as out:
                    # Начинаем транзакцию
                    out.write("BEGIN;\n\n")
                    
                    # Создаем временную таблицу для импорта
                    out.write("""
CREATE TEMPORARY TABLE temp_users (
    full_name VARCHAR(200),
    birthdate DATE,
    city VARCHAR(100)
);
                    \n""")
                    
                    # Обрабатываем данные пакетами
                    batch_count = 0
                    rows = []
                    
                    for i, row in enumerate(reader):
                        if len(row) >= 3:
                            full_name = row[0].replace("'", "''")  # Экранируем одинарные кавычки
                            birthdate = row[1]
                            city = row[2].replace("'", "''")  # Экранируем одинарные кавычки
                            
                            rows.append(f"('{full_name}', '{birthdate}', '{city}')")
                            
                            # Если достигли размера пакета, записываем данные
                            if len(rows) >= batch_size:
                                batch_count += 1
                                
                                # Вставляем данные во временную таблицу
                                out.write(f"-- Batch {batch_count}\n")
                                out.write("INSERT INTO temp_users (full_name, birthdate, city) VALUES\n")
                                out.write(",\n".join(rows))
                                out.write(";\n\n")
                                
                                # Вставляем данные из временной таблицы в основную таблицу
                                out.write("""
-- Разделяем имя и фамилию по пробелу и вставляем в основную таблицу
INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password, created_at)
SELECT 
    md5(random()::text || clock_timestamp()::text)::uuid,
    CASE 
        WHEN position(' ' in full_name) > 0 
        THEN substring(full_name from 1 for position(' ' in full_name) - 1) 
        ELSE full_name 
    END as first_name,
    CASE 
        WHEN position(' ' in full_name) > 0 
        THEN substring(full_name from position(' ' in full_name) + 1) 
        ELSE 'Unknown' 
    END as second_name,
    birthdate,
    'Пользователь не заполнил информацию о себе',
    city,
    'password123',
    NOW()
FROM temp_users;
                                \n""")
                                
                                # Очищаем временную таблицу для следующей партии
                                out.write("DELETE FROM temp_users;\n\n")
                                
                                rows = []
                                print(f"Processed {i+1} rows")
                    
                    # Обрабатываем оставшиеся строки
                    if rows:
                        batch_count += 1
                        
                        # Вставляем данные во временную таблицу
                        out.write(f"-- Batch {batch_count}\n")
                        out.write("INSERT INTO temp_users (full_name, birthdate, city) VALUES\n")
                        out.write(",\n".join(rows))
                        out.write(";\n\n")
                        
                        # Вставляем данные из временной таблицы в основную таблицу
                        out.write("""
-- Разделяем имя и фамилию по пробелу и вставляем в основную таблицу
INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password, created_at)
SELECT 
    md5(random()::text || clock_timestamp()::text)::uuid,
    CASE 
        WHEN position(' ' in full_name) > 0 
        THEN substring(full_name from 1 for position(' ' in full_name) - 1) 
        ELSE full_name 
    END as first_name,
    CASE 
        WHEN position(' ' in full_name) > 0 
        THEN substring(full_name from position(' ' in full_name) + 1) 
        ELSE 'Unknown' 
    END as second_name,
    birthdate,
    'Пользователь не заполнил информацию о себе',
    city,
    'password123',
    NOW()
FROM temp_users;
                        \n""")
                    
                    # Завершаем транзакцию
                    out.write("COMMIT;\n")
                    
                    print(f"SQL script created: {tmp_path}")
                    success = True
                    break
        except UnicodeDecodeError:
            print(f"Failed with encoding: {encoding}")
            continue
    
    if not success:
        print("Could not find a suitable encoding for the CSV file")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return None
    
    return tmp_path

def import_to_postgres(sql_file):
    """
    Импортирует данные из SQL файла в PostgreSQL через Docker.
    
    Args:
        sql_file: Путь к SQL файлу
    
    Returns:
        True в случае успеха, False в случае ошибки
    """
    try:
        # Копируем SQL файл в контейнер
        copy_cmd = f'docker cp "{sql_file}" lesson-01-db-1:/tmp/import.sql'
        print(f"Running: {copy_cmd}")
        subprocess.run(copy_cmd, shell=True, check=True)
        
        # Выполняем SQL файл в PostgreSQL
        exec_cmd = 'docker exec lesson-01-db-1 psql -U postgres -d social_network -f /tmp/import.sql'
        print(f"Running: {exec_cmd}")
        subprocess.run(exec_cmd, shell=True, check=True)
        
        print("Data import completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error importing data: {e}")
        return False

def check_import_results():
    """
    Проверяет результаты импорта данных.
    """
    try:
        # Получаем количество записей в таблице users
        count_cmd = 'docker exec lesson-01-db-1 psql -U postgres -d social_network -c "SELECT COUNT(*) FROM users"'
        print(f"Running: {count_cmd}")
        subprocess.run(count_cmd, shell=True, check=True)
        
        # Получаем примеры записей
        sample_cmd = 'docker exec lesson-01-db-1 psql -U postgres -d social_network -c "SELECT * FROM users LIMIT 5"'
        print(f"Running: {sample_cmd}")
        subprocess.run(sample_cmd, shell=True, check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error checking import results: {e}")
        return False

if __name__ == "__main__":
    # Создаем SQL скрипт для импорта данных
    sql_file = create_import_script('people.v2.csv', batch_size=5000)
    
    if sql_file:
        try:
            # Импортируем данные в PostgreSQL
            if import_to_postgres(sql_file):
                # Проверяем результаты импорта
                check_import_results()
        finally:
            # Удаляем временный файл
            if os.path.exists(sql_file):
                os.remove(sql_file)
    else:
        print("Failed to create SQL script")