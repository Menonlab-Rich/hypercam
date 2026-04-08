import argparse
import itertools
import json
import logging
import queue
import sys
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from glob import glob
from numbers import Number
from pathlib import Path
from typing import Optional, Tuple

import cv2
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
import polars as pl
from filterpy.common import Q_discrete_white_noise
from filterpy.kalman import KalmanFilter
from metavision_core.event_io import EventsIterator
from metavision_hal import DeviceDiscovery, RawFileConfig
from metavision_modules import stc_filter
from metavision_sdk_core import (PeriodicFrameGenerationAlgorithm,
                                 PolarityFilterAlgorithm, RoiFilterAlgorithm)
from scipy.spatial import KDTree
from sklearn.cluster import DBSCAN, KMeans

optuna.logging.set_verbosity(optuna.logging.INFO)


@dataclass
class Crop:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0


@dataclass
class File:
    path: Path
    crop: Optional[Crop] = None
    start: Optional[Number] = None
    duration: Optional[Number] = None
    dest: Path = Path('./')

    def __post_init__(self):
        if self.start is not None: self.start = int(self.start)
        if self.duration is not None: self.duration = int(self.duration)


@dataclass
class Track:
    track_id: int
    kf: KalmanFilter
    age: int = 1
    hits: int = 1
    invisible_count: int = 0
    confirmed = False


class FilterPipeline:
    def __init__(self, *filters):
        self.pipeline = list(filters)

    def push(self, filter):
        self.pipeline.append(filter)

    def process_events(self, events):
        buffers = [events]
        for filter in self.pipeline:
            buffer = filter.get_empty_output_buffer()
            filter.process_events(buffers[-1], buffer)
            buffers.append(buffer)
        return buffers[-1].numpy(copy=True)


class EventBatchGenerator:
    def __init__(self, file_path, dt, start_time=0, duration=None, crop: Optional[Crop] = None, filter_polarity=None):
        self.file_path = str(file_path)
        self.dt = dt
        config = RawFileConfig()
        device = DeviceDiscovery.open_raw_file(str(file_path), config)
        
        self.target_start_time = int(start_time) if start_time else 0
        self.target_end_time = (self.target_start_time + int(duration)) if duration else None
        self.evts_iter = EventsIterator.from_device(device=device, start_ts=self.target_start_time, max_duration=duration, delta_t=self.dt)
        self.height, self.width = self.evts_iter.get_size()
        self.stc_filter = stc_filter.SpatioTemporalContrastAlgorithm(self.width, self.height, 100000, False, False)
        
        self.filters = FilterPipeline()
        if crop is not None:
            self.filters.push(RoiFilterAlgorithm(x0=crop.x0, x1=crop.x1, y0=crop.y0, y1=crop.y1))
        self.filters.push(self.stc_filter)
        self.polarity_bias_threshold = 0.9
        self.global_flash_threshold = (self.height * self.width) * 0.005

        self.keep_off_filter = PolarityFilterAlgorithm(polarity=0)
        self.keep_on_filter = PolarityFilterAlgorithm(polarity=1)

        if filter_polarity == 1:
            self.filters.push(self.keep_off_filter)
        elif filter_polarity == 0:
            self.filters.push(self.keep_on_filter)

    def get_external_events(self):
        return self.evts_iter.get_ext_trigger_events()

    def _veto(self, events):
        return False, -1

    def __iter__(self):
        for idx, evts in enumerate(self.evts_iter):
            if len(evts) == 0:
                continue
            activity_np = self.filters.process_events(evts)
            yield idx, activity_np


class PoseEstimator:
    def __init__(self, max_k=6, sigma_threshold=3.0, smoothing_alpha=0.3):
        self.max_k = max_k
        self.sigma_threshold = sigma_threshold
        self.alpha = smoothing_alpha
        self.prev_centers = None
        self.initialized = False

    def update(self, tracker, timestamp):
        raw_points = [
            np.round(t.kf.x[:2]).astype(float) 
            for t in tracker.tracks.values() 
            if t.confirmed
        ]

        if len(raw_points) == 0:
            return []

        points_arr = np.array(raw_points)

        if len(points_arr) > 2:
            mean = np.mean(points_arr, axis=0)
            centered = points_arr - mean
            cov = np.cov(centered.T)
            evals, evecs = np.linalg.eig(cov)

            idx = np.argsort(evals)[::-1]
            minor_std = np.sqrt(evals[idx[1]])
            minor_axis = evecs[:, idx[1]]

            perp_distances = np.abs(np.dot(centered, minor_axis))
            threshold = (self.sigma_threshold * minor_std) + 2.0

            mask = perp_distances < threshold
            clean_points = points_arr[mask]
        else:
            clean_points = points_arr

        n_tracks = len(clean_points)
        if n_tracks == 0: return []

        k = min(self.max_k, n_tracks)
        can_warm_start = (self.initialized and 
                          self.prev_centers is not None and 
                          len(self.prev_centers) == k)

        if can_warm_start:
            km = KMeans(n_clusters=k, init=self.prev_centers, n_init=1, random_state=42)
            km.fit(clean_points)
            new_centers = km.cluster_centers_
        else:
            km = KMeans(n_clusters=k, random_state=42)
            km.fit(clean_points)
            centers = km.cluster_centers_

            if len(centers) > 1:
                c_mean = np.mean(centers, axis=0)
                c_centered = centers - c_mean
                c_evals, c_evecs = np.linalg.eig(np.cov(c_centered.T))
                p_axis = c_evecs[:, np.argmax(c_evals)]

                if p_axis[1] < 0: p_axis = -p_axis
                projections = np.dot(c_centered, p_axis)
                new_centers = centers[np.argsort(projections)]
            else:
                new_centers = centers
            self.initialized = True

        if self.prev_centers is not None and len(self.prev_centers) == len(new_centers):
            smoothed_centers = (self.alpha * new_centers) + ((1 - self.alpha) * self.prev_centers)
        else:
            smoothed_centers = new_centers

        self.prev_centers = smoothed_centers

        pose_points = []
        for i, center in enumerate(smoothed_centers):
            pose_points.append({
                "t": timestamp,
                "pose_id": i,
                "x": center[0],
                "y": center[1]
            })

        return pose_points


class TunableTracker:
    def __init__(self, dist_thresh, max_age, min_hits, R_var, Q_var, omega, shape):
        self.dist_thresh = dist_thresh
        self.max_age_time = max_age / 1000.0 
        self.min_hits = min_hits
        self.R_var = R_var
        self.Q_var = Q_var
        self.Q_var_scalar = 10e3
        self.tracks = {}
        self.next_id = 0
        self.shape = shape
        self.n_init = 3
        self.omega = omega
        self.cold_tracks = []

    def _create_kalman_filter(self, measurement, dt, velocity=(0.0, 0.0)):
        kf = KalmanFilter(dim_x=4, dim_z=2)
        kf.x = np.array([measurement[0], measurement[1], velocity[0], velocity[1]])
        kf.P = np.diag([100., 100., 1e3, 1e3]) 
        w = self.omega
        if abs(w) > 1e-5:
            sin_wdt = np.sin(w * dt)
            cos_wdt = np.cos(w * dt)
            ctr_F = np.array([
                [1, 0, sin_wdt / w, -(1 - cos_wdt) / w],
                [0, 1, (1 - cos_wdt) / w, sin_wdt / w],
                [0, 0, cos_wdt, -sin_wdt],
                [0, 0, sin_wdt, cos_wdt]
            ])
        else:
            ctr_F = np.array([
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ])

        kf.F = ctr_F
        kf.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
        kf.R = np.eye(2) * self.R_var       
        kf.Q = Q_discrete_white_noise(dim=4, dt=dt, var=self.Q_var * self.Q_var_scalar)
        return kf

    def update(self, detections, dt):     
        frame_Q = Q_discrete_white_noise(dim=4, dt=dt, var=self.Q_var * self.Q_var_scalar)
        assignments = np.full(len(detections), -1, dtype=np.int64)

        predicted_positions = []
        track_ids = []
        
        # Calculate dynamic CTR F matrix for current timestep
        w = self.omega
        if abs(w) > 1e-5:
            sin_wdt = np.sin(w * dt)
            cos_wdt = np.cos(w * dt)
            ctr_F = np.array([
                [1, 0, sin_wdt / w, -(1 - cos_wdt) / w],
                [0, 1, (1 - cos_wdt) / w, sin_wdt / w],
                [0, 0, cos_wdt, -sin_wdt],
                [0, 0, sin_wdt, cos_wdt]
            ])
        else:
            ctr_F = np.array([
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ])

        # Predict phase
        for tid, track in self.tracks.items():
            track.kf.F = ctr_F
            track.kf.Q = frame_Q 
            track.kf.predict()
            predicted_positions.append(track.kf.x[:2])
            track_ids.append(tid)
            
        predicted_positions = np.array(predicted_positions)
        matched_groups = {tid: [] for tid in track_ids}
        matched_det_indices = set()
        active_track_ids = set() 

        # Match phase
        if len(predicted_positions) > 0 and len(detections) > 0:
            tree = KDTree(predicted_positions)
            dist, indices = tree.query(detections)
            if np.isscalar(dist): dist, indices = [dist], [indices]

            for det_idx, (d, trk_idx) in enumerate(zip(dist, indices)):
                if d < self.dist_thresh:
                    tid = track_ids[trk_idx]
                    matched_groups[tid].append(detections[det_idx])
                    matched_det_indices.add(det_idx)
                    active_track_ids.add(tid)
                    assignments[det_idx] = tid

        # Update phase
        for tid, points in matched_groups.items():
            if len(points) == 0: continue
            points_arr = np.array(points)
            centroid = np.mean(points_arr, axis=0)
            track = self.tracks[tid]
            track.kf.update(centroid)
            track.hits += 1 
            track.invisible_count = 0.0

        # Spawn Phase: Two-Point Initialization
        unmatched_dets = []
        for i, det in enumerate(detections):
            if i not in matched_det_indices:
                unmatched_dets.append((i, det))

        new_tracks = []
        for i, det in unmatched_dets:
            spawned = False
            if self.cold_tracks:
                track_positions = np.array(self.cold_tracks)
                tree = KDTree(track_positions)
                
                # Use a wider radius just for the initial jump matching
                dist, idx = tree.query(det, distance_upper_bound=self.dist_thresh * 3.0)
                
                if dist != float('inf'):
                    prev_det = self.cold_tracks[idx]
                    
                    vx = (det[0] - prev_det[0]) / dt
                    vy = (det[1] - prev_det[1]) / dt
                    
                    kf = self._create_kalman_filter(det, dt, velocity=(vx, vy))
                    track = Track(track_id=self.next_id, kf=kf)
                    track.hits = 2 # Starts with 2 hits representing the two points
                    
                    self.tracks[self.next_id] = track
                    active_track_ids.add(self.next_id)
                    assignments[i] = self.next_id
                    self.next_id += 1
                    spawned = True
                    
                    self.cold_tracks.pop(idx)
            
            if not spawned:
                new_tracks.append(det)

        self.cold_tracks = new_tracks

        # Cleanup phase
        height, width = self.shape
        dead_tracks = []

        for tid, t in self.tracks.items():
            x, y = t.kf.x[:2]

            if tid not in active_track_ids:
                t.invisible_count += dt

            is_tentative = t.hits < self.n_init
            is_lost = t.invisible_count > 0

            if is_tentative and is_lost:
                 dead_tracks.append(tid)
                 continue

            if not t.confirmed and t.hits >= self.n_init:
                t.confirmed = True

            if x < 0 or x > width or y < 0 or y > height:
                dead_tracks.append(tid)
                continue

            if t.invisible_count > self.max_age_time:
                dead_tracks.append(tid)

        for tid in set(dead_tracks):
            del self.tracks[tid]

        return assignments

@dataclass
class Video:
    codec: int
    output_path: Path
    dimensions: Tuple[int, int]
    mkdir: bool = True
    fps: int = 30
    delay_init: bool = False
    threaded: bool = field(default=False, repr=False)

    _writer: Optional[cv2.VideoWriter] = field(init=False, repr=False, default=None)
    _queue: Optional[queue.Queue] = field(init=False, repr=False, default=None)
    _thread: Optional[threading.Thread] = field(init=False, repr=False, default=None)
    _stopped: bool = field(init=False, repr=False, default=False)

    def __post_init__(self):
        if self.mkdir:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.delay_init:
            self.init_writer()
        if self.threaded:
            self._start_worker()

    def _start_worker(self):
        self._queue = queue.Queue(maxsize=256)
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()

    def __enter__(self):
        if self._writer is None and not self.delay_init:
            self.init_writer()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def _process_queue(self):
        while True:
            frame = self._queue.get()
            if frame is None:
                break
            self._writer.write(frame)
            self._queue.task_done()

    def write(self, frame: np.ndarray):
        if self.threaded:
            if not self._stopped:
                self._queue.put(frame.copy())
        else:
            self._writer.write(frame)

    def init_writer(self):
        if self._writer is None:
            self._writer = cv2.VideoWriter(
                str(self.output_path),
                fourcc=self.codec,
                fps=self.fps,
                frameSize=self.dimensions
            )

    def release(self):
        if self.threaded and self._thread and self._thread.is_alive():
            self._stopped = True
            self._queue.put(None)
            self._thread.join()

        if self._writer:
            self._writer.release()
            self._writer = None

    @property
    def width(self) -> int: return self.dimensions[0]

    @property
    def height(self) -> int: return self.dimensions[1]


class ColorGenerator:
    def __init__(self):
        self.mapping = {}
        self.cmap = plt.get_cmap('tab10')
        self.norm = mcolors.Normalize(vmin=0, vmax=10)

    def get_color(self, track_id):
        if track_id not in self.mapping:
            seed = hash(track_id) % 10
            rgba = self.cmap(self.norm(seed))
            bgr = (int(rgba[2]*255), int(rgba[1]*255), int(rgba[0]*255))
            self.mapping[track_id] = bgr
        return self.mapping[track_id]


def process_and_save(file_info: File, args, outvid: Optional[Video] = None):
    print(f"Processing {file_info.path.name}...")
    gen_video = outvid is not None

    evt_gen = EventBatchGenerator(
        file_path=file_info.path, 
        dt=args.dt, 
        start_time=0,
        crop=file_info.crop,
        filter_polarity=args.filter_polarity
    )

    tracker = TunableTracker(
        dist_thresh=args.dist_thresh,
        max_age=args.max_age,
        min_hits=args.min_hits,
        R_var=args.r_var,
        Q_var=args.q_var,
        omega=args.omega,
        shape=(evt_gen.height, evt_gen.width)
    )

    pose_estimator = None
    if args.pose:
        pose_estimator = PoseEstimator(
            max_k=args.max_k,
            sigma_threshold=args.sigma_threshold,
            smoothing_alpha=args.smoothing_alpha
        )

    if gen_video:
        frame_gen = PeriodicFrameGenerationAlgorithm(evt_gen.width, evt_gen.height, accumulation_time_us=args.dt, fps=1/(args.dt * 1e-6))
        outvid.dimensions = (evt_gen.width, evt_gen.height)
        outvid.init_writer()
        color_gen = ColorGenerator()

    data_frames = []
    latest_pose_points = [] 
    all_pose_samples = [] 

    def frame_gen_cb(ts, frame):
        frame_copy = frame.copy()
        cv2.putText(frame_copy, f'{ts / 1000} ms', (evt_gen.width - 150, 25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255))
        
        if args.pose:
            for pt in latest_pose_points:
                x, y = int(pt['x']), int(pt['y'])
                c = (0, 255, 0)
                cv2.circle(frame_copy, (x, y), 5, c, -1)
                
        for tid, t in tracker.tracks.items():
            if not t.confirmed and not args.plot_all_tracks:
                continue
                
            x, y = np.round(t.kf.x[:2]).astype(int)
            c = color_gen.get_color(tid)
            cv2.circle(frame_copy, (x, y), 3, c, -1)       
            cv2.putText(
                frame_copy, 
                f"ID: {tid}", 
                (x + 10, y), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, c, 1, cv2.LINE_AA
            )

        outvid.write(frame_copy)

    if gen_video:
        frame_gen.set_output_callback(frame_gen_cb)

    last_time = None
    current_time = 0
    for item in evt_gen:
        if item is None:
            empty_coords = np.empty((0, 2), dtype=np.float32)
            tracker.update(empty_coords, args.dt / 1e6)
            continue
            
        _, evts = item
        if len(evts) == 0: continue

        coords = np.stack((evts['x'], evts['y']), axis=1).astype(np.float32)
        current_time = evts['t'][-1]
        
        if last_time is None:
            dt_us = evts['t'][-1] - evts['t'][0]
            if dt_us == 0: dt_us = args.dt
        else:
            dt_us = current_time - last_time
            
        last_time = current_time
        
        # 1. Spatial Pre-Clustering
        clustering = DBSCAN(eps=5.0, min_samples=10).fit(coords)
        
        centroids = []
        cluster_labels = []
        for cluster_id in np.unique(clustering.labels_):
            if cluster_id == -1: continue # Drop unclustered noise
            mask = clustering.labels_ == cluster_id
            centroids.append(np.mean(coords[mask], axis=0))
            cluster_labels.append(cluster_id)
            
        centroids_arr = np.array(centroids, dtype=np.float32) if centroids else np.empty((0, 2), dtype=np.float32)
        
        # 2. Update tracker with centroids
        centroid_track_ids = tracker.update(centroids_arr, dt_us/1e6)
        
        # 3. Map track IDs back to raw events
        event_track_ids = np.full(len(coords), -1, dtype=np.int64)
        for i, tid in enumerate(centroid_track_ids):
            if tid >= 0:
                orig_cluster_id = cluster_labels[i]
                event_track_ids[clustering.labels_ == orig_cluster_id] = tid
        
        if args.pose and pose_estimator:
            current_pose = pose_estimator.update(tracker, current_time)
            all_pose_samples.extend(current_pose)
            latest_pose_points = current_pose

        batch_df = pl.DataFrame({
            "x": evts['x'],
            "y": evts['y'],
            "p": evts['p'],
            "t": evts['t'],
            "track_id": event_track_ids
        }).filter(pl.col("track_id") != -1)

        data_frames.append(batch_df)
        if gen_video:
            frame_gen.process_events(evts)
            
    if not data_frames:
        print("No tracks generated.")
        return None

    out_path = file_info.dest / str(args.dt) / f"{file_info.path.stem}-tracked.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if len(data_frames):
        final_df = pl.concat(data_frames)
        final_df.write_parquet(out_path)
        print(f"Saved {len(final_df)} events to {out_path}")
        
    if args.pose and len(all_pose_samples):
        pose_path = out_path.parent / f"{file_info.path.stem}-pose.parquet"
        pl.DataFrame(all_pose_samples).write_parquet(pose_path)
        print(f"Saved pose data to {pose_path}")
        
    if gen_video:
        print(f"Saved {outvid.output_path}")
        
    return out_path


def run_tuning(files, args):
    def objective(trial):
        dist_thresh = trial.suggest_float("dist_thresh", 10.0, 150.0)
        max_age = trial.suggest_int("max_age", 10, 50) 
        min_hits = trial.suggest_int("min_hits", 5, 20)
        R_var = trial.suggest_float("R_var", 0.1, 5.0) 
        Q_var = trial.suggest_float("Q_var", 10.0, 100.0)
        omega = trial.suggest_float("omega", -60, 60)
        total_score = 0.0
        ideal_dt = args.dt 

        if len(files) == 0:
            return 0.0
            
        for i, file_info in enumerate(files):
            evt_gen = EventBatchGenerator(
                file_path=file_info.path, 
                dt=ideal_dt,
                crop=file_info.crop,
                filter_polarity=args.filter_polarity
            )

            tracker = TunableTracker(
                dist_thresh=dist_thresh, max_age=max_age, min_hits=min_hits,
                R_var=R_var, Q_var=Q_var, omega=omega, shape=(evt_gen.height, evt_gen.width)
            )

            path_history = {} 
            last_time = None
            current_time = 0
            file_score = 0.0
            
            for item in evt_gen:
                if item is None: continue
                _, evts = item
                if len(evts) == 0:
                    continue

                coords = np.stack((evts['x'], evts['y']), axis=1).astype(np.float32)
                current_time = evts['t'][-1]
                if last_time is None:
                    dt_us = evts['t'][-1] - evts['t'][0] 
                    if dt_us == 0: dt_us = ideal_dt 
                else:
                    dt_us = current_time - last_time
                    if dt_us <= 0: dt_us = ideal_dt

                last_time = current_time
                
                # Spatial Pre-Clustering for tuning
                clustering = DBSCAN(eps=5.0, min_samples=10).fit(coords)
                centroids = [np.mean(coords[clustering.labels_ == cid], axis=0) 
                             for cid in np.unique(clustering.labels_) if cid != -1]
                centroids_arr = np.array(centroids, dtype=np.float32) if centroids else np.empty((0, 2), dtype=np.float32)

                tracker.update(centroids_arr, dt=dt_us/1e6)

                active_tids = set()
                for tid, track in tracker.tracks.items():
                    active_tids.add(tid)
                    if tid not in path_history: path_history[tid] = []
                    path_history[tid].append(track.kf.x[:2].copy())

                # Evaluate dead tracks immediately and free memory
                dead_tids = [tid for tid in path_history.keys() if tid not in active_tids]
                for tid in dead_tids:
                    history = np.array(path_history[tid])
                    if len(history) >= min_hits and len(history) >= 10:
                        min_x, min_y = np.min(history, axis=0)
                        max_x, max_y = np.max(history, axis=0)
                        box_diagonal = np.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
                        
                        # Filter out tracks that jitter in place
                        if box_diagonal >= 30.0:
                            file_score += float(len(history)) ** 2
                            
                    del path_history[tid]

            # Score any remaining active tracks at the end of the file
            for tid, track in tracker.tracks.items():
                if track.hits >= min_hits:
                    history = np.array(path_history[tid])
                    if len(history) < 10: continue
                    
                    min_x, min_y = np.min(history, axis=0)
                    max_x, max_y = np.max(history, axis=0)
                    box_diagonal = np.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
                    
                    if box_diagonal >= 30.0:
                        file_score += float(track.hits) ** 2
            num_unique_ids = max(1, tracker.next_id)
            file_score /= num_unique_ids
            total_score += file_score
            trial.report(total_score / (i + 1), step=i)
            if trial.should_prune(): raise optuna.TrialPruned()
            
        return total_score / len(files)
        
    pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=3, interval_steps=1)
    
    storage = None
    if args.optuna_db:
        storage = args.optuna_db if args.optuna_db.startswith("sqlite:///") else f"sqlite:///{args.optuna_db}"
        
    study = optuna.create_study(
        direction="maximize", 
        pruner=pruner,
        storage=storage,
        study_name=args.study_name,
        load_if_exists=True
    )

    # Inject a physically calculated baseline for circular motion
    study.enqueue_trial({
        "dist_thresh": 60.0,
        "max_age": 35,       
        "min_hits": 15,
        "R_var": 1.0,
        "Q_var": 50.0,
        "omega": 6.28        
    })
    
    study.optimize(objective, n_trials=args.n_trials)

    print("\n--- Optimization Complete ---")
    print(f"Best Score: {study.best_value:.2e}")
    print("Best Parameters:")
    for k, v in study.best_params.items():
        print(f"  '{k}': {v:.4f}")
        
    if args.save_params:
        with open(args.save_params, 'w') as f:
            json.dump(study.best_params, f, indent=4)
        print(f"\nSaved best parameters to {args.save_params}")
    try:
        print("\n--- Hyperparameter Importance ---")
        importances = optuna.importance.get_param_importances(study)
        for param, importance in importances.items():
            print(f"  '{param}': {importance:.4f} ({(importance * 100):.1f}%)")
    except Exception as e:
        print(f"Could not calculate importances: {e}")

    # 2. Generate Interactive Visualizations
    try:
        import optuna.visualization as vis

        # Ranks the parameters by their impact
        fig_importance = vis.plot_param_importances(study)
        fig_importance.write_html("optuna_importance.html")
        
        # Shows the effective ranges (score vs. parameter value)
        fig_slice = vis.plot_slice(study)
        fig_slice.write_html("optuna_slice.html")
        
        # Shows how parameters interact with each other
        fig_parallel = vis.plot_parallel_coordinate(study)
        fig_parallel.write_html("optuna_parallel.html")
        
        print("\nSaved interactive Optuna graphs to current directory (.html)")
    except ImportError:
        print("\nNote: Install 'plotly' to generate interactive Optuna graphs.")


def analyze_tracking_video(video_path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return

    cmap = plt.get_cmap('tab10')
    norm = mcolors.Normalize(vmin=0, vmax=10)

    target_colors = []
    for i in range(20): 
        seed = hash(i) % 10
        rgba = cmap(norm(seed))
        bgr = (int(rgba[2]*255), int(rgba[1]*255), int(rgba[0]*255))
        target_colors.append(bgr)
    target_colors = list(set(target_colors))

    tracks = defaultdict(list)
    frame_idx = 0

    print(f"Analyzing frames in {video_path}...")
    while True:
        ret, frame = cap.read()
        if not ret: break

        for color in target_colors:
            lower = np.array([max(c-10, 0) for c in color], dtype=np.uint8)
            upper = np.array([min(c+10, 255) for c in color], dtype=np.uint8)
            mask = cv2.inRange(frame, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                if cv2.contourArea(cnt) < 5: continue 
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    tracks[str(color)].append((frame_idx, np.array([cx, cy])))

        frame_idx += 1
        if frame_idx % 100 == 0: print(f"Scanned {frame_idx} frames...")
    cap.release()

    jitter_stats = []
    durations = []
    for color_key, positions in tracks.items():
        if len(positions) < 5: continue
        positions.sort(key=lambda x: x[0])
        coords = np.array([p[1] for p in positions])
        velocities = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        jitter = np.std(velocities)
        jitter_stats.append(jitter)
        durations.append(len(positions))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.hist(jitter_stats, bins=10, color='salmon', edgecolor='black')
    ax1.set_title('Track Stability (Lower is Better)')
    ax1.set_xlabel('Velocity Jitter (Std Dev in Pixels)')
    ax1.set_ylabel('Count of Tracks')
    ax1.axvline(x=5.0, color='red', linestyle='--', label='Unstable Threshold')
    ax1.legend()

    ax2.hist(durations, bins=10, color='skyblue', edgecolor='black')
    ax2.set_title('Track Continuity (Higher is Better)')
    ax2.set_xlabel('Track Duration (Frames)')
    ax2.set_ylabel('Count of Tracks')

    plt.tight_layout()
    print(f"Avg Jitter: {np.mean(jitter_stats):.2f} pixels")
    print(f"Avg Duration: {np.mean(durations):.1f} frames")
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Metavision Tracker and Pose Estimator")
    parser.add_argument("--input", type=str, required=True, help="Input raw file or directory of raw files")
    parser.add_argument("--out-dir", type=str, default="output", help="Output directory")
    
    # Modes
    parser.add_argument("--tune", action="store_true", help="Run Optuna tuning instead of tracking")
    parser.add_argument("--analyze-video", type=str, help="Path to video to analyze (skips main tracking)")
    
    # Feature Flags
    parser.add_argument("--no-video", action="store_true", help="Disable output video generation")
    parser.add_argument("--pose", action="store_true", help="Enable pose estimation")
    parser.add_argument("--plot-all-tracks", action="store_true", help="Plot all active tracks in the output video")
    parser.add_argument("--filter-polarity", type=int, default=None, help="Filter out the given polarity before tracking")
    
    # General Tracking Parameters
    parser.add_argument("--dt", type=int, default=10000, help="Accumulation time (dt) in microseconds")
    
    # TunableTracker Parameters
    parser.add_argument("--dist-thresh", type=float, default=13.4110, help="Distance threshold for tracking")
    parser.add_argument("--max-age", type=float, default=10.0, help="Max age for tracking")
    parser.add_argument("--min-hits", type=float, default=48.0, help="Minimum hits to confirm track")
    parser.add_argument("--r-var", type=float, default=8.4270, help="Kalman Filter R variance")
    parser.add_argument("--q-var", type=float, default=1.1344, help="Kalman Filter Q variance")
    parser.add_argument("--omega", type=float, default=6.0, help="Kalman Filter expected angular frequency")
    
    # Optuna Persistence & File I/O
    parser.add_argument("--optuna-db", type=str, help="Path to SQLite DB to save/resume Optuna study (e.g., tuning.db)")
    parser.add_argument("--study-name", type=str, default="tracker_tuning", help="Name of the Optuna study in the database")
    parser.add_argument("--save-params", type=str, help="Path to save best parameters as JSON after tuning")
    parser.add_argument("--load-params", type=str, help="Path to load tracking parameters from JSON (overrides default args)")
    
    # Optuna Tuning Params
    parser.add_argument("--n-trials", type=int, default=100, help="Number of Optuna trials")
    
    # Pose Estimator Params
    parser.add_argument("--max-k", type=int, default=6, help="Max nodes for pose estimation")
    parser.add_argument("--sigma-threshold", type=float, default=2.0, help="Covariance filter width (std devs)")
    parser.add_argument("--smoothing-alpha", type=float, default=0.1, help="Fluidity factor (0.1 smooth to 1.0 jittery)")

    args = parser.parse_args()

    if args.load_params:
        try:
            with open(args.load_params, 'r') as f:
                params = json.load(f)
                if 'dist_thresh' in params: args.dist_thresh = params['dist_thresh']
                if 'max_age' in params: args.max_age = params['max_age']
                if 'min_hits' in params: args.min_hits = params['min_hits']
                if 'R_var' in params: args.r_var = params['R_var']
                if 'Q_var' in params: args.q_var = params['Q_var']
                if 'omega' in params: args.omega = params['omega']
                print(f"Loaded parameters from {args.load_params}")
        except FileNotFoundError:
            print(f"Error: Parameter file {args.load_params} not found.")
            sys.exit(1)

    if args.analyze_video:
        analyze_tracking_video(args.analyze_video)
        return

    input_path = Path(args.input)
    if input_path.is_dir():
        raw_files = glob(str(input_path / '*.raw'))
    else:
        raw_files = [str(input_path)]

    out_dir = Path(args.out_dir)
    files = [File(path=Path(f), crop=None, dest=out_dir) for f in raw_files]

    if len(files) == 0:
        print("No raw files found.")
        sys.exit(1)

    if args.tune:
        run_tuning(files, args)
    else:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        saved_paths = []
        for file_info in files:
            if not args.no_video:
                output_video_path = file_info.dest / str(args.dt) / f'{file_info.path.stem}.mp4'
                with Video(codec=fourcc, dimensions=(640,480), output_path=output_video_path, delay_init=True, fps=20) as v:
                    saved_paths.append(process_and_save(file_info, args, outvid=v))
            else:
                saved_paths.append(process_and_save(file_info, args))

if __name__ == "__main__":
    main()
