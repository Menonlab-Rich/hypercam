from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
from metavision_core.event_io import EventsIterator
from metavision_modules import stc_filter


def calculate_snr(raw_file_path):
    """
    Calculates SNR by passing raw events through the STC filter.
    Signal = events passing STC filter.
    Noise = total events - Signal.
    """
    mv_iterator = EventsIterator(input_path=str(raw_file_path), delta_t=10000)
    height, width = mv_iterator.get_size()
    
    # Initializes STC filter with parameters matching event-tracking/main.py
    stc = stc_filter.SpatioTemporalContrastAlgorithm(width, height, 100000, False, False)
    
    total_events = 0
    signal_events = 0
    
    for evts in mv_iterator:
        total_events += len(evts)
        filtered_buffer = stc.get_empty_output_buffer()
        stc.process_events(evts, filtered_buffer)
        signal_events += len(filtered_buffer.numpy())
        
    noise_events = total_events - signal_events
    if noise_events == 0:
        return float('inf')
        
    return signal_events / noise_events

def calculate_mae(csv_file, parquet_file, test_id, dt_us=10000):
    """
    Calculates the Mean Absolute Error between ground truth and tracker output.
    Uses nearest timestamp matching.
    """
    # Load ground truth and isolate requested test case
    gt_df = pd.read_csv(csv_file)
    gt_df = gt_df[gt_df['test_id'] == test_id].copy()
    gt_df['t_us'] = (gt_df['timestamp_ms'] * 1000).astype(float)
    gt_df = gt_df.sort_values('t_us')
    
    # Load tracked events
    try:
        track_df = pl.read_parquet(parquet_file).to_pandas()
    except Exception as e:
        print(f"Error loading {parquet_file}: {e}")
        return None

    if track_df.empty:
        return None

    # Calculate spatial centroid of the grouped events for the given accumulation time
    track_df['t_bin'] = ( (track_df['t'] // dt_us) * dt_us ).astype(float)
    centroids = track_df.groupby('t_bin')[['x', 'y']].mean().reset_index().astype(float)
    centroids = centroids.sort_values('t_bin')
    
    # Align ground truth continuous time to discrete tracking bins
    merged = pd.merge_asof(
        gt_df, 
        centroids, 
        left_on='t_us', 
        right_on='t_bin', 
        direction='nearest', 
        tolerance=dt_us * 1.5
    )
    merged = merged.dropna(subset=['x', 'y'])
    
    if len(merged) == 0:
        print(f"No overlapping timestamps found for test {test_id}.")
        return None
        
    # MAE derived via mean Euclidean distance
    mae = np.sqrt((merged['pos_x'] - merged['x'])**2 + (merged['pos_y'] - merged['y'])**2).mean()
    return mae

def main():
    csv_file = "../object-tracking-test/tracking_log.csv"
    
    test_mapping = [
        {"test_id": 5, "raw_path": "../../../data/raw/tracking_tests/recording_2026-03-30_13-18-37_test_5.raw", "parquet_path": "../event-tracking/output/8335/recording_2026-03-30_13-18-37_test_5-tracked.parquet"},
        {"test_id": 6, "raw_path": "../../../data/raw/tracking_tests/recording_2026-03-30_13-19-15_test_6.raw", "parquet_path": "../event-tracking/output/8335/recording_2026-03-30_13-19-15_test_6-tracked.parquet"},
        {"test_id": 7, "raw_path": "../../../data/raw/tracking_tests/recording_2026-03-30_13-26-25_test_7.raw", "parquet_path": "../event-tracking/output/8335/recording_2026-03-30_13-26-25_test_7-tracked.parquet"},
        {"test_id": 8, "raw_path": "../../../data/raw/tracking_tests/recording_2026-03-30_13-27-45_test_8.raw", "parquet_path": "../event-tracking/output/8335/recording_2026-03-30_13-27-45_test_8-tracked.parquet"},
        {"test_id": 9, "raw_path": "../../../data/raw/tracking_tests/recording_2026-03-30_13-40-06_test_9.raw", "parquet_path": "../event-tracking/output/8335/recording_2026-03-30_13-40-06_test_9-tracked.parquet"}
    ]
    
    results = []
    
    for case in test_mapping:
        raw_path = Path(case["raw_path"])
        parquet_path = Path(case["parquet_path"])
        test_id = case["test_id"]
        
        if not raw_path.exists() or not parquet_path.exists():
            print(f"Skipping Test {test_id} - Required data files not found.")
            continue
            
        print(f"Evaluating Test {test_id}...")
        snr = calculate_snr(raw_path)
        mae = calculate_mae(csv_file, parquet_path, test_id)
        
        if mae is not None:
            results.append((snr, mae, test_id))
            print(f"  SNR: {snr:.4f} | MAE: {mae:.2f} pixels")
            
    if len(results) < 2:
        print("\nInsufficient data points to generate a curve.")
        return
        
    # Order points by ascending SNR
    results.sort(key=lambda x: x[0])
    snrs = [r[0] for r in results]
    maes = [r[1] for r in results]
    labels = [f"Test {r[2]}" for r in results]

    # Plot Configuration
    plt.figure(figsize=(9, 6))
    plt.plot(snrs, maes, marker='o', linestyle='-', color='indigo', linewidth=2)
    
    for i, label in enumerate(labels):
        plt.annotate(
            label, 
            (snrs[i], maes[i]), 
            textcoords="offset points", 
            xytext=(0,10), 
            ha='center'
        )

    plt.xlabel("Signal-to-Noise Ratio (SNR)")
    plt.ylabel("Mean Absolute Error (Pixels)")
    plt.title("Tracker MAE vs. SNR Across Event Densities")
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
