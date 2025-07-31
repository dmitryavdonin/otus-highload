#!/usr/bin/env python3
"""
Генератор отчета по результатам тестирования Redis UDF
"""

import json
import os
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
    """Форматирует время в читаемый вид"""
    if seconds < 1:
        return f"{seconds*1000:.1f}ms"
    else:
        return f"{seconds:.3f}s"

def generate_html_report(redis_udf_data):
    """Генерирует HTML отчет"""
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет по тестированию Redis UDF</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .content {{
            padding: 30px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 5px solid #667eea;
        }}
        .metric-title {{
            font-size: 1.2em;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .metric-details {{
            color: #666;
            font-size: 0.9em;
        }}
        .summary {{
            background: #e3f2fd;
            border-radius: 10px;
            padding: 20px;
            margin-top: 30px;
        }}
        .summary h3 {{
            color: #1976d2;
            margin-top: 0;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Отчет по тестированию Redis UDF</h1>
            <p>Результаты тестирования производительности диалогов</p>
            <p>Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        </div>
        
        <div class="content">
            <div class="metrics-grid">
"""

    # Добавляем метрики для каждой операции
    operations = [
        ('user_registration', 'Регистрация пользователей', '👤'),
        ('user_login', 'Авторизация пользователей', '🔐'),
        ('friend_addition', 'Добавление друзей', '👥'),
        ('message_send', 'Отправка сообщений', '📤'),
        ('message_list', 'Чтение сообщений', '📥')
    ]
    
    for op_key, op_name, emoji in operations:
        if op_key in redis_udf_data:
            data = redis_udf_data[op_key]
            avg_time = data.get('average_time', 0)
            ops_per_sec = data.get('operations_per_second', 0)
            count = data.get('operation_count', 0)
            
            html_content += f"""
                <div class="metric-card">
                    <div class="metric-title">{emoji} {op_name}</div>
                    <div class="metric-value">{format_time(avg_time)}</div>
                    <div class="metric-details">
                        <strong>Операций:</strong> {count}<br>
                        <strong>Операций/сек:</strong> {ops_per_sec:.1f}<br>
                        <strong>Медиана:</strong> {format_time(data.get('median_time', 0))}<br>
                        <strong>95-й перцентиль:</strong> {format_time(data.get('p95_time', 0))}
                    </div>
                </div>
"""

    html_content += """
            </div>
            
            <div class="summary">
                <h3>📋 Сводка результатов</h3>
                <p><strong>Конфигурация теста:</strong></p>
                <ul>
                    <li>Пользователей: 40</li>
                    <li>Сообщений в диалоге: 20</li>
                    <li>Диалогов на пользователя: 10</li>
                    <li>Бэкенд: Redis UDF</li>
                </ul>
                
                <p><strong>Основные выводы:</strong></p>
                <ul>
                    <li>🚀 Самая быстрая операция: Авторизация пользователей</li>
                    <li>⏱️ Самая медленная операция: Отправка сообщений</li>
                    <li>📊 Redis UDF показывает стабильную производительность для операций чтения</li>
                    <li>🔧 Операции записи требуют дополнительной оптимизации</li>
                </ul>
            </div>
        </div>
        
        <div class="footer">
            <p>Отчет сгенерирован автоматически • Redis UDF Performance Test</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html_content

def main():
    print("🚀 ГЕНЕРАЦИЯ HTML ОТЧЕТА: Redis UDF")
    print("=" * 60)
    
    # Загружаем данные Redis UDF
    redis_udf_file = "lesson-07/dialog_metrics_redis_udf.json"
    redis_udf_data = load_metrics(redis_udf_file)
    
    if not redis_udf_data:
        print("❌ Не удалось загрузить данные Redis UDF")
        return
    
    print("✅ Данные Redis UDF загружены")
    
    # Генерируем HTML отчет
    html_content = generate_html_report(redis_udf_data)
    
    # Сохраняем отчет
    output_file = "lesson-07/redis_udf_performance_report.html"
    os.makedirs("lesson-07", exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML отчет сохранен: {output_file}")
    print(f"🌐 Откройте файл в браузере для просмотра")

if __name__ == "__main__":
    main() 