#!/usr/bin/env python3
"""
Скрипт для сравнения производительности PostgreSQL, Redis и Redis UDF
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

def calculate_improvement(baseline, value):
    """Вычисляет улучшение относительно baseline в процентах"""
    if baseline == 0:
        return 0
    improvement = ((baseline - value) / baseline) * 100
    return improvement

def compare_all_backends(postgres_data, redis_data, redis_udf_data):
    """Сравнивает метрики производительности всех бэкендов"""
    
    print("🚀 ПОЛНОЕ СРАВНЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ")
    print("=" * 80)
    print(f"📊 Конфигурация тестов: {postgres_data['test_config']}")
    print()
    
    # Операции для сравнения
    operations = [
        ('user_registration', 'Регистрация пользователей'),
        ('user_login', 'Авторизация пользователей'),
        ('friend_addition', 'Добавление друзей'),
        ('message_send', 'Отправка сообщений'),
        ('message_list', 'Чтение сообщений')
    ]
    
    print("📈 СРАВНИТЕЛЬНАЯ ТАБЛИЦА (среднее время):")
    print("-" * 80)
    print(f"{'Операция':<25} {'PostgreSQL':<15} {'Redis':<15} {'Redis UDF':<15} {'Лучший':<10}")
    print("-" * 80)
    
    winners = {'PostgreSQL': 0, 'Redis': 0, 'Redis UDF': 0}
    
    for op_key, op_name in operations:
        if (op_key in postgres_data['metrics'] and 
            op_key in redis_data['metrics'] and 
            op_key in redis_udf_data['metrics']):
            
            pg_avg = postgres_data['metrics'][op_key]['avg']
            redis_avg = redis_data['metrics'][op_key]['avg']
            redis_udf_avg = redis_udf_data['metrics'][op_key]['avg']
            
            # Определяем лучший результат
            times = {'PostgreSQL': pg_avg, 'Redis': redis_avg, 'Redis UDF': redis_udf_avg}
            best_backend = min(times, key=times.get)
            winners[best_backend] += 1
            
            print(f"{op_name:<25} {format_time(pg_avg):<15} {format_time(redis_avg):<15} {format_time(redis_udf_avg):<15} {best_backend:<10}")
    
    print("-" * 80)
    print(f"{'ИТОГО ПОБЕД:':<25} {winners['PostgreSQL']:<15} {winners['Redis']:<15} {winners['Redis UDF']:<15}")
    print()
    
    # Детальное сравнение
    print("📊 ДЕТАЛЬНОЕ СРАВНЕНИЕ:")
    print("=" * 80)
    
    for op_key, op_name in operations:
        if (op_key in postgres_data['metrics'] and 
            op_key in redis_data['metrics'] and 
            op_key in redis_udf_data['metrics']):
            
            pg_metrics = postgres_data['metrics'][op_key]
            redis_metrics = redis_data['metrics'][op_key]
            redis_udf_metrics = redis_udf_data['metrics'][op_key]
            
            print(f"\n🔧 {op_name}:")
            print(f"   PostgreSQL: {format_time(pg_metrics['avg'])} | {pg_metrics['ops_per_second']:.1f} ops/sec")
            print(f"   Redis:      {format_time(redis_metrics['avg'])} | {redis_metrics['ops_per_second']:.1f} ops/sec")
            print(f"   Redis UDF:  {format_time(redis_udf_metrics['avg'])} | {redis_udf_metrics['ops_per_second']:.1f} ops/sec")
            
            # Сравнение с PostgreSQL как baseline
            redis_vs_pg = calculate_improvement(pg_metrics['avg'], redis_metrics['avg'])
            udf_vs_pg = calculate_improvement(pg_metrics['avg'], redis_udf_metrics['avg'])
            
            print(f"   📈 Redis vs PostgreSQL: {redis_vs_pg:+.1f}%")
            print(f"   📈 Redis UDF vs PostgreSQL: {udf_vs_pg:+.1f}%")
            
            # Сравнение Redis UDF с обычным Redis
            udf_vs_redis = calculate_improvement(redis_metrics['avg'], redis_udf_metrics['avg'])
            print(f"   📈 Redis UDF vs Redis: {udf_vs_redis:+.1f}%")
    
    print("\n" + "=" * 80)
    print("🏆 ОБЩИЕ ВЫВОДЫ:")
    
    # Определяем общего победителя
    overall_winner = max(winners, key=winners.get)
    print(f"🥇 Общий лидер: {overall_winner} ({winners[overall_winner]} побед из {len(operations)})")
    
    # Рекомендации по использованию
    print("\n💡 РЕКОМЕНДАЦИИ ПО ИСПОЛЬЗОВАНИЮ:")
    
    if winners['PostgreSQL'] >= 3:
        print("✅ PostgreSQL - лучший выбор для большинства операций")
        print("   • Используйте для основного хранения данных")
        print("   • Подходит для сложных запросов и транзакций")
    
    if winners['Redis'] >= 2:
        print("✅ Redis - хорошая производительность")
        print("   • Используйте для кэширования")
        print("   • Подходит для быстрого доступа к данным")
    
    if winners['Redis UDF'] >= 2:
        print("✅ Redis UDF - специализированные операции")
        print("   • Используйте для custom логики")
        print("   • Требует дополнительной оптимизации")
    else:
        print("⚠️  Redis UDF - требует оптимизации")
        print("   • Рассмотрите оптимизацию Lua кода")
        print("   • Используйте батчинг операций")
    
    print("\n🔄 ГИБРИДНЫЙ ПОДХОД:")
    print("   • PostgreSQL - основное хранение")
    print("   • Redis - кэширование и сессии")
    print("   • Redis UDF - специфические операции после оптимизации")
    
    print("=" * 80)

def main():
    """Основная функция"""
    
    # Пути к файлам метрик
    postgres_file = Path("lesson-07/dialog_metrics_postgresql.json")
    redis_file = Path("lesson-07/dialog_metrics_redis.json")
    redis_udf_file = Path("lesson-07/dialog_metrics_redis_udf.json")
    
    print("🚀 АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ: PostgreSQL vs Redis vs Redis UDF")
    print("=" * 80)
    
    # Загружаем данные
    postgres_data = load_metrics(postgres_file)
    redis_data = load_metrics(redis_file)
    redis_udf_data = load_metrics(redis_udf_file)
    
    if not all([postgres_data, redis_data, redis_udf_data]):
        print("❌ Не удалось загрузить все данные для сравнения")
        sys.exit(1)
    
    # Сравниваем метрики
    compare_all_backends(postgres_data, redis_data, redis_udf_data)

if __name__ == "__main__":
    main() 