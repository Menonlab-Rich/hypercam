"""

More efficient reimplementation.
The main difference is cuda kernels & possibility to
directly stream the voxel grid.
"""
from __future__ import annotations
from metavision_core_ml.video_to_event.cutoff_kernels import _cpu_kernel_dynamic_moving_average
from metavision_core_ml.video_to_event.cutoff_kernels import _cuda_kernel_dynamic_moving_average
from metavision_core_ml.video_to_event.events_kernels import _cpu_kernel_count_events
from metavision_core_ml.video_to_event.events_kernels import _cpu_kernel_fill_events
from metavision_core_ml.video_to_event.events_kernels import _cpu_kernel_voxel_grid_sequence
from metavision_core_ml.video_to_event.events_kernels import _cuda_kernel_count_events
from metavision_core_ml.video_to_event.events_kernels import _cuda_kernel_fill_events
from metavision_core_ml.video_to_event.events_kernels import _cuda_kernel_voxel_grid_sequence
from numba import cuda
import numpy as np
import torch as torch
from torch import nn
__all__: list[str] = ['GPUEventSimulator', 'cuda', 'nn', 'np', 'torch']
class GPUEventSimulator(torch.nn.modules.module.Module):
    """
    
        GPU Event Simulator of events from frames & timestamps.
    
        Implementation is based on the following publications:
    
        - Video to Events: Recycling Video Datasets for Event Cameras: Daniel Gehrig et al.
        - V2E: From video frames to realistic DVS event camera streams: Tobi Delbruck et al.
    
        Args:
            batch_size (int): number of video clips / batch
            height (int): height
            width (int): width
            c_mu (float or list): threshold average
                                  if scalar will consider same OFF and ON thresholds
                                  if list, will be considered as [ths_OFF, ths_ON] 
            c_std (float): threshold standard deviation
            refractory period (int): time before event can be triggered again
            leak_rate_hz (float): frequency of reference voltage leakage
            cutoff_hz (float): frequency for photodiode latency
            shot_noise_hz (float): frequency of shot noise events
        
    """
    @staticmethod
    def count_events(*args, **kwargs):
        """
        
                Estimates the number of events per pixel.
        
                Args:
                    log_images (Tensor): shape (H, W, total_num_frames) tensor containing the video frames
                    video_len (Tensor): shape (B,) len of each video in the batch.
                    images_ts (Tensor): shape (B, max(video_len)) timestamp associated with each frame.
                    first_times (Tensor): shape (B) whether the video is a new one or the continuation of one.
                    reset: do reset the count variable
                Returns:
                    counts: B,H,W
                
        """
    @staticmethod
    def dynamic_moving_average(*args, **kwargs):
        """
        
        
                Converts byte images to log and
                performs a pass-band motion blur of incoming images.
                This simulates the latency of the photodiode w.r.t to incoming
                light dynamic.
        
                Args:
                    images (torch.Tensor): H,W,T byte or float images in the 0 to 255 range
                    num_frames (torch.Tensor): shape (B,) len of each video in the batch.
                    timestamps (torch.Tensor): B,T timestamps
                    first_times (torch.Tensor): B flags
                    eps (float): epsilon factor
                
        """
    @staticmethod
    def event_volume(*args, **kwargs):
        """
        
                Computes a volume of discretized images formed after the events, without
                storing the AER events themselves. We go from simulation directly to this
                space-time quantized representation. You can obtain the event-volume of
                [Unsupervised Event-based Learning of Optical Flow, Zhu et al. 2018] by
                specifying the mode to "bilinear" or you can obtain a stack of histograms
                if mode is set to "nearest".
        
                Args:
                    log_images (Tensor): shape (H, W, total_num_frames) tensor containing the video frames
                    video_len (Tensor): shape (B,) len of each video in the batch.
                    images_ts (Tensor): shape (B, max(video_len)) timestamp associated with each frame.
                    first_times (Tensor): shape (B) whether the video is a new one or the continuation of one.
                    nbins (int): number of time-bins for the voxel grid
                    mode (str): bilinear or nearest
                    split_channels: if True positive and negative events have a distinct channels instead of doing their
                        difference in a single channel.
                
        """
    @staticmethod
    def event_volume_sequence(*args, **kwargs):
        """
        
                Computes a volume of discretized images formed after the events, without
                storing the AER events themselves. We go from simulation directly to this
                space-time quantized representation. You can obtain the event-volume of
                [Unsupervised Event-based Learning of Optical Flow, Zhu et al. 2018] by
                specifying the mode to "bilinear" or you can obtain a stack of histograms
                if mode is set to "nearest".
                Here, we also receive a sequence of target timestamps to cut non uniformly the event volumes.
        
                Args:
                    log_images (Tensor): shape (H, W, total_num_frames) tensor containing the video frames
                    video_len (Tensor): shape (B,) len of each video in the batch.
                    images_ts (Tensor): shape (B, max(video_len)) timestamp associated with each frame.
                    first_times (Tensor): shape (B) whether the video is a new one or the continuation of one.
                    nbins (int): number of time-bins for the voxel grid
                    mode (str): bilinear or nearest
                    split_channels: if True positive and negative events have a distinct channels instead of doing their
                        difference in a single channel.
                
        """
    @staticmethod
    def get_events(*args, **kwargs):
        """
        
                Retrieves the AER event list in a pytorch array.
        
                Args:
                    log_images (Tensor): shape (H, W, total_num_frames) tensor containing the video frames
                    video_len (Tensor): shape (B,) len of each video in the batch.
                    images_ts (Tensor): shape (B, max(video_len)) timestamp associated with each frame.
                    first_times (Tensor): shape (B) whether the video is a new one or the continuation of one.
                Returns:
                    events: N,5 in batch_index, x, y, polarity, timestamp (micro-seconds)
                
        """
    @staticmethod
    def log_images(*args, **kwargs):
        """
        
                Converts byte images to log
        
                Args:
                    u8imgs (torch.Tensor): B,C,H,W,T byte images
                    eps (float): epsilon factor
                
        """
    def __init__(self, batch_size, height, width, c_mu = 0.1, c_std = 0.022, refractory_period = 10, leak_rate_hz = 0, cutoff_hz = 0, shot_noise_hz = 0):
        ...
    def _kernel_call(self, log_images, video_len, image_ts, first_times, cuda_kernel, cpu_kernel, args_list, *args, reset_rng_states = True):
        """
        
                generic functions to call simulation and feature computation kernels.
        
                Args:
                    log_images (Tensor): shape (H, W, total_num_frames) tensor containing the video frames
                    video_len (Tensor): shape (B,) len of each video in the batch.
                    images_ts (Tensor): shape (B, max(video_len)) timestamp associated with each frame.
                    first_times (Tensor): shape (B) whether the video is a new one or the continuation of one.
                    cuda_kernel (function): numba.cuda jitted function (defined in events_kernel.py)
                    cpu_kernel (function): numba jitted function (defined in events_kernel.py)
                    args_list (Tensor list): additional Tensor arguments that the kernel might take as argument.
                    *args: additional flags for the kernel
                
        """
    def forward(self):
        ...
    def get_size(self):
        ...
    def randomize_broken_pixels(self, first_times, video_proba = 0.01, crazy_pixel_proba = 0.0005, dead_pixel_proba = 0.005):
        """
        
                Simulates dead & crazy pixels
        
                Args:
                    first_times: B video just started flags
                    video_proba: probability to simulate broken pixels
                
        """
    def randomize_cutoff(self, first_times, cutoff_min = 0, cutoff_max = 900):
        """
        
                Randomizes the cutoff rates per video
        
                Args:
                    first_times: B video just started flags
                    cutoff_min: in hz
                    cutoff_max: in hz
                
        """
    def randomize_leak(self, first_times, leak_min = 0, leak_max = 1):
        """
        
                Randomizes the leak rates per video
        
                Args:
                    first_times: B video just started flags
                    leak_min: in hz
                    leak_max: in hz
                
        """
    def randomize_refractory_periods(self, first_times, ref_min = 10, ref_max = 1000):
        """
        
                Randomizes the refractory period per video
        
                Args:
                    first_times: B video just started flags
                    ref_min: in microseconds
                    ref_max: in microseconds
                
        """
    def randomize_shot(self, first_times, shot_min = 0, shot_max = 1):
        """
        
                Randomizes the shot noise per video
        
                Args:
                    shot_min: in hz
                    shot_max: in hz
                
        """
    def randomize_thresholds(self, first_times, th_mu_min = 0.05, th_mu_max = 0.2, th_std_min = 0.001, th_std_max = 0.01):
        """
        
                Re-Randomizes thresholds per video
        
                Args:
                    first_times: B video just started flags
                    th_mu_min (scalar or list of scalars): min average threshold 
                                      if list, will be considered as [th_mu_min_OFF, th_mu_min_ON] 
                    th_mu_max (scalar or list of scalars): max average threshold 
                                      if list, will be considered as [th_mu_max_OFF, th_mu_max_ON] 
                    th_std_min: min threshold standard deviation
                    th_std_max: max threshold standard deviation
                
        """
