import csv
import os
import subprocess
import tempfile

def create_sql_file(csv_file, output_file):
    """Создает SQL файл для импорта данных из CSV"""
    # Попробуем разные кодировки
    encodings = ['utf-8', 'cp1251', 'latin1', 'windows-1251']
    
    for encoding in encodings:
        try:
            print(f"Trying encoding: {encoding}")
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                with open(output_file, 'w', encoding='utf-8') as out:
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
                    
                    # Подготавливаем данные для вставки во временную таблицу
                    out.write("INSERT INTO temp_users (full_name, birthdate, city) VALUES\n")
                    
                    rows = []
                    for i, row in enumerate(reader):
                        if len(row) >= 3:
                            full_name = row[0].replace("'", "''")  # Экранируем одинарные кавычки
                            birthdate = row[1]
                            city = row[2].replace("'", "''")  # Экранируем одинарные кавычки
                            
                            rows.append(f"('{full_name}', '{birthdate}', '{city}')")
                            
                            # Записываем по 1000 строк за раз
                            if len(rows) >= 1000:
                                out.write(",\n".join(rows))
                                out.write(";\n\n")
                                
                                # Вставляем данные из временной таблицы в основную таблицу
                                out.write("""
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
                                
                                # Начинаем новую вставку
                                out.write("INSERT INTO temp_users (full_name, birthdate, city) VALUES\n")
                                rows = []
                                
                                print(f"Processed {i+1} rows")
                    
                    # Вставляем оставшиеся строки
                    if rows:
                        out.write(",\n".join(rows))
                        out.write(";\n\n")
                        
                        # Вставляем данные из временной таблицы в основную таблицу
                        out.write("""
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
                    
                    print(f"SQL file created: {output_file}")
                    return True
        except UnicodeDecodeError:
            print(f"Failed with encoding: {encoding}")
            continue
    
    print("Could not find a suitable encoding for the CSV file")
    return False

def import_data_to_postgres(sql_file):
    """Импортирует данные из SQL файла в PostgreSQL через Docker"""
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
    except subprocess.CalledProcessError as e:
        print(f"Error importing data: {e}")

if __name__ == "__main__":
    # Создаем временный SQL файл
    with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Создаем SQL файл из CSV
        if create_sql_file('people.v2.csv', tmp_path):
            # Импортируем данные в PostgreSQL
            import_data_to_postgres(tmp_path)
        else:
            print("Failed to create SQL file")
    finally:
        # Удаляем временный файл
        if os.path.exists(tmp_path):
            os.remove(tmp_path)