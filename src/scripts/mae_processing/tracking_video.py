import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
# Metavision imports
from metavision_core.event_io import EventsIterator
from metavision_sdk_core import PeriodicFrameGenerationAlgorithm


def generate_tracking_video(raw_file, parquet_file, test_id, output_video, width=1280, height=720, fps=120.0):
    """
    Generates a video overlaying the tracked predictions on top of the event frames.
    """
    print(f"Loading predictions for Test ID {test_id}...")
    
    # 1. Load predictions and isolate the current test
    try:
        df = pd.read_parquet(parquet_file)
        df_test = df[df['test_id'] == test_id].copy()
        df_test = df_test.sort_values('timestamp_ms')
    except Exception as e:
        print(f"Error loading parquet file: {e}")
        return

    if df_test.empty:
        print(f"No predictions found for Test ID {test_id} in the parquet file.")
        return

    print(f"Opening RAW file: {raw_file}")
    mv_iterator = EventsIterator(raw_file)
    
    # 2. Setup Video Writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
    
    # Calculate accumulation time based on the desired FPS (in microseconds)
    accumulation_time_us = int(1000000 / fps)
    
    # 3. Setup the Frame Generator Algorithm
    frame_gen = PeriodicFrameGenerationAlgorithm(
        sensor_width=width, 
        sensor_height=height, 
        accumulation_time_us=accumulation_time_us, 
        fps=fps
    )

    # 4. Define the callback that gets triggered every time a frame is generated
    def frame_callback(ts, cd_frame):
        # The frame generated is usually in RGB. OpenCV uses BGR.
        if cd_frame.ndim == 3 and cd_frame.shape[2] == 3:
            frame_bgr = cv2.cvtColor(cd_frame, cv2.COLOR_RGB2BGR)
        else:
            # Fallback if it generates a grayscale frame
            frame_bgr = cv2.cvtColor(cd_frame, cv2.COLOR_GRAY2BGR)

        # Convert frame timestamp (us) to milliseconds to match our dataframe
        ts_ms = ts / 1000.0

        # Find the closest prediction in time
        idx = (np.abs(df_test['timestamp_ms'] - ts_ms)).argmin()
        pred = df_test.iloc[idx]

        # Only draw if the prediction is temporally close to this frame (e.g., within 15ms)
        if abs(pred['timestamp_ms'] - ts_ms) < 15.0:
            px, py = int(pred['pred_x']), int(pred['pred_y'])
            
            # The CSV says radius=20, so a 40x40 box is a good representation
            box_size = 40 
            top_left = (px - box_size // 2, py - box_size // 2)
            bottom_right = (px + box_size // 2, py + box_size // 2)

            # Draw the bounding box (Red)
            cv2.rectangle(frame_bgr, top_left, bottom_right, (0, 0, 255), 2)
            
            # Draw a center point
            cv2.circle(frame_bgr, (px, py), 2, (0, 255, 0), -1)

            # Optional: Add label text
            cv2.putText(frame_bgr, f"Track (ts:{pred['timestamp_ms']:.1f})", 
                        (top_left[0], top_left[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Write the frame to the video
        out.write(frame_bgr)

    # Attach the callback to the frame generator
    frame_gen.set_output_callback(frame_callback)

    print("Generating video... This may take a moment.")
    
    # 5. Process the events
    for chunk in mv_iterator:
        if len(chunk) > 0:
            frame_gen.process_events(chunk)

    # Release resources
    out.release()
    print(f"Video generation complete! Saved to {output_video}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tracking visualization video.")
    parser.add_argument("raw_file", help="Path to the .raw file")
    parser.add_argument("parquet_file", help="Path to the tracker_predictions.parquet file")
    parser.add_argument("test_id", type=int, help="The numeric ID of the test (to match in the parquet file)")
    parser.add_argument("--output", default="tracking_output.mp4", help="Name of the output mp4 file")
    
    args = parser.parse_args()

    # Make sure to set your camera's actual resolution here if it's not 1280x720
    generate_tracking_video(
        raw_file=args.raw_file, 
        parquet_file=args.parquet_file, 
        test_id=args.test_id, 
        output_video=args.output,
        width=1280, 
        height=720,
        fps=120.0
    )
