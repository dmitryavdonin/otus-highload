#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sys

# Set up the plotting style
sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 10})

# Moving average window size for smoothing
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
    Loads a CSV with raw timing data and computes throughput (req/sec).
    """
    df = pd.read_csv(file_path)
    
    # Convert timestamp to numeric, handling any non-numeric values
    df['timeStamp'] = pd.to_numeric(df['timeStamp'], errors='coerce')
    
    # Convert timestamp from milliseconds to seconds
    df['timestamp_sec'] = df['timeStamp'] / 1000.0
    
    # Calculate time differences between consecutive requests
    df['time_diff'] = df['timestamp_sec'].diff()
    
    # Calculate throughput (requests per second)
    df['throughput'] = 1 / df['time_diff']
    
    # Handle any infinite or NaN values
    df['throughput'] = df['throughput'].replace([np.inf, -np.inf], np.nan)
    df['throughput'] = df['throughput'].fillna(0)
    
    # Smooth throughput with moving average
    df['throughput_ma'] = df['throughput'].rolling(window=window, center=True).mean()
    df['throughput_ma'] = df['throughput_ma'].fillna(df['throughput'])
    
    return df

def create_comparison_latency_plot(endpoint):
    """
    Create a figure comparing latency for a specific endpoint with and without replication.
    
    Args:
        endpoint (str): Either 'get' or 'search' to specify which endpoint to plot
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Define file paths based on endpoint
    if endpoint == 'get':
        no_replica_path = os.path.join(script_dir, "test_results", "no_replica_user_get_results.jtl")
        with_replica_path = os.path.join(script_dir, "test_results", "with_replica_user_get_results.jtl")
        title = "User Get Endpoint - Latency Comparison"
    else:  # search
        no_replica_path = os.path.join(script_dir, "test_results", "no_replica_user_search_results.jtl")
        with_replica_path = os.path.join(script_dir, "test_results", "with_replica_user_search_results.jtl")
        title = "User Search Endpoint - Latency Comparison"
    
    # Process data
    df_no_replica = process_latency_data(no_replica_path)
    df_with_replica = process_latency_data(with_replica_path)
    
    # Trim 5% from the beginning and end to remove outliers
    trim_percent = 0.05
    
    # Trim no replica data
    start_idx_no = int(len(df_no_replica) * trim_percent)
    end_idx_no = int(len(df_no_replica) * (1 - trim_percent))
    df_no_replica_trimmed = df_no_replica.iloc[start_idx_no:end_idx_no]
    
    # Trim with replica data
    start_idx_with = int(len(df_with_replica) * trim_percent)
    end_idx_with = int(len(df_with_replica) * (1 - trim_percent))
    df_with_replica_trimmed = df_with_replica.iloc[start_idx_with:end_idx_with]
    
    # Plot the smoothed elapsed time (latency)
    ax.plot(range(len(df_no_replica_trimmed)), df_no_replica_trimmed['elapsed_ma'], 
            label="Without Replication", color="blue", linewidth=2)
    ax.plot(range(len(df_with_replica_trimmed)), df_with_replica_trimmed['elapsed_ma'], 
            label="With Replication", color="red", linewidth=2)
    
    ax.set_xlabel("Requests")
    ax.set_ylabel("Response Time (ms)")
    ax.set_title(title)
    
    # Add horizontal lines for average latency
    avg_latency_no = df_no_replica_trimmed['elapsed'].mean()
    avg_latency_with = df_with_replica_trimmed['elapsed'].mean()
    
    ax.axhline(y=avg_latency_no, color='blue', linestyle='--', 
               label=f'Avg Without Replication: {avg_latency_no:.2f} ms')
    ax.axhline(y=avg_latency_with, color='red', linestyle='--', 
               label=f'Avg With Replication: {avg_latency_with:.2f} ms')
    
    ax.legend()
    plt.tight_layout()
    
    # Save the figure
    out_path = os.path.join(script_dir, f"user_{endpoint}_latency_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Latency comparison for {endpoint} endpoint saved to: {out_path}")

def create_comparison_throughput_plot(endpoint):
    """
    Create a figure comparing throughput for a specific endpoint with and without replication.
    
    Args:
        endpoint (str): Either 'get' or 'search' to specify which endpoint to plot
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Define file paths based on endpoint
    if endpoint == 'get':
        no_replica_path = os.path.join(script_dir, "test_results", "no_replica_user_get_results.jtl")
        with_replica_path = os.path.join(script_dir, "test_results", "with_replica_user_get_results.jtl")
        title = "User Get Endpoint - Throughput Comparison"
    else:  # search
        no_replica_path = os.path.join(script_dir, "test_results", "no_replica_user_search_results.jtl")
        with_replica_path = os.path.join(script_dir, "test_results", "with_replica_user_search_results.jtl")
        title = "User Search Endpoint - Throughput Comparison"
    
    # Process data
    df_no_replica = process_throughput_data(no_replica_path)
    df_with_replica = process_throughput_data(with_replica_path)
    
    # Trim 5% from the beginning and end to remove outliers
    trim_percent = 0.05
    
    # Trim no replica data
    start_idx_no = int(len(df_no_replica) * trim_percent)
    end_idx_no = int(len(df_no_replica) * (1 - trim_percent))
    df_no_replica_trimmed = df_no_replica.iloc[start_idx_no:end_idx_no]
    
    # Trim with replica data
    start_idx_with = int(len(df_with_replica) * trim_percent)
    end_idx_with = int(len(df_with_replica) * (1 - trim_percent))
    df_with_replica_trimmed = df_with_replica.iloc[start_idx_with:end_idx_with]
    
    # Plot the smoothed throughput
    ax.plot(range(len(df_no_replica_trimmed)), df_no_replica_trimmed['throughput_ma'], 
            label="Without Replication", color="blue", linewidth=2)
    ax.plot(range(len(df_with_replica_trimmed)), df_with_replica_trimmed['throughput_ma'], 
            label="With Replication", color="red", linewidth=2)
    
    ax.set_xlabel("Requests")
    ax.set_ylabel("Requests per Second")
    ax.set_title(title)
    
    # Add horizontal lines for average throughput
    avg_throughput_no = df_no_replica_trimmed['throughput'].mean()
    avg_throughput_with = df_with_replica_trimmed['throughput'].mean()
    
    ax.axhline(y=avg_throughput_no, color='blue', linestyle='--', 
               label=f'Avg Without Replication: {avg_throughput_no:.2f} req/sec')
    ax.axhline(y=avg_throughput_with, color='red', linestyle='--', 
               label=f'Avg With Replication: {avg_throughput_with:.2f} req/sec')
    
    ax.legend()
    plt.tight_layout()
    
    # Save the figure
    out_path = os.path.join(script_dir, f"user_{endpoint}_throughput_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Throughput comparison for {endpoint} endpoint saved to: {out_path}")

def plot_results(results_file):
    # Чтение данных из файла результатов
    data = pd.read_csv(results_file)

    # Создание графиков
    plt.figure(figsize=(10, 5))
    
    # График времени отклика
    plt.plot(data['timeStamp'], data['elapsed'], label='Response Time (ms)')
    plt.xlabel('Timestamp')
    plt.ylabel('Elapsed Time (ms)')
    plt.title('Response Time Over Time')
    plt.legend()
    
    # Получение директории для сохранения графиков
    output_dir = os.path.dirname(results_file)
    output_file = os.path.join(output_dir, 'response_time_graph.png')
    
    # Сохранение графика
    plt.savefig(output_file)
    plt.close()

    print(f'График сохранен: {output_file}')

if __name__ == "__main__":
    if len(sys.argv) > 1:
        results_file = sys.argv[1]
        plot_results(results_file)
    else:
        print("Creating performance comparison plots...")
        
        # 1) Latency comparison for /user/get endpoint
        create_comparison_latency_plot('get')
        
        # 2) Throughput comparison for /user/get endpoint
        create_comparison_throughput_plot('get')
        
        # 3) Latency comparison for /user/search endpoint
        create_comparison_latency_plot('search')
        
        # 4) Throughput comparison for /user/search endpoint
        create_comparison_throughput_plot('search')
        
        print("All comparison plots created successfully!")
