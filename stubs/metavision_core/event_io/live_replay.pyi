"""

Live Replay Events Iterator, this is for user friendliness
"""
from __future__ import annotations
from metavision_core.event_io.events_iterator import EventsIterator
import os as os
import time as time
__all__: list[str] = ['EventsIterator', 'LiveReplayEventsIterator', 'is_live_camera', 'os', 'time']
class LiveReplayEventsIterator:
    """
    
        LiveReplayEventsIterator allows replaying a record in "live" ("real-time") condition or at a
        speed-up (or slow-motion) factor of real-time.
    
        Args:
            events_iterator (EventsIterator): event iterator
            replay_factor (float): if greater than 1.0 we replay with slow-motion,
            otherwise this is a speed-up over real-time.
        
    """
    def __init__(self, events_iterator, replay_factor = 1.0):
        ...
    def __iter__(self):
        ...
    def get_current_time(self):
        ...
    def get_size(self):
        ...
    @property
    def delta_t(self):
        ...
    @property
    def start_ts(self):
        ...
def is_live_camera(input_path):
    """
    
        Checks if input_path is a live camera
    
        Args:
            input_path (str): path to the file to read. if `path` is an empty string or a camera serial number,
            this function will return true.
        
    """
