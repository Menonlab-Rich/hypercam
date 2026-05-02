import numpy as np
import pandas as pd
from metavision_core.event_io import EventsIterator
from metavision_modules import event_cluster_tracker, stc_filter


# ==========================================
# 1. Iterative Tracking & SNR Processing
# ==========================================
def process_test_from_iterator(test_id, event_iterator, width=1280, height=720):
    """
    Processes a single test recording from an event iterator.
    Returns: (list_of_predictions, snr_value)
    """
    # Initialize Stateful Algorithms
    stc = stc_filter.SpatioTemporalContrastAlgorithm(width, height, 10000, True, False)
    stc_out_buf = stc_filter.SpatioTemporalContrastAlgorithm.get_empty_output_buffer()
    
    tracker = event_cluster_tracker.EventClusterTracker(width, height, 10000)
    
    total_events_count = 0
    signal_events_count = 0
    tracked_chunks = []
    track_ids = []
    for chunk_np in event_iterator:
        if len(chunk_np) == 0:
            continue
            
        # Accumulate SNR stats
        stc.process_events(chunk_np.copy(), stc_out_buf)
        signal_events_count += len(stc_out_buf.numpy())
        total_events_count += len(chunk_np)
        
        # Process Tracking
        output_events, track_ids_ = tracker.process_events(chunk_np)
        if len(output_events) > 0:
            tracked_chunks.append(np.copy(output_events))
            track_ids.append(track_ids_)

    # Finalize SNR
    noise_events_count = total_events_count - signal_events_count
    snr_value = signal_events_count / noise_events_count if noise_events_count > 0 else float('inf')
    
    # Finalize 120Hz Tracking Predictions
    predictions = []
    if tracked_chunks:
        all_tracked_events = np.concatenate(tracked_chunks)
        df_events = pd.DataFrame({
            'x': all_tracked_events['x'],
            'y': all_tracked_events['y'],
            't': all_tracked_events['t'],
            'cluster_id': np.concatenate(track_ids),
        })
        
        # Apply 120Hz binning (8333.33 us)
        dt_120hz_us = 1000000 / 120.0 
        df_events = df_events[df_events['cluster_id'] >= 0] 
        df_events['time_bin_idx'] = np.floor(df_events['t'] / dt_120hz_us).astype(int)
        
        for bin_idx, group in df_events.groupby('time_bin_idx'):
            timestamp_ms = (bin_idx * dt_120hz_us) / 1000.0
            target_cluster_id = group['cluster_id'].mode().iloc[0]
            target_events = group[group['cluster_id'] == target_cluster_id]
            
            predictions.append({
                'test_id': test_id, 
                'timestamp_ms': float(timestamp_ms),
                'pred_x': float(target_events['x'].mean()),
                'pred_y': float(target_events['y'].mean())
            })
            
    return predictions, snr_value

def build_predictions(iterator_mapping, output_preds_parquet, width=1280, height=720):
    """
    Executes the tracking loop over all tests and exports the predictions.
    """
    all_predictions = []
    snr_mapping = {}
    
    for test_id, event_iterator in iterator_mapping.items():
        print(f"Processing Test ID: {test_id} from iterator...")
        test_preds, test_snr = process_test_from_iterator(test_id, event_iterator, width, height)
        
        all_predictions.extend(test_preds)
        snr_mapping[test_id] = test_snr
        
    df_final_preds = pd.DataFrame(all_predictions)
    df_final_preds.to_parquet(output_preds_parquet, engine='pyarrow', index=False)
    print(f"Exported {len(df_final_preds)} prediction rows to {output_preds_parquet}")
    
    return df_final_preds, snr_mapping

# ==========================================
# 2. MAE Evaluation & Metrics Export
# ==========================================
def evaluate_and_export_metrics(gt_csv_path, df_predictions, snr_mapping, output_metrics_parquet):
    """
    Aligns GT with predictions, calculates MAE and Accuracy, and exports the final metrics.
    """
    
    print("\nStarting Evaluation...")
    df_gt = pd.read_csv(gt_csv_path).sort_values(['test_id', 'timestamp_ms'])
    
    # ---------------------------------------------------------
    # Spatial Scaling for Inverted Optics (180-degree rotation)
    # ---------------------------------------------------------
    screen_w, screen_h = 800, 600 
    
    # Coordinates of the Pygame window corners within the Metavision sensor FOV.
    # Note: These represent the physical sensor pixels that capture the 
    # TOP-LEFT and BOTTOM-RIGHT of the actual monitor.
    cam_tl_x, cam_tl_y = 120, 80   # Sensor pixel seeing monitor's Top-Left (actually at bottom-right of projection)
    cam_br_x, cam_br_y = 1100, 600 # Sensor pixel seeing monitor's Bottom-Right (actually at top-left of projection)
    
    # Absolute scale factors
    scale_x = abs(cam_br_x - cam_tl_x) / screen_w
    scale_y = abs(cam_br_y - cam_tl_y) / screen_h
    
    # Identify the maximum boundaries of the projection on the sensor
    max_cam_x = max(cam_tl_x, cam_br_x)
    max_cam_y = max(cam_tl_y, cam_br_y)

    # Apply dual-axis inversion anchored to the bounding box
    df_gt['cam_gt_x'] = max_cam_x - (df_gt['pos_x'] * scale_x)
    df_gt['cam_gt_y'] = max_cam_y - (df_gt['pos_y'] * scale_y)
    # ---------------------------------------------------------

    metrics = []
    
    for test_id, group in df_gt.groupby('test_id'):
        if test_id not in snr_mapping:
            continue
            
        group = group.set_index('timestamp_ms')
        pred_subset = df_predictions[df_predictions['test_id'] == test_id]
        
        if pred_subset.empty:
            continue
            
        target_times = pred_subset['timestamp_ms'].unique()
        df_target = pd.DataFrame(index=target_times)
        
        combined_index = group.index.union(df_target.index)
        df_combined = group.reindex(combined_index)
        df_combined['gt_x_linear'] = df_combined['cam_gt_x'].interpolate(method='index')
        df_combined['gt_y_linear'] = df_combined['cam_gt_y'].interpolate(method='index')
        
        df_aligned = df_combined.loc[df_target.index].reset_index()
        df_aligned = df_aligned.rename(columns={'index': 'timestamp_ms'})
        
        eval_df = pd.merge(pred_subset, df_aligned, on='timestamp_ms')
        
        # Calculate Errors
        mae_x = np.abs(eval_df['pred_x'] - eval_df['gt_x_linear']).mean()
        mae_y = np.abs(eval_df['pred_y'] - eval_df['gt_y_linear']).mean()
        mae_euclidean = np.sqrt((eval_df['pred_x'] - eval_df['gt_x_linear'])**2 + 
                                (eval_df['pred_y'] - eval_df['gt_y_linear'])**2).mean()
        
        acc_combined = 1 / (mae_euclidean + 1e-9)
        snr = snr_mapping[test_id]
        
        metrics.append({
            'test_id': int(test_id),
            'mae_x': float(mae_x),
            'mae_y': float(mae_y),
            'mae_euclidean': float(mae_euclidean),
            'accuracy_combined': float(acc_combined),
            'snr': float(snr)
        })
        
    df_results = pd.DataFrame(metrics)
    df_results.to_parquet(output_metrics_parquet, engine='pyarrow', index=False)
    print(f"Exported metrics to {output_metrics_parquet}")
    
    return df_results

# ==========================================
# 3. Master Execution Function
# ==========================================
def run_full_pipeline(iterator_mapping, gt_csv_path, output_preds_parquet, output_metrics_parquet):
    """
    Orchestrates the data extraction and evaluation pipelines.
    """
    # 1. Track, calculate SNR, and save predictions
    df_predictions, snr_mapping = build_predictions(
        iterator_mapping, 
        output_preds_parquet, 
        width=1280, 
        height=720
    )
    
    # 2. Evaluate and export metrics
    df_results = evaluate_and_export_metrics(
        gt_csv_path, 
        df_predictions, 
        snr_mapping,
        output_metrics_parquet
    )
    
    return df_results


if __name__ == "__main__":
    import argparse
    import re
    from pathlib import Path

    from metavision_core.event_io import EventsIterator 

    parser = argparse.ArgumentParser(description="Evaluate Event Tracker metrics")
    parser.add_argument("parent_folder", help="Path to the parent folder containing distance subfolders")
    args = parser.parse_args()

    parent_folder_path = Path(args.parent_folder)

    # Iterate through all subdirectories in the parent folder
    for test_folder_path in parent_folder_path.iterdir():
        if not test_folder_path.is_dir():
            continue
            
        print(f"\n======================================")
        print(f"Processing directory: {test_folder_path.name}")
        print(f"======================================")

        csv_files = list(test_folder_path.glob('*.csv'))
        if not csv_files:
            print(f"Skipping {test_folder_path.name}: No CSV file found.")
            continue
            
        gt_csv_path = str(csv_files[0]) 

        raw_files = list(test_folder_path.glob('*.raw'))
        if not raw_files:
            print(f"Skipping {test_folder_path.name}: No RAW files found.")
            continue

        iterators = {}
        fps_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
        for raw_path in raw_files:
            for fps in fps_values:
                numbers = re.findall(r'\d+', raw_path.stem)
                if numbers:
                    test_id = f"{numbers[-1]}-{fps}fps"
                    iterators[test_id] = EventsIterator(str(raw_path), delta_t = int(1/fps * 1e6))

        output_preds = str(test_folder_path / 'tracker_predictions.parquet')
        output_metrics = str(test_folder_path / 'tracker_metrics.parquet')

        # Execute the pipeline for this specific subfolder
        run_full_pipeline(
            iterator_mapping=iterators,
            gt_csv_path=gt_csv_path,
            output_preds_parquet=output_preds,
            output_metrics_parquet=output_metrics
        )
