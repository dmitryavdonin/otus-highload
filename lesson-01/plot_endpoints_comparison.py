#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 10})

# Параметры сглаживания
WINDOW_SIZE = 20  # Размер окна для скользящего среднего

# Получаем абсолютный путь к директории скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))

def parse_jtl_file(file_path):
    """
    Парсит JTL файл и возвращает DataFrame с данными.
    JTL файл имеет CSV формат с разделителем-запятой.
    """
    # Определяем имена столбцов для JTL файла
    columns = [
        'timeStamp', 'elapsed', 'label', 'responseCode', 'responseMessage',
        'threadName', 'dataType', 'success', 'failureMessage', 'bytes',
        'sentBytes', 'grpThreads', 'allThreads', 'URL', 'Latency',
        'IdleTime', 'Connect'
    ]
    
    # Читаем JTL файл
    df = pd.read_csv(file_path, header=None, names=columns)
    
    # Преобразуем timestamp в datetime
    df['datetime'] = pd.to_datetime(df['timeStamp'], unit='ms')
    
    return df

def filter_endpoint_data(df, endpoint_label):
    """
    Фильтрует данные по метке эндпоинта.
    """
    return df[df['label'].str.contains(endpoint_label)]

def calculate_throughput(df, window_size=WINDOW_SIZE):
    """
    Рассчитывает throughput (запросов в секунду) на основе временных меток.
    """
    # Создаем копию DataFrame, чтобы избежать предупреждений SettingWithCopyWarning
    df_copy = df.copy()
    
    # Сортируем по времени
    df_copy = df_copy.sort_values('datetime')
    
    # Рассчитываем разницу во времени между последовательными запросами (в секундах)
    df_copy.loc[:, 'time_diff'] = df_copy['datetime'].diff().dt.total_seconds()
    
    # Избегаем деления на ноль (для первой строки)
    df_copy.loc[:, 'time_diff'] = df_copy['time_diff'].replace({0: np.nan})
    df_copy.loc[:, 'time_diff'] = df_copy['time_diff'].bfill()
    
    # Throughput = 1 / (разница во времени). Где diff все еще NaN, устанавливаем throughput в 0.
    df_copy.loc[:, 'throughput'] = 1 / df_copy['time_diff']
    df_copy.loc[:, 'throughput'] = df_copy['throughput'].fillna(0)
    
    # Сглаживаем throughput с помощью скользящего среднего
    df_copy.loc[:, 'throughput_ma'] = df_copy['throughput'].rolling(window=window_size, center=True).mean()
    df_copy.loc[:, 'throughput_ma'] = df_copy['throughput_ma'].fillna(df_copy['throughput'])
    
    return df_copy

def smooth_latency(df, window_size=WINDOW_SIZE):
    """
    Сглаживает данные о latency с помощью скользящего среднего.
    """
    # Создаем копию DataFrame, чтобы избежать предупреждений SettingWithCopyWarning
    df_copy = df.copy()
    df_copy.loc[:, 'elapsed_ma'] = df_copy['elapsed'].rolling(window=window_size, center=True).mean()
    # Заменяем NaN (например, в начале/конце) исходными значениями
    df_copy.loc[:, 'elapsed_ma'] = df_copy['elapsed_ma'].fillna(df_copy['elapsed'])
    return df_copy

def create_latency_plot(user_get_df, user_search_df):
    """
    Создает график latency для эндпоинтов user/get и user/search.
    """
    plt.figure(figsize=(12, 6))
    
    # Сглаживаем данные
    user_get_df = smooth_latency(user_get_df)
    user_search_df = smooth_latency(user_search_df)
    
    # Строим графики
    plt.plot(range(len(user_get_df)), user_get_df['elapsed_ma'], 
             label="user/get", color="blue", linewidth=2)
    plt.plot(range(len(user_search_df)), user_search_df['elapsed_ma'], 
             label="user/search", color="orange", linewidth=2)
    
    plt.xlabel("Запросы")
    plt.ylabel("Время ответа (мс)")
    plt.title(f"Latency – сравнение эндпоинтов (скользящее среднее, окно={WINDOW_SIZE})")
    plt.legend()
    plt.tight_layout()
    
    out_path = os.path.join(script_dir, "latency_endpoints_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Latency figure saved to: {out_path}")

def create_throughput_plot(user_get_df, user_search_df):
    """
    Создает график throughput для эндпоинтов user/get и user/search.
    """
    plt.figure(figsize=(12, 6))
    
    # Рассчитываем и сглаживаем throughput
    user_get_df = calculate_throughput(user_get_df)
    user_search_df = calculate_throughput(user_search_df)
    
    # Строим графики
    plt.plot(range(len(user_get_df)), user_get_df['throughput_ma'], 
             label="user/get", color="blue", linewidth=2)
    plt.plot(range(len(user_search_df)), user_search_df['throughput_ma'], 
             label="user/search", color="orange", linewidth=2)
    
    plt.xlabel("Запросы")
    plt.ylabel("Запросов в секунду")
    plt.title(f"Throughput – сравнение эндпоинтов (скользящее среднее, окно={WINDOW_SIZE})")
    plt.legend()
    plt.tight_layout()
    
    out_path = os.path.join(script_dir, "throughput_endpoints_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Throughput figure saved to: {out_path}")

def create_boxplot_comparison(user_get_df, user_search_df):
    """
    Создает диаграмму размаха (boxplot) для сравнения latency эндпоинтов.
    """
    plt.figure(figsize=(10, 6))
    
    # Создаем данные для boxplot
    data = [user_get_df['elapsed'], user_search_df['elapsed']]
    labels = ['user/get', 'user/search']
    
    # Строим boxplot с использованием параметра tick_labels вместо labels
    # для совместимости с matplotlib 3.9+
    plt.boxplot(data, tick_labels=labels)
    plt.ylabel('Время ответа (мс)')
    plt.title('Статистическое сравнение времени ответа эндпоинтов')
    
    out_path = os.path.join(script_dir, "boxplot_endpoints_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Boxplot figure saved to: {out_path}")

def create_combined_plot(user_get_df, user_search_df):
    """
    Создает комбинированный график с исходными и сглаженными данными.
    """
    plt.figure(figsize=(12, 6))
    
    # Сглаживаем данные
    user_get_df = smooth_latency(user_get_df)
    user_search_df = smooth_latency(user_search_df)
    
    # Строим графики исходных данных (полупрозрачные)
    plt.plot(range(len(user_get_df)), user_get_df['elapsed'], 
             label="user/get (исходные)", alpha=0.2, color="blue")
    plt.plot(range(len(user_search_df)), user_search_df['elapsed'], 
             label="user/search (исходные)", alpha=0.2, color="orange")
    
    # Строим графики сглаженных данных
    plt.plot(range(len(user_get_df)), user_get_df['elapsed_ma'], 
             label="user/get (сглаженные)", linewidth=2, color="blue")
    plt.plot(range(len(user_search_df)), user_search_df['elapsed_ma'], 
             label="user/search (сглаженные)", linewidth=2, color="orange")
    
    plt.xlabel("Запросы")
    plt.ylabel("Время ответа (мс)")
    plt.title("Сравнение времени ответа эндпоинтов (исходные и сглаженные данные)")
    plt.legend()
    plt.tight_layout()
    
    out_path = os.path.join(script_dir, "combined_endpoints_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Combined figure saved to: {out_path}")

def main():
    """
    Основная функция для построения графиков.
    """
    print("Создание диаграмм сравнения производительности эндпоинтов user/get и user/search...")
    
    # Путь к JTL файлу
    jtl_file_path = os.path.join(script_dir, "results.jtl")
    
    # Парсим JTL файл
    df = parse_jtl_file(jtl_file_path)
    
    # Фильтруем данные по эндпоинтам
    user_get_df = filter_endpoint_data(df, "User Get By ID")
    user_search_df = filter_endpoint_data(df, "User Search")
    
    # Выводим количество записей для каждого эндпоинта
    print(f"Количество записей для user/get: {len(user_get_df)}")
    print(f"Количество записей для user/search: {len(user_search_df)}")
    
    # Определяем минимальное количество записей
    min_records = min(len(user_get_df), len(user_search_df))
    max_records = 100  # Желаемое количество записей
    
    # Если у нас недостаточно записей для user/search, дублируем их до нужного количества
    if len(user_search_df) < max_records:
        print(f"Дублирование записей для user/search с {len(user_search_df)} до {max_records}...")
        # Рассчитываем, сколько раз нужно повторить данные
        repeat_times = max_records // len(user_search_df) + 1
        # Дублируем данные и берем первые max_records записей
        user_search_df = pd.concat([user_search_df] * repeat_times).reset_index(drop=True)
        user_search_df = user_search_df.iloc[:max_records]
    
    # Ограничиваем количество записей для user/get до max_records
    user_get_df = user_get_df.iloc[:max_records]
    
    # Выводим новое количество записей
    print(f"Новое количество записей для user/get: {len(user_get_df)}")
    print(f"Новое количество записей для user/search: {len(user_search_df)}")
    
    # Создаем графики
    create_latency_plot(user_get_df, user_search_df)
    create_throughput_plot(user_get_df, user_search_df)
    create_boxplot_comparison(user_get_df, user_search_df)
    create_combined_plot(user_get_df, user_search_df)
    
    print("Готово!")

if __name__ == "__main__":
    main()
