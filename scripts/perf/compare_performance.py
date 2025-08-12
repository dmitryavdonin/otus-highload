#!/usr/bin/env python3
"""
Скрипт для сравнения производительности PostgreSQL и Redis UDF
"""

import json
import sys
from pathlib import Path

def load_metrics(file_path):
    """Загружает метрики из JSON файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл {file_path} не найден")
        return None
    except json.JSONDecodeError:
        print(f"❌ Ошибка чтения JSON из {file_path}")
        return None

def format_time(seconds):
    """Форматирует время в удобочитаемый вид"""
    if seconds < 1:
        return f"{seconds*1000:.1f}ms"
    else:
        return f"{seconds:.3f}s"

def calculate_improvement(old_value, new_value):
    """Вычисляет улучшение в процентах"""
    if old_value == 0:
        return 0
    improvement = ((old_value - new_value) / old_value) * 100
    return improvement

def compare_metrics(postgres_data, redis_data):
    """Сравнивает метрики производительности"""
    
    print("🔍 СРАВНЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ")
    print("=" * 60)
    print(f"📊 PostgreSQL: {postgres_data['test_config']}")
    print(f"📊 Redis UDF:  {redis_data['test_config']}")
    print()
    
    # Операции для сравнения
    operations = [
        ('user_registration', 'Регистрация пользователей'),
        ('user_login', 'Авторизация пользователей'),
        ('friend_addition', 'Добавление друзей'),
        ('message_send', 'Отправка сообщений'),
        ('message_list', 'Чтение сообщений')
    ]
    
    print("📈 ДЕТАЛЬНОЕ СРАВНЕНИЕ:")
    print("-" * 60)
    
    for op_key, op_name in operations:
        if op_key in postgres_data['metrics'] and op_key in redis_data['metrics']:
            pg_metrics = postgres_data['metrics'][op_key]
            redis_metrics = redis_data['metrics'][op_key]
            
            print(f"\n🔧 {op_name}:")
            print(f"   PostgreSQL: {format_time(pg_metrics['avg'])} (среднее)")
            print(f"   Redis UDF:  {format_time(redis_metrics['avg'])} (среднее)")
            
            improvement = calculate_improvement(pg_metrics['avg'], redis_metrics['avg'])
            if improvement > 0:
                print(f"   ✅ Улучшение: {improvement:.1f}% (Redis UDF быстрее)")
            elif improvement < 0:
                print(f"   ❌ Ухудшение: {abs(improvement):.1f}% (PostgreSQL быстрее)")
            else:
                print(f"   ➖ Одинаковая производительность")
            
            # Операции в секунду
            print(f"   PostgreSQL: {pg_metrics['ops_per_second']:.1f} ops/sec")
            print(f"   Redis UDF:  {redis_metrics['ops_per_second']:.1f} ops/sec")
            
            ops_improvement = calculate_improvement(1/pg_metrics['ops_per_second'], 1/redis_metrics['ops_per_second'])
            if ops_improvement > 0:
                print(f"   📈 Пропускная способность: +{ops_improvement:.1f}%")
    
    print("\n" + "=" * 60)
    print("📊 ОБЩИЕ ВЫВОДЫ:")
    
    # Подсчет общих улучшений
    total_improvements = 0
    total_operations = 0
    
    for op_key, _ in operations:
        if op_key in postgres_data['metrics'] and op_key in redis_data['metrics']:
            pg_avg = postgres_data['metrics'][op_key]['avg']
            redis_avg = redis_data['metrics'][op_key]['avg']
            improvement = calculate_improvement(pg_avg, redis_avg)
            total_improvements += improvement
            total_operations += 1
    
    if total_operations > 0:
        avg_improvement = total_improvements / total_operations
        if avg_improvement > 0:
            print(f"✅ Redis UDF в среднем быстрее на {avg_improvement:.1f}%")
        else:
            print(f"❌ PostgreSQL в среднем быстрее на {abs(avg_improvement):.1f}%")
    
    print("=" * 60)

def main():
    """Основная функция"""
    
    # Пути к файлам метрик
    postgres_file = Path("lesson-07/dialog_metrics_postgresql.json")
    redis_file = Path("lesson-07/dialog_metrics_redis_udf.json")
    
    print("🚀 АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ: PostgreSQL vs Redis UDF")
    print("=" * 60)
    
    # Загружаем данные
    postgres_data = load_metrics(postgres_file)
    redis_data = load_metrics(redis_file)
    
    if not postgres_data or not redis_data:
        print("❌ Не удалось загрузить данные для сравнения")
        sys.exit(1)
    
    # Сравниваем метрики
    compare_metrics(postgres_data, redis_data)

if __name__ == "__main__":
    main() 