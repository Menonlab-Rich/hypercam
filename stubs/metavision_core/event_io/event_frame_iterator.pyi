"""

Simple Iterator over event frame reader (diff and histo)
"""
from __future__ import annotations
from collections import deque
from metavision_core.event_io.raw_info import is_event_frame_raw
from metavision_core.event_io.raw_info import is_event_raw
from metavision_core.event_io.raw_info import raw_file_header
from metavision_hal import DeviceDiscovery
from metavision_sdk_core import RawEventFrameConverter
import os as os
__all__: list[str] = ['DeviceDiscovery', 'EventFrameIterator', 'EventFrameReader', 'RawEventFrameConverter', 'deque', 'is_event_frame_raw', 'is_event_raw', 'os', 'raw_file_header']
class EventFrameIterator:
    def __del__(self):
        ...
    def __init__(self, input_path):
        """
        
                Iterates over a raw file of either DIFF3D or HISTO3D
                
        """
    def __iter__(self):
        ...
    def get_frame_type(self):
        """
        
                Returns the frame type. Will be either 'DIFF3D' or 'HISTO3D'
                
        """
    def get_size(self):
        """
        Function returning the size of the imager which produced the events.
        
                Returns:
                    Tuple of int (height, width) which might be (None, None)
        """
class EventFrameReader:
    def __del__(self):
        ...
    def __enter__(self):
        ...
    def __exit__(self, type, value, traceback):
        ...
    def __init__(self, input_path):
        """
        
                Reads a raw file of either DIFF3D or HISTO3D
                
        """
    def _decode_next_frames(self):
        ...
    def get_size(self):
        ...
    def is_done(self):
        ...
    def load_next_frame(self):
        ...
