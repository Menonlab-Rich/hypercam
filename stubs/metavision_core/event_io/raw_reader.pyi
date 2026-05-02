"""

This class loads events from a camera or a RAW file

 the interface is close to DatReader but not everything could be implemented
    - no backward seek functionality
    - cd events dtype contains a 2 byte offset
"""
from __future__ import annotations
from collections import deque
from metavision_hal import DeviceDiscovery
from metavision_hal import RawFileConfig
from metavision_sdk_core import SharedCdEventsBufferProducer as EventsBufferProducer
import numpy as np
import numpy.dtypes
import os as os
__all__: list[str] = ['DeviceDiscovery', 'EventCD', 'EventExtTrigger', 'EventsBufferProducer', 'RawFileConfig', 'RawReader', 'RawReaderBase', 'deque', 'initiate_device', 'np', 'os']
class RawReader(RawReaderBase):
    """
    
        RawReader loads events from a RAW file or a camera
    
        When reading a file, RawReader allows to read the events while maintaining a position of the cursor.
        Further manipulations like advancing the cursor in time are possible.
    
        Attributes:
            path (string): Path to the file being read. If `path` is an empty string or a camera serial number it will
                try to open that camera instead.
            current_time (int): Indicating the position of the cursor in the file in us.
            do_time_shifting (bool): If True the origin of time is a few us from the first events.
                Otherwise it is when the camera was started.
    
        Args:
            record_base (string): Path to the record being read.
            do_time_shifting (bool): If True the origin of time is a few us from the first events.
                Otherwise it is when the camera was started.
            use_external_triggers (Channel List): list of integer values corresponding to the channels of external trigger
                to be activated (only relevant for a live camera).
        
    """
    @classmethod
    def from_device(cls, device, max_events = 10000000):
        """
        
                Alternate way of constructing an RawReader from an already initialized HAL device.
        
                        Note that it is not recommended to leave a device in the global scope, so either create the HAL device
                        in a function or, delete explicitly afterwards. In some cameras this could result in an undefined
                        behaviour.
        
                Args:
                    device (device): Hal device object initialized independently.
        
                Examples:
                    >>> device = initiate_device(path=args.input_path)
                    >>> # call any methods on device
                    >>> reader = RawReader.from_device(device=device)
                    >>> del device  # do not leave the device variable in the global scope
                
        """
    def __init__(self, record_base, max_events = 10000000, do_time_shifting = True, device = None, initiate_device = True, use_external_triggers = list()):
        ...
    def __repr__(self):
        ...
    def _count_ev_loaded(self):
        """
        helper function to count loaded events in rolling buffer
        """
    def _last_loaded_ts(self):
        """
        returns the timestamp of the last loaded event and -1 if None are in the buffer
        """
    def _process_batch(self, ts, batch):
        ...
    def _reset_buffer(self):
        ...
    def is_done(self):
        """
        
                Indicates if all events have been already read.
                
        """
    def load_delta_t(self, delta_t):
        """
        
                Loads all the events contained in the next *delta_t* microseconds.
        
                Args:
                    delta_t (int): Interval of time in us since last loading, within which events are loaded
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
                
        """
    def load_mixed(self, n_events, delta_t):
        """
        Loads batch of n events or delta_t microseconds, whichever comes first.
        
                Args:
                    n_events (int): Maximum number of events that will be loaded.
                    delta_t (int): Maximum allowed slice duration (in us).
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
        
                Note that current time will be incremented to reach the timestamp of the first event not loaded yet unless
                the maximal time slice duration is reached in which case current time will be increased by delta_t instead.
                
        """
    def load_n_events(self, n_events):
        """
        
                Loads a batch of *n_events* events.
        
                Args:
                    n_events (int): Number of events to load
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
                
        """
    def seek_event(self, n_events):
        """
        
                Advance n_events into the RAW file. The decoded events are dropped.
        
                Args:
                    n_events (int): number of events to skip.
                
        """
    def seek_time(self, final_time):
        """
        
                seeks into the RAW file until current_time >= final_time.
        
                Args:
                    final_time (int): Timestamp in us at which the search stops.
                
        """
class RawReaderBase:
    @classmethod
    def from_device(cls, device, ev_count = 0, delta_t = 50000):
        ...
    def __del__(self):
        ...
    def __enter__(self):
        ...
    def __exit__(self, type, value, traceback):
        ...
    def __init__(self, record_base, device = None, do_time_shifting = True, ev_count = 0, delta_t = 50000, initiate_device = True, use_external_triggers = list()):
        ...
    def __repr__(self):
        ...
    def _advance(self, n_events = 0, delta_t = 0, drop_events = False):
        """
        
                decodes events until either n_events or delta_t events are decoded.
        
                Args:
                    n_events (int): number of events to decode.
                    delta_t (int): duration in us of events to decode
                    drop_events (boolean): if True drop the decoded events until the desired point.
                
        """
    def _count_ev_loaded(self):
        """
        return the number of events in buffer
        """
    def _last_loaded_ts(self):
        """
        returns the timestamp of the last loaded event and -1 if None are in the buffer
        """
    def _load_next_buffer(self):
        """
        
                Loads a batch of events from the queue.
        
                Returns:
                    events
                
        """
    def _process_batch(self, ts, batch):
        ...
    def _reset_buffer(self):
        ...
    def _reset_state_vars(self):
        ...
    def _run(self):
        """
        "decode a packet
        """
    def clear_ext_trigger_events(self):
        """
        Deletes previously stored external trigger events
        """
    def current_event_index(self):
        """
        Returns the number of event already loaded
        """
    def get_ext_trigger_events(self):
        """
        Returns all external trigger events that have been loaded until now in the record
        """
    def get_size(self):
        """
        Function returning the size of the imager which produced the events.
        
                Returns:
                    Tuple of int (height, width)
        """
    def is_done(self):
        """
        
                indicates if all events have been loaded and if the rolling buffer is empty
                
        """
    def load_delta_t(self, delta_t):
        """
        
                Loads all the events contained in the next *delta_t* microseconds.
        
                Args:
                    delta_t (int): Interval of time in us since last loading, within which events are loaded
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
                
        """
    def load_mixed(self, n_events, delta_t):
        """
        Loads batch of n events or delta_t microseconds, whichever comes first.
        
                Args:
                    n_events (int): Maximum number of events that will be loaded.
                    delta_t (int): Maximum allowed slice duration (in us).
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
        
                Note that current time will be incremented to reach the timestamp of the first event not loaded yet Unless
                the maximal time slice duration is reached in which case current time will be increased by delta_t instead.
                
        """
    def load_n_events(self, n_events):
        """
        
                Loads a batch of *n_events* events.
        
                Args:
                    n_events (int): Number of events to load
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
                
        """
    def reset(self):
        """
        Resets at beginning of file.
        """
    def seek_event(self, n_events):
        """
        
                Advance n_events into the RAW file
        
                Args:
                    n_events (int): number of events to skip (only multiples of n_events are supported.).
                
        """
    def seek_time(self, final_time):
        """
        
                seeks into the RAW file until current_time >= final_time.
        
                Args:
                    final_time (int): Timestamp in us at which the search stops (only multiples of delta_t are supported.).
                
        """
def initiate_device(path, do_time_shifting = True, use_external_triggers = list()):
    """
    
        Constructs a device either from a file (if the path ends with .raw) or a camera.
    
        This device can be used in conjunction with `RawReader.from_device` or `EventsIterator.from_device`
        to create a RawReader or an EventsIterator with a customized HAL device.
    
        Args:
            path (str): either path to a RAW file (having a .raw or .RAW extension) or a camera serial number.
                Leave blank to take the first available camera.
            do_time_shifting (bool): in case of a file, makes the timestamps start close to 0us.
            use_external_triggers (Channel List): list of channels of external trigger to be activated (only relevant for a live camera).
                On most systems, only one (MAIN) channel can be enabled.
        Returns:
            device: a HAL Device.
    
        
    """
EventCD: numpy.dtypes.VoidDType  # value = dtype({'names': ['x', 'y', 'p', 't'], 'formats': ['<u2', '<u2', '<i2', '<i8'], 'offsets': [0, 2, 4, 8], 'itemsize': 16})
EventExtTrigger: numpy.dtypes.VoidDType  # value = dtype({'names': ['p', 't', 'id'], 'formats': ['<i2', '<i8', '<i2'], 'offsets': [0, 8, 16], 'itemsize': 24})
