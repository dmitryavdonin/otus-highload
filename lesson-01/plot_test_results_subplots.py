#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 10})

# Use a moving average window of 50 (as requested)
WINDOW_SIZE = 50

# Get the absolute path of this script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

def process_latency_data(file_path, window=WINDOW_SIZE):
    """
    Loads a CSV file with latency data and computes the smoothed 'elapsed' using
    a simple moving average.
    """
    df = pd.read_csv(file_path)
    df['elapsed_ma'] = df['elapsed'].rolling(window=window, center=True).mean()
    # Replace NaNs (e.g. at beginning/end) with the original values
    df['elapsed_ma'] = df['elapsed_ma'].fillna(df['elapsed'])
    return df

def process_throughput_data(file_path, window=WINDOW_SIZE):
    """
    Loads a CSV with raw timing data, computes throughput (req/sec) from timeStamp (in ms)
    and applies a moving average to smooth the results.
    """
    df = pd.read_csv(file_path)
    # Convert timestamp to datetime (assume milliseconds)
    df['datetime'] = pd.to_datetime(df['timeStamp'], unit='ms')
    df = df.sort_values('datetime')
    # Compute time difference (in seconds) between consecutive requests
    df['time_diff'] = df['datetime'].diff().dt.total_seconds()
    # Avoid division by zero (for the first row)
    df['time_diff'] = df['time_diff'].replace({0: np.nan})
    df['time_diff'] = df['time_diff'].bfill()
    # Throughput = 1 / (time difference). Where diff is still NaN, set throughput to 0.
    df['throughput'] = 1 / df['time_diff']
    df['throughput'] = df['throughput'].fillna(0)
    # Smooth throughput with moving average
    df['throughput_ma'] = df['throughput'].rolling(window=window, center=True).mean()
    df['throughput_ma'] = df['throughput_ma'].fillna(df['throughput'])
    return df

def create_latency_subplots():
    """
    Create a figure with 3 subplots (for 1, 10, and 100 users) showing the smoothed latency.
    """
    fig, axes = plt.subplots(3, 1, figsize=(12, 15))
    # List of user counts to process
    for i, user_count in enumerate([1, 10, 100]):
        # Determine filename suffix (singular if one user, plural otherwise)
        suffix = "user" if user_count == 1 else "users"
        # Build paths for no index and with index data
        no_index_path = os.path.join(script_dir, "test_results", "no_index", 
                          f"response_time_graph_{user_count}_{suffix}_no_index.csv")
        with_index_path = os.path.join(script_dir, "test_results", "with_index", 
                          f"response_time_graph_{user_count}_{suffix}_with_index.csv")
        # Load and process the data
        df_no = process_latency_data(no_index_path)
        df_with = process_latency_data(with_index_path)
        
        # For 100 users, make sure we use the same number of data points
        if user_count == 100:
            # Get the minimum length of both datasets
            min_length = min(len(df_no), len(df_with))
            # Truncate both datasets to this length
            df_no = df_no.iloc[:min_length]
            df_with = df_with.iloc[:min_length]
        
        # Trim 5% from the beginning and 5% from the end to remove outliers
        trim_percent = 0.05
        start_idx = int(len(df_no) * trim_percent)
        end_idx = int(len(df_no) * (1 - trim_percent))
        df_no_trimmed = df_no.iloc[start_idx:end_idx]
        
        start_idx = int(len(df_with) * trim_percent)
        end_idx = int(len(df_with) * (1 - trim_percent))
        df_with_trimmed = df_with.iloc[start_idx:end_idx]
        
        # Plot the smoothed elapsed time (latency)
        axes[i].plot(range(len(df_no_trimmed)), df_no_trimmed['elapsed_ma'], label="Без индекса", color="blue", linewidth=2)
        axes[i].plot(range(len(df_with_trimmed)), df_with_trimmed['elapsed_ma'], label="С индексом", color="orange", linewidth=2)
        axes[i].set_xlabel("Запросы")
        axes[i].set_ylabel("Время ответа (мс)")
        axes[i].set_title(f"Latency – {user_count} {'пользователей' if user_count > 1 else 'пользователь'}")
        axes[i].legend()
    plt.tight_layout()
    out_path = os.path.join(script_dir, "latency_comparison_subplots.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Latency figure saved to: {out_path}")

def create_throughput_subplots():
    """
    Create a figure with 3 subplots (for 1, 10, and 100 users) showing the smoothed throughput.
    """
    fig, axes = plt.subplots(3, 1, figsize=(12, 15))
    for i, user_count in enumerate([1, 10, 100]):
        suffix = "user" if user_count == 1 else "users"
        no_index_path = os.path.join(script_dir, "test_results", "no_index", 
                          f"throughput_{user_count}_{suffix}_no_index.csv")
        with_index_path = os.path.join(script_dir, "test_results", "with_index", 
                          f"throughput_{user_count}_{suffix}_with_index.csv")
        df_no = process_throughput_data(no_index_path)
        df_with = process_throughput_data(with_index_path)
        
        # For 100 users, make sure we use the same number of data points
        if user_count == 100:
            # Get the minimum length of both datasets
            min_length = min(len(df_no), len(df_with))
            # Truncate both datasets to this length
            df_no = df_no.iloc[:min_length]
            df_with = df_with.iloc[:min_length]
        
        # Trim 5% from the beginning and 5% from the end to remove outliers
        trim_percent = 0.05
        start_idx = int(len(df_no) * trim_percent)
        end_idx = int(len(df_no) * (1 - trim_percent))
        df_no_trimmed = df_no.iloc[start_idx:end_idx]
        
        start_idx = int(len(df_with) * trim_percent)
        end_idx = int(len(df_with) * (1 - trim_percent))
        df_with_trimmed = df_with.iloc[start_idx:end_idx]
        
        axes[i].plot(range(len(df_no_trimmed)), df_no_trimmed['throughput_ma'], label="Без индекса", color="blue", linewidth=2)
        axes[i].plot(range(len(df_with_trimmed)), df_with_trimmed['throughput_ma'], label="С индексом", color="orange", linewidth=2)
        axes[i].set_xlabel("Запросы")
        axes[i].set_ylabel("Запросов в секунду")
        axes[i].set_title(f"Throughput – {user_count} {'пользователей' if user_count > 1 else 'пользователь'}")
        axes[i].legend()
    plt.tight_layout()
    out_path = os.path.join(script_dir, "throughput_comparison_subplots.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Throughput figure saved to: {out_path}")

if __name__ == "__main__":
    print("Создание диаграмм сравнения производительности (latency и throughput)...")
    create_latency_subplots()
    create_throughput_subplots()
    print("Готово!")
