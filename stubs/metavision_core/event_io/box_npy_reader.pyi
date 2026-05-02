from __future__ import annotations
import metavision_core.event_io.py_reader
from metavision_core.event_io.py_reader import EventNpyReader
import numpy as np
import numpy.dtypes
__all__: list[str] = ['EventBbox', 'EventBboxNpyReader', 'EventNpyReader', 'np']
class EventBboxNpyReader(metavision_core.event_io.py_reader.EventNpyReader):
    """
    
        EventBboxNpyReader class to read NPY long files.
    
        Attributes:
            path (string): Path to the file being read
            current_time (int): Indicating the position of the cursor in the file in us
            duration_s (int): Indicating the total duration of the file in seconds
    
        Args:
            event_file (str): file containing events
        
    """
    def __init__(self, event_file):
        ...
    def open_file(self):
        ...
EventBbox: numpy.dtypes.VoidDType  # value = dtype({'names': ['t', 'x', 'y', 'w', 'h', 'class_id', 'track_id', 'class_confidence'], 'formats': ['<i8', '<f4', '<f4', '<f4', '<f4', '<u4', '<u4', '<f4'], 'offsets': [0, 8, 12, 16, 20, 24, 28, 32], 'itemsize': 40})
