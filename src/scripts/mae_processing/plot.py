import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_multi_distance_mae_vs_snr(parent_directory, output_image_path='multi_distance_mae_vs_snr.png'):
    parent_path = Path(parent_directory)
    
    # Recursively find all tracker_metrics.parquet files in the subdirectories
    metric_files = list(parent_path.rglob('tracker_metrics.parquet'))

    if not metric_files:
        print(f"No metric files found in {parent_directory}")
        return

    # Sort files by the distance number in the folder name (e.g., 45cm, 50cm, 60cm)
    def extract_dist(p):
        m = re.search(r'(\d+)', p.parent.name)
        return int(m.group(1)) if m else 0
        
    metric_files.sort(key=extract_dist)

    # Initialize the Plot
    plt.figure(figsize=(9, 6))

    # Generate a set of visually distinct colors for the different distances
    colors = plt.cm.tab10(np.linspace(0, 1, len(metric_files)))

    for idx, file_path in enumerate(metric_files):
        # The parent folder name (e.g., '60cm') will be used for the legend label
        distance_label = file_path.parent.name  
        print(f"Loading data for {distance_label}...")

        # Load and aggregate data
        df = pd.read_parquet(file_path)
        df['snr_bin'] = df['snr'].round(1)

        agg_df = df.groupby('snr_bin')['mae_euclidean'].agg(['mean', 'std']).reset_index()
        agg_df = agg_df.sort_values('snr_bin')

        snr_vals = agg_df['snr_bin']
        mean_error = agg_df['mean']
        std_error = agg_df['std'].fillna(0)

        color = colors[idx]

        # Plot the main line for this distance
        plt.plot(snr_vals, mean_error, marker='o', linewidth=2.5, markersize=5, 
                 label=f'Proposed Tracker ({distance_label})', color=color)

        # Add the shaded region for Standard Deviation
        plt.fill_between(snr_vals,
                         np.maximum(0, mean_error - std_error), # Prevent shading below 0 px
                         mean_error + std_error,
                         color=color, alpha=0.15)

    # Styling and Formatting
    plt.xlabel('Signal-to-Noise Ratio (SNR)', fontsize=12, fontweight='bold')
    plt.ylabel('Localization Error (px)', fontsize=12, fontweight='bold')
    
    plt.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.7, color='gray')
    plt.ylim(bottom=0) 
    
    # Legend
    plt.legend(loc='upper right', fontsize=10, framealpha=1.0, edgecolor='black')

    # Save
    plt.tight_layout()
    plt.savefig(output_image_path, dpi=300)
    print(f"\nPlot saved successfully to: {output_image_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot Tracker Accuracy vs SNR across multiple distances")
    parser.add_argument("baseline_folder", help="Path to the parent tracking_baseline folder")
    args = parser.parse_args()

    # Define output image dynamically based on where the script was run
    out_path = Path(args.baseline_folder) / 'aggregate_mae_vs_snr.png'
    
    plot_multi_distance_mae_vs_snr(args.baseline_folder, str(out_path))
