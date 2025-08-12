#!/usr/bin/env python3
"""
Скрипт для сравнения операций с диалогами: PostgreSQL vs Redis UDF
Генерирует HTML отчет
"""

import json
import sys
from pathlib import Path
from datetime import datetime

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

def generate_html_report(postgres_data, redis_udf_data):
    """Генерирует HTML отчет сравнения операций с диалогами"""
    
    # Операции с диалогами
    dialog_operations = [
        ('message_send', 'Отправка сообщений'),
        ('message_list', 'Чтение сообщений')
    ]
    
    # Начинаем формировать HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет о сравнении производительности операций с диалогами</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2980b9;
            margin-top: 20px;
        }}
        h3 {{
            color: #34495e;
            margin-top: 15px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .note {{
            background-color: #f8f9fa;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin-bottom: 20px;
        }}
        .success {{
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 10px;
            margin-bottom: 20px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .config-section {{
            background-color: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin-bottom: 20px;
        }}
        .metric-section {{
            margin-bottom: 25px;
        }}
        .improvement {{
            font-weight: bold;
        }}
        .improvement.positive {{
            color: #28a745;
        }}
        .improvement.negative {{
            color: #dc3545;
        }}
        ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <h1>Отчет о сравнении производительности операций с диалогами</h1>
    <p>Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
    <p>Сравнение: PostgreSQL vs Redis UDF</p>
    
    <div class="success">
        <p><strong>РЕЗУЛЬТАТ:</strong> Тестирование завершено успешно. Проведено сравнение производительности операций с диалогами.</p>
    </div>
    
    <div class="section">
        <h2>1. Конфигурация тестирования</h2>
        <div class="config-section">
            <table>
                <tr>
                    <th>Параметр</th>
                    <th>Значение</th>
                </tr>
                <tr>
                    <td>Количество пользователей</td>
                    <td>{postgres_data['test_config']['users_count']}</td>
                </tr>
                <tr>
                    <td>Сообщений в диалоге</td>
                    <td>{postgres_data['test_config']['messages_per_dialog']}</td>
                </tr>
                <tr>
                    <td>Диалогов на пользователя</td>
                    <td>{postgres_data['test_config']['dialogs_per_user']}</td>
                </tr>
                <tr>
                    <td>Общее количество сообщений</td>
                    <td>{postgres_data['test_config']['users_count'] * postgres_data['test_config']['messages_per_dialog'] * postgres_data['test_config']['dialogs_per_user']}</td>
                </tr>
                <tr>
                    <td>Общее количество операций чтения</td>
                    <td>{postgres_data['test_config']['users_count'] * postgres_data['test_config']['dialogs_per_user']}</td>
                </tr>
            </table>
        </div>
    </div>
"""

    # Добавляем сравнительную таблицу
    html_content += """
    <div class="section">
        <h2>2. Сводная таблица результатов</h2>
        <table>
            <thead>
                <tr>
                    <th>Операция</th>
                    <th>PostgreSQL (сек)</th>
                    <th>Redis UDF (сек)</th>
                    <th>Лучший результат</th>
                    <th>Улучшение</th>
                </tr>
            </thead>
            <tbody>
"""

    winners = {'PostgreSQL': 0, 'Redis UDF': 0}
    
    for op_key, op_name in dialog_operations:
        if op_key in postgres_data['metrics'] and op_key in redis_udf_data['metrics']:
            pg_metrics = postgres_data['metrics'][op_key]
            redis_metrics = redis_udf_data['metrics'][op_key]
            
            pg_time = format_time(pg_metrics['avg'])
            redis_time = format_time(redis_metrics['avg'])
            
            # Определяем победителя
            if pg_metrics['avg'] < redis_metrics['avg']:
                winner = 'PostgreSQL'
                improvement = calculate_improvement(redis_metrics['avg'], pg_metrics['avg'])
                improvement_text = f"+{improvement:.1f}%"
                improvement_class = "positive"
            else:
                winner = 'Redis UDF'
                improvement = calculate_improvement(pg_metrics['avg'], redis_metrics['avg'])
                improvement_text = f"+{improvement:.1f}%"
                improvement_class = "positive"
            
            winners[winner] += 1
            
            html_content += f"""
                <tr>
                    <td>{op_name}</td>
                    <td>{pg_metrics['avg']:.3f}</td>
                    <td>{redis_metrics['avg']:.3f}</td>
                    <td>{winner}</td>
                    <td><span class="improvement {improvement_class}">{improvement_text}</span></td>
                </tr>
"""

    html_content += """
            </tbody>
        </table>
    </div>
"""

    # Добавляем детальные метрики для каждой операции
    html_content += """
    <div class="section">
        <h2>3. Детальный анализ операций</h2>
"""
    
    section_num = 1
    for op_key, op_name in dialog_operations:
        if op_key in postgres_data['metrics'] and op_key in redis_udf_data['metrics']:
            pg_metrics = postgres_data['metrics'][op_key]
            redis_metrics = redis_udf_data['metrics'][op_key]
            
            html_content += f"""
        <div class="metric-section">
            <h3>3.{section_num}. {op_name}</h3>
            <table>
                <tr>
                    <th>Метрика</th>
                    <th>PostgreSQL</th>
                    <th>Redis UDF</th>
                </tr>
                <tr>
                    <td>Среднее время выполнения</td>
                    <td>{pg_metrics['avg']:.3f} сек</td>
                    <td>{redis_metrics['avg']:.3f} сек</td>
                </tr>
                <tr>
                    <td>Операций в секунду</td>
                    <td>{pg_metrics['ops_per_second']:.1f}</td>
                    <td>{redis_metrics['ops_per_second']:.1f}</td>
                </tr>
                <tr>
                    <td>Медиана</td>
                    <td>{pg_metrics['median']:.3f} сек</td>
                    <td>{redis_metrics['median']:.3f} сек</td>
                </tr>
                <tr>
                    <td>95-й перцентиль</td>
                    <td>{pg_metrics['p95']:.3f} сек</td>
                    <td>{redis_metrics['p95']:.3f} сек</td>
                </tr>
            </table>
        </div>
"""
            section_num += 1

    html_content += """
    </div>
"""

    # Добавляем итоговую секцию
    overall_winner = max(winners, key=winners.get)
    total_operations = len(dialog_operations)
    
    html_content += f"""
    <div class="section">
        <h2>4. Выводы</h2>
        <p>По результатам тестирования можно сделать следующие выводы:</p>
        <ul>
            <li>Проведено сравнение производительности операций с диалогами между PostgreSQL и Redis UDF</li>
            <li>Общий победитель: {overall_winner}</li>
        </ul>
    </div>

    <p>Отчет сгенерирован автоматически {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
</body>
</html>
"""

    return html_content

def main():
    """Основная функция"""
    
    # Пути к файлам метрик
    postgres_file = Path("lesson-07/dialog_metrics_postgresql.json")
    redis_udf_file = Path("lesson-07/dialog_metrics_redis_udf.json")
    
    print("🚀 ГЕНЕРАЦИЯ HTML ОТЧЕТА: Сравнение операций с диалогами")
    print("=" * 60)
    
    # Загружаем данные
    postgres_data = load_metrics(postgres_file)
    redis_udf_data = load_metrics(redis_udf_file)
    
    if not postgres_data or not redis_udf_data:
        print("❌ Не удалось загрузить данные для сравнения")
        sys.exit(1)
    
    # Генерируем HTML отчет
    html_content = generate_html_report(postgres_data, redis_udf_data)
    
    # Сохраняем отчет
    output_file = Path("lesson-07/dialog_performance_comparison.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML отчет создан: {output_file}")
    print(f"🌐 Откройте файл в браузере для просмотра")

if __name__ == "__main__":
    main() 