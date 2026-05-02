"""

Defines some tools to handle events, mimicking dat_tools.py.
In particular :
    -> defines functions to read events from binary .npy files using numpy
"""
from __future__ import annotations
import numpy as np
__all__: list[str] = ['np', 'parse_header', 'stream_events']
def parse_header(fhandle):
    """
    
        Parses the header of a .npy file
    
        Args:
            fhandle (file): File handle to a DAT file.
    
        Returns:
            int position of the file cursor after the header
            int type of event
            int size of event in bytes
            size (height, width) tuple of int or None
        
    """
def stream_events(file_handle, buffer, dtype, ev_count = -1):
    """
    
        Streams data from opened file_handle
    
        Args :
            file_handle: File object, needs to be opened.
            buffer (events numpy array): Pre-allocated buffer to fill with events.
            dtype (numpy dtype): Expected fields.
            ev_count (int): Number of events.
        
    """
