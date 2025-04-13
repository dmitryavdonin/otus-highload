#!/usr/bin/env python
import csv
import uuid
import hashlib
from datetime import datetime
import sys
import os
from db import get_db_connection, get_db_cursor

def get_password_hash(password: str) -> str:
    """
    Generate a hash for the given password
    """
    return hashlib.sha256(password.encode()).hexdigest()

def import_users_from_csv(csv_file_path: str, batch_size=1000):
    """
    Import users from CSV file to the database
    
    CSV file format is expected to have columns for name, birthdate, city
    """
    if not os.path.exists(csv_file_path):
        print(f"Error: File {csv_file_path} not found.")
        return
    
    print(f"Starting import from {csv_file_path}...")
    
    # Default password hash (using '12345' as default password)
    default_password = get_password_hash('12345')
    
    # Default biography
    default_biography = "Пользователь не заполнил информацию о себе"
    
    # Counter for progress reporting
    total_imported = 0
    error_count = 0
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Prepare insert query
            insert_query = """
            INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """
            
            # Read CSV file and insert data
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                batch = []
                
                # Skip header if exists
                try:
                    header = next(reader, None)
                except Exception as e:
                    print(f"Warning: Could not read header: {e}")
                
                for row in reader:
                    try:
                        if len(row) >= 3:  # Check if row has necessary data
                            # Split full name into first and last name
                            full_name = row[0].strip()
                            name_parts = full_name.split(' ', 1)
                            
                            if len(name_parts) == 2:
                                first_name, second_name = name_parts
                            else:
                                # If name couldn't be split, use full name as first_name
                                first_name = full_name
                                second_name = "Unknown"
                            
                            # Get birthdate
                            try:
                                birthdate = row[1].strip()
                                # Validate date format
                                datetime.strptime(birthdate, '%Y-%m-%d')
                            except:
                                birthdate = "2000-01-01"  # Default value
                            
                            # Get city
                            try:
                                city = row[2].strip()
                            except:
                                city = "Unknown"  # Default value
                            
                            # Generate unique ID
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
                    except Exception as e:
                        error_count += 1
                        print(f"Error processing row: {e}")
                        # Continue with next row
                
                # Insert remaining data
                if batch:
                    cursor.executemany(insert_query, batch)
                    conn.commit()
                    total_imported += len(batch)
                    print(f"Imported {total_imported} users")
    
    except Exception as e:
        print(f"Error during import: {e}")
        return
    
    print(f"Import completed. Total imported: {total_imported}, Errors: {error_count}")

if __name__ == "__main__":
    # Get CSV file path from command line argument or use default
    csv_file_path = sys.argv[1] if len(sys.argv) > 1 else "people.v2.csv"
    
    # Run the import
    import_users_from_csv(csv_file_path)