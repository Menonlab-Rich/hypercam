"""

Get Raw Duration: Either search for a json filename called "path_name_info.json" or compute duration itself.
"""
from __future__ import annotations
from genericpath import exists
from genericpath import isfile
import json as json
from metavision_core.event_io.raw_reader import RawReader
from metavision_sdk_base import GenericHeader
from posixpath import splitext
__all__: list[str] = ['GenericHeader', 'RawReader', 'exists', 'get_raw_info', 'is_event_frame_raw', 'is_event_raw', 'isfile', 'json', 'raw_file_header', 'raw_histo_header_bits_per_channel', 'read_raw_info', 'splitext']
def get_raw_info(path):
    """
    
        Reads path raw info json file.
        If it does not exists, it will create it.
    
        Args:
            path (str): raw path
        
    """
def is_event_frame_raw(path):
    """
    
        Reads the header of a raw file and returns True if it contains event frames, False otherwise
        
    """
def is_event_raw(path):
    """
    
        Reads the header of a raw file and returns True if it contains events, False otherwise
        
    """
def raw_file_header(path):
    """
    
        Reads path raw and returns a dictionary of the header
        
    """
def raw_histo_header_bits_per_channel(path):
    """
    
        Reads the header of a histo raw file and returns the number of bits used for the negative and positive channels
        
    """
def read_raw_info(path):
    """
    
        Collects information of duration by running RawReader.
    
        Args:
            path (str): raw path
        
    """
