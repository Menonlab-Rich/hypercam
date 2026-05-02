"""

Reads & Seeks into an HDF5 event file
"""
from __future__ import annotations
import h5py as h5py
import numpy as np
import numpy.dtypes
__all__: list[str] = ['EventCD', 'EventExtTrigger', 'HDF5EventsReader', 'h5py', 'np']
class HDF5EventsReader:
    """
    
        Reads & Seeks into an HDF5 event file
    
        Args:
            src_name (str): input path
        
    """
    def __del__(self):
        ...
    def __enter__(self):
        ...
    def __exit__(self, type, value, traceback):
        ...
    def __init__(self, path):
        ...
    def get_ext_trigger_events(self):
        """
        
                Load external events which are triggered before the current time.
                
        """
    def get_size(self):
        """
        
                Resolution of the sensor that produced the events.
                The format of the resolution is 'widthxheight', such as '640x480'
                
        """
    def is_done(self):
        ...
    def load_delta_t(self, delta_t):
        """
        
                Load events whose timestamp ranges (current_time, current_time + delta_t)
                
        """
    def load_mixed(self, n_events, delta_t):
        """
        
                Try loading n events, if the duration of these events is larger than delta_t,
                then only keep part of the events which stay inside the time range(delta_t).
                
        """
    def load_n_events(self, n_events):
        """
        
                Continue loading n events once a time
                
        """
    def seek_time(self, ts):
        """
        
                Move the position to the event whose timestamp is before and closest to ts.
        
                Assume the timetable of indexes_CD is:
                (    0,    -1), (    0,    19), (  797,  2010), ( 1513,  4002),
                ( 2234,  6000), ( 3067,  8000), ( 3919, 10000), ( 4715, 12008),
                ( 5495, 14003), ( 6324, 16002), ( 7195, 18009), ( 7964, 20000)
        
                When ts = 12333, table_idx = 12333 // 2000 = 6, then events[3919: 5495+1] will be loaded and its timestamp range 
                is (10000, 14003), the pointer will be moved to the event whose timestamp is before and closest to 12333.
        
                When ts = 1998, table_idx = 1998 // 2000 = 0, then events[0: 797+1] will be loaded and its timestamp range 
                is (19, 2010), the pointer will be moved to the event whose timestamp is before and closest to 1998.
        
                
        """
EventCD: numpy.dtypes.VoidDType  # value = dtype({'names': ['x', 'y', 'p', 't'], 'formats': ['<u2', '<u2', '<i2', '<i8'], 'offsets': [0, 2, 4, 8], 'itemsize': 16})
EventExtTrigger: numpy.dtypes.VoidDType  # value = dtype({'names': ['p', 't', 'id'], 'formats': ['<i2', '<i8', '<i2'], 'offsets': [0, 8, 16], 'itemsize': 24})
