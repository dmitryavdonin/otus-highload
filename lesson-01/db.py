import psycopg2
from psycopg2.extras import RealDictCursor
import os
from contextlib import contextmanager

# Database connection parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "social_network")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


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
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        yield conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()


@contextmanager
def get_db_cursor():
    """
    Context manager for database cursor
    """
    with get_db_connection() as conn:
        cursor = None
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database query error: {e}")
            raise
        finally:
            if cursor is not None:
                cursor.close()