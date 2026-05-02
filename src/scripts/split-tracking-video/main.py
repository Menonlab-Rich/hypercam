from argparse import ArgumentParser
from pathlib import Path

import cv2
import numpy as np
import yaml
from metavision_core.event_io import EventsIterator
from metavision_modules import RawCutter

# =====================================================================
# EVENT CAMERA HELPERS
# =====================================================================

def generate_histogram_for_window(input_file: Path, start_us: int, duration_us: int, sensor_size: tuple[int, int]) -> np.ndarray:
    start_us = max(0, start_us)
    
    # 1. Align to 10,000 for the SDK iterator to prevent I/O errors
    aligned_start = start_us - (start_us % 10000)
    
    # 2. Calculate the offset to extend the read duration
    offset_us = start_us - aligned_start
    total_duration = duration_us + offset_us
    
    iterator = EventsIterator(str(input_file), start_ts=aligned_start, max_duration=total_duration)
    frame = np.zeros((sensor_size[0], sensor_size[1]), dtype=np.uint8)
    
    for evts in iterator:
        # 3. Filter strictly for the exact microsecond bounds
        valid_mask = (evts['t'] >= start_us) & (evts['t'] < start_us + duration_us)
        valid_evts = evts[valid_mask]
        np.add.at(frame, (valid_evts['y'], valid_evts['x']), 1)
        
    return frame

def save_event_slice(input_file: Path, output_file: Path, start_us: int, end_us: int):
    cutter = RawCutter()
    cutter.set_output_file_path(str(output_file))
    cutter.cut_file(str(input_file), start_us, end_us)
    print(f"Saved {output_file.name} | Start: {start_us}us | End: {end_us}us")

# =====================================================================
# COMPUTER VISION DETECTION
# =====================================================================

def detect_circle(frame: np.ndarray, threshold: int = 25, min_circularity: float = 0.5, max_area: float = 5000) -> tuple[bool, np.ndarray | None]:
    """
    Evaluates the frame and returns (is_circle, contour_array).
    """
    frame = cv2.normalize(src=frame, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    kernel = np.ones((3,3),np.uint8)
    _, thresh = cv2.threshold(frame, threshold, 255, cv2.THRESH_BINARY)
    thresh = cv2.dilate(thresh, kernel, iterations=2)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return False, None

    for cnt in contours:
        area = cv2.contourArea(cnt)
        
        if 0 < area < max_area:
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
                
            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            if circularity >= min_circularity:
                return True, cnt
                
    return False, None

# =====================================================================
# CORE ALGORITHMS
# =====================================================================

def find_circle_start(input_file: Path, search_center_us: int, sensor_size: tuple[int, int], window_us: int = 1_000_000, resolution_us: int = 1000) -> int:
    """
    Left-bounding binary search with a raw-event microsecond resolver.
    """
    low = max(0, search_center_us - window_us // 2)
    high = search_center_us + window_us // 2
    
    integration_window_us = 20000 
    best_mid = high
    best_cnt = None

    # 1. Macro Search (Frame-based)
    while (high - low) > resolution_us:
        mid = (low + high) // 2
        frame = generate_histogram_for_window(input_file, mid, integration_window_us, sensor_size)
        is_circle, cnt = detect_circle(frame)
        
        if is_circle:
            best_mid = mid
            best_cnt = cnt
            high = mid
        else:
            low = mid

    # 2. Microsecond Resolver (Event-based)
    # The frame contains a valid circle. Let's find the absolute first microsecond 
    # an event hits the circle's bounding mask.
    if best_cnt is not None:
        mask = np.zeros((sensor_size[0], sensor_size[1]), dtype=np.uint8)
        cv2.drawContours(mask, [best_cnt], -1, 255, -1)
        
        aligned_start = best_mid - (best_mid % 10000)
        iterator = EventsIterator(str(input_file), start_ts=aligned_start, max_duration=integration_window_us + 10000)
        
        for evts in iterator:
            valid_mask = (evts['t'] >= best_mid) & (evts['t'] < best_mid + integration_window_us)
            valid_evts = evts[valid_mask]
            
            if len(valid_evts) > 0:
                in_mask = mask[valid_evts['y'], valid_evts['x']] == 255
                circle_evts = valid_evts[in_mask]
                
                if len(circle_evts) > 0:
                    return int(circle_evts['t'][0])

    return best_mid

def find_circle_end(input_file: Path, search_center_us: int, sensor_size: tuple[int, int], window_us: int = 1_000_000, resolution_us: int = 1000) -> int:
    """
    Right-bounding binary search with a raw-event microsecond resolver.
    """
    low = max(0, search_center_us - window_us // 2)
    high = search_center_us + window_us // 2
    
    integration_window_us = 20000
    best_mid = low
    best_cnt = None

    # 1. Macro Search (Frame-based)
    while (high - low) > resolution_us:
        mid = (low + high) // 2
        frame = generate_histogram_for_window(input_file, mid, integration_window_us, sensor_size)
        is_circle, cnt = detect_circle(frame)
        
        if is_circle:
            best_mid = mid
            best_cnt = cnt
            low = mid
        else:
            high = mid

    # 2. Microsecond Resolver (Event-based)
    # The frame is the right-most valid circle. Let's find the absolute last microsecond
    # an event hits the circle's bounding mask before it disappears.
    if best_cnt is not None:
        mask = np.zeros((sensor_size[0], sensor_size[1]), dtype=np.uint8)
        cv2.drawContours(mask, [best_cnt], -1, 255, -1)
        
        aligned_start = best_mid - (best_mid % 10000)
        iterator = EventsIterator(str(input_file), start_ts=aligned_start, max_duration=integration_window_us + 20000)
        
        last_t = best_mid
        for evts in iterator:
            valid_mask = (evts['t'] >= best_mid) & (evts['t'] < best_mid + integration_window_us + 10000)
            valid_evts = evts[valid_mask]
            
            if len(valid_evts) > 0:
                in_mask = mask[valid_evts['y'], valid_evts['x']] == 255
                circle_evts = valid_evts[in_mask]
                
                if len(circle_evts) > 0:
                    last_t = max(last_t, int(circle_evts['t'][-1]))
                    
        return last_t

    return best_mid

def process_recording(input_file: str, yaml_config: str, output_dir: str, text_start_us: int):
    fps = 30
    text_blink_us = 2_000_000

    input_path = Path(input_file)
    output_path = Path(output_dir)
    yaml_config_path = Path(yaml_config)

    if not input_path.exists() or input_path.suffix not in ['.dat', '.raw', '.hdf5']:
        raise ValueError("Input path must exist and be a .raw, .dat, or .hdf5 file")
    if not yaml_config_path.exists():
        raise ValueError("A valid tests.yaml file is required.")
        
    output_path.mkdir(parents=True, exist_ok=True)

    with open(yaml_config_path, "r") as f:
        config = yaml.safe_load(f)

    temp_iter = EventsIterator(str(input_path), max_duration=1)
    sensor_size = (temp_iter.get_size()[0], temp_iter.get_size()[1])
    del temp_iter

    current_text_start_us = text_start_us

    for test in config.get("tests", []):
        test_id = test["id"]
        duration_frames = test.get("duration_frames", 300)
        test_duration_us = int((duration_frames / fps) * 1_000_000)
        
        print(f"\n--- Processing Test ID: {test_id} ---")
        
        # 1. Step forward 2s from the text appearance and find the exact circle start
        expected_circle_start = current_text_start_us + text_blink_us
        print(f"Finding exact START near {expected_circle_start}us...")
        actual_circle_start = find_circle_start(input_path, expected_circle_start, sensor_size)
        
        # 2. Step forward by the test duration and find the exact circle end
        expected_circle_end = actual_circle_start + test_duration_us
        print(f"Finding exact END near {expected_circle_end}us...")
        actual_circle_end = find_circle_end(input_path, expected_circle_end, sensor_size)
        
        out_file_path = output_path / f"test_{test_id}_events.raw"
        save_event_slice(input_path, out_file_path, actual_circle_start, actual_circle_end)
        
        # 3. Anchor the next loop to the resolved end timestamp
        current_text_start_us = actual_circle_end

if __name__ == "__main__":
    parser = ArgumentParser(description="Extract individual tests based on circular tracking objects.")
    parser.add_argument("recording", type=str, help="The file to process (.raw, .dat, .hdf5).")
    parser.add_argument("--start", type=int, required=True, help="Exact microsecond timestamp where Test 1's text appears.")
    parser.add_argument("--config", type=str, default="tests.yaml", help="The path of the config file.")
    parser.add_argument("--out", type=str, default="./split_tests", help="The directory to save the split files.")

    args = parser.parse_args()
    process_recording(args.recording, args.config, args.out, args.start)
