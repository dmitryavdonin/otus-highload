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

# Apply different smoothing methods
# 1. Simple Moving Average (SMA)
window_size = 20  # Adjust window size for desired smoothness
df_no_index['elapsed_sma'] = df_no_index['elapsed'].rolling(window=window_size, center=True).mean()
df_index['elapsed_sma'] = df_index['elapsed'].rolling(window=window_size, center=True).mean()

# 2. Exponential Moving Average (EMA)
span = 15  # Adjust span for desired smoothness
df_no_index['elapsed_ema'] = df_no_index['elapsed'].ewm(span=span, adjust=False).mean()
df_index['elapsed_ema'] = df_index['elapsed'].ewm(span=span, adjust=False).mean()

# 3. LOESS/LOWESS smoothing using numpy's polyfit (alternative to splines)
def lowess_smooth(x, y, f=0.1, iterations=3):
    """
    Basic LOWESS smoother with no scipy dependency
    - x, y: data points
    - f: smoothing span (between 0 and 1)
    - iterations: number of iterations
    """
    n = len(x)
    r = int(np.ceil(f * n))
    y_smooth = np.zeros(n)
    
    for i in range(n):
        weights = np.zeros(n)
        # Compute weights for each point based on distance
        for j in range(n):
            h = abs(x[i] - x[j])
            if h <= r:
                weights[j] = (1 - (h/r)**3)**3
            else:
                weights[j] = 0
                
        # Fit weighted linear regression
        w_sum = np.sum(weights)
        if w_sum != 0:
            x_weighted = np.sum(x * weights) / w_sum
            y_weighted = np.sum(y * weights) / w_sum
            
            # Simple weighted linear fit
            if np.sum(weights * (x - x_weighted)**2) != 0:
                b = np.sum(weights * (x - x_weighted) * (y - y_weighted)) / np.sum(weights * (x - x_weighted)**2)
                a = y_weighted - b * x_weighted
                y_smooth[i] = a + b * x[i]
            else:
                y_smooth[i] = y_weighted
        else:
            y_smooth[i] = y[i]
            
    return y_smooth

# Apply LOWESS smoothing
x_no_index = np.arange(len(df_no_index))
y_no_index = df_no_index['elapsed'].values
y_smooth_no_index = lowess_smooth(x_no_index, y_no_index, f=0.1)

x_index = np.arange(len(df_index))
y_index = df_index['elapsed'].values
y_smooth_index = lowess_smooth(x_index, y_index, f=0.1)

# Create plots with different smoothing methods
# 1. Original data (for reference)
plt.figure(figsize=(12, 6))
plt.plot(df_no_index['elapsed'], label='Без индекса', alpha=0.3)
plt.plot(df_index['elapsed'], label='С индексом', alpha=0.3)
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title('Исходные данные (без сглаживания)')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_original.png'))
plt.close()

# 2. Simple Moving Average (SMA)
plt.figure(figsize=(12, 6))
plt.plot(df_no_index['elapsed_sma'], label='Без индекса (SMA)', linewidth=2)
plt.plot(df_index['elapsed_sma'], label='С индексом (SMA)', linewidth=2)
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title(f'Сравнение времени ответа (скользящее среднее, окно={window_size})')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_sma.png'))
plt.close()

# 3. Exponential Moving Average (EMA)
plt.figure(figsize=(12, 6))
plt.plot(df_no_index['elapsed_ema'], label='Без индекса (EMA)', linewidth=2)
plt.plot(df_index['elapsed_ema'], label='С индексом (EMA)', linewidth=2)
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title(f'Сравнение времени ответа (экспоненциальное сглаживание, span={span})')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_ema.png'))
plt.close()

# 4. LOWESS smoothing
plt.figure(figsize=(12, 6))
plt.plot(x_no_index, y_smooth_no_index, label='Без индекса (LOWESS)', linewidth=2)
plt.plot(x_index, y_smooth_index, label='С индексом (LOWESS)', linewidth=2)
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title('Сравнение времени ответа (LOWESS сглаживание)')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_lowess.png'))
plt.close()

# 5. Combined visualization: original data with EMA overlay
plt.figure(figsize=(12, 6))
# Original data (transparent)
plt.plot(df_no_index['elapsed'], label='Без индекса (исходные)', alpha=0.2, color='blue')
plt.plot(df_index['elapsed'], label='С индексом (исходные)', alpha=0.2, color='orange')
# EMA overlay
plt.plot(df_no_index['elapsed_ema'], label='Без индекса (сглаженные)', linewidth=2, color='blue')
plt.plot(df_index['elapsed_ema'], label='С индексом (сглаженные)', linewidth=2, color='orange')
plt.xlabel('Запросы')
plt.ylabel('Время ответа (мс)')
plt.title('Сравнение времени ответа (исходные и сглаженные данные)')
plt.legend()
plt.savefig(os.path.join(script_dir, 'comparison_combined.png'))
plt.close()

# Create boxplot comparison with Matplotlib
plt.figure(figsize=(12, 6))
# Use the appropriate parameter name based on matplotlib version
if matplotlib_version >= (3, 9):
    plt.boxplot([df_no_index['elapsed'], df_index['elapsed']], 
               tick_labels=['Без индекса', 'С индексом'])
else:
    plt.boxplot([df_no_index['elapsed'], df_index['elapsed']], 
               labels=['Без индекса', 'С индексом'])
plt.ylabel('Время ответа (мс)')
plt.title('Статистическое сравнение времени ответа')
plt.savefig(os.path.join(script_dir, 'boxplot_comparison.png'))
plt.close()

print("Графики успешно сохранены:")
print(f"1. {os.path.join(script_dir, 'comparison_original.png')} - исходные данные")
print(f"2. {os.path.join(script_dir, 'comparison_sma.png')} - скользящее среднее")
print(f"3. {os.path.join(script_dir, 'comparison_ema.png')} - экспоненциальное сглаживание")
print(f"4. {os.path.join(script_dir, 'comparison_lowess.png')} - LOWESS сглаживание")
print(f"5. {os.path.join(script_dir, 'comparison_combined.png')} - комбинированный график")
print(f"6. {os.path.join(script_dir, 'boxplot_comparison.png')} - диаграмма размаха")
