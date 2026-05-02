"""

This class loads events from DAT or NPY files
"""
from __future__ import annotations
from metavision_core.event_io import dat_tools as dat
from metavision_core.event_io import npy_tools as npy_format
import numpy as np
import os as os
__all__: list[str] = ['EventBaseReader', 'EventDatReader', 'EventNpyReader', 'dat', 'np', 'npy_format', 'os']
class EventBaseReader:
    """
    
        EventBaseReader base class to pure python event readers.
    
        EventBaseReader allows reading a file of events while maintaining a position of the cursor.
        Further manipulations like advancing the cursor or going backward are allowed.
    
        Attributes:
            path (string): Path to the file being read
            current_time (int): Indicating the position of the cursor in the file in us
            duration_s (int): Indicating the total duration of the file in seconds
    
        Args:
            event_file (str): file containing events
        
    """
    def __del__(self):
        ...
    def __enter__(self):
        ...
    def __exit__(self, type, value, traceback):
        ...
    def __init__(self, event_file):
        ...
    def __repr__(self):
        """
        String representation of a `DatReader` object.
        
                Returns:
                    string describing the DatReader state and attributes
                
        """
    def current_event_index(self):
        """
        Returns the number of event already loaded
        """
    def event_count(self):
        """
        Getter on event_count.
        
                Returns:
                    An int indicating the total number of events in the file
                
        """
    def get_first_ev_timestamp(self):
        """
        
                Returns the timestamp of the first event in us
                
        """
    def get_last_ev_timestamp(self):
        """
        
                Returns the timestamp of the last event in us
                
        """
    def get_size(self):
        """
        Function returning the size of the imager which produced the events.
        
                Returns:
                    Tuple of int (height, width) which might be (None, None)
        """
    def is_done(self):
        """
        Returns True if the end of the file has been reached.
        """
    def load_delta_t(self, delta_t):
        """
        
                Loads events corresponding to a slice of time, starting from the DatReader's `current_time`.
        
                Args:
                    delta_t (int): slice duration (in us).
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
        
                Note that current time will be incremented by `delta_t`.
                If an event is timestamped at exactly current_time it will not be loaded.
                
        """
    def load_mixed(self, n_events, delta_t):
        """
        
                Loads batch of n events or delta_t microseconds, whichever comes first.
        
                Args:
                    n_events (int): Maximum number of events that will be loaded.
                    delta_t (int): Maximum allowed slice duration (in us).
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
        
                Note that current time will be incremented to reach the timestamp of the first event not loaded yet.
                However if the maximal time slice duration is reached, current time will be increased by delta_t instead.
                
        """
    def load_n_events(self, n_events):
        """
        
                Loads batch of n events.
        
                Args:
                    n_events (int): Number of events that will be loaded
        
                Returns:
                    events (numpy array): structured numpy array containing the events.
        
                
        """
    def open_file(self):
        ...
    def reset(self):
        """
        Resets at beginning of file.
        """
    def seek_event(self, n_events):
        """
        
                Seeks in the file by `n_events` events
        
                Args:
                    n_events (int): seek in the file the nth events
        
                
        """
    def seek_time(self, expected_time, term_criterion = 100000):
        """
        Goes to the time expected_time inside the file.
                This is implemented using a binary search algorithm.
        
                Args:
                    expected_time (int): Expected time
                    term_criterion (int): Binary search termination criterion in nb of events
        
                Once the binary search has found a buffer of size *term_criterion* events, containing the
                *expected_time*. It will load them in memory and perform a `searchsorted`_ from numpy, so that the end
                of the binary search doesn't take to many iterations in python.
        
                .. _searchsorted:
                    https://numpy.org/doc/stable/reference/generated/numpy.searchsorted.html
                
        """
class EventDatReader(EventBaseReader):
    """
    
        EventDatReader class to read DAT long files.
        DAT files are a binary format with events stored
        with polarity, x and y casted into a uint32 and timestamp on another uint32.
        This format still exists in many of our datasets, so this file is used to support it.
    
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
class EventNpyReader(EventBaseReader):
    """
    
        EventNpyReader class to read NPY long files.
    
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
