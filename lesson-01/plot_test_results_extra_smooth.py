import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np
import matplotlib

# Get matplotlib version to handle parameter naming correctly
matplotlib_version = tuple(map(int, matplotlib.__version__.split('.')[:2]))

# Get the absolute path to the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load data using absolute paths
df_no_index = pd.read_csv(os.path.join(script_dir, 'test_results', 'aggregate_report_no_index_10_users.csv'))
df_index = pd.read_csv(os.path.join(script_dir, 'test_results', 'aggregate_report_index_10_users.csv'))

# Apply different smoothing methods with stronger smoothing
# 1. Simple Moving Average (SMA) with larger window
window_size = 50  # Larger window for stronger smoothing
df_no_index['elapsed_sma'] = df_no_index['elapsed'].rolling(window=window_size, center=True).mean()
df_index['elapsed_sma'] = df_index['elapsed'].rolling(window=window_size, center=True).mean()

# 2. Exponential Moving Average (EMA) with larger span
span = 30  # Larger span for stronger smoothing
df_no_index['elapsed_ema'] = df_no_index['elapsed'].ewm(span=span, adjust=False).mean()
df_index['elapsed_ema'] = df_index['elapsed'].ewm(span=span, adjust=False).mean()

# 3. Double EMA for even smoother results
df_no_index['elapsed_double_ema'] = df_no_index['elapsed_ema'].ewm(span=span, adjust=False).mean()
df_index['elapsed_double_ema'] = df_index['elapsed_ema'].ewm(span=span, adjust=False).mean()

# Create plots with different smoothing methods
# 1. Simple Moving Average (SMA) with stronger smoothing
plt.figure(figsize=(12, 6))
plt.plot(df_no_index['elapsed_sma'], label='Без индекса (SMA)', linewidth=2)
plt.plot(df_index['elapsed_sma'], label='С индексом (SMA)', linewidth=2)
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title(f'Сравнение времени ответа (скользящее среднее, окно={window_size})')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_sma_extra_smooth.png'))
plt.close()

# 2. Exponential Moving Average (EMA) with stronger smoothing
plt.figure(figsize=(12, 6))
plt.plot(df_no_index['elapsed_ema'], label='Без индекса (EMA)', linewidth=2)
plt.plot(df_index['elapsed_ema'], label='С индексом (EMA)', linewidth=2)
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title(f'Сравнение времени ответа (экспоненциальное сглаживание, span={span})')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_ema_extra_smooth.png'))
plt.close()

# 3. Double Exponential Moving Average for extra smoothing
plt.figure(figsize=(12, 6))
plt.plot(df_no_index['elapsed_double_ema'], label='Без индекса (Double EMA)', linewidth=2)
plt.plot(df_index['elapsed_double_ema'], label='С индексом (Double EMA)', linewidth=2)
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title('Сравнение времени ответа (двойное экспоненциальное сглаживание)')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_double_ema.png'))
plt.close()

# 4. Combined visualization with original data and double EMA
plt.figure(figsize=(12, 6))
# Original data (very transparent)
plt.plot(df_no_index['elapsed'], label='Без индекса (исходные)', alpha=0.1, color='blue')
plt.plot(df_index['elapsed'], label='С индексом (исходные)', alpha=0.1, color='orange')
# Double EMA overlay
plt.plot(df_no_index['elapsed_double_ema'], label='Без индекса (сглаженные)', linewidth=2, color='blue')
plt.plot(df_index['elapsed_double_ema'], label='С индексом (сглаженные)', linewidth=2, color='orange')
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title('Сравнение времени ответа (исходные и сильно сглаженные данные)')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_combined_extra_smooth.png'))
plt.close()

print("Графики с дополнительным сглаживанием успешно сохранены:")
print(f"1. {os.path.join(script_dir, 'comparison_sma_extra_smooth.png')} - скользящее среднее (сильное сглаживание)")
print(f"2. {os.path.join(script_dir, 'comparison_ema_extra_smooth.png')} - экспоненциальное сглаживание (сильное сглаживание)")
print(f"3. {os.path.join(script_dir, 'comparison_double_ema.png')} - двойное экспоненциальное сглаживание")
print(f"4. {os.path.join(script_dir, 'comparison_combined_extra_smooth.png')} - комбинированный график (сильное сглаживание)")
