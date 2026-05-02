"""

Simple Iterator built around the Metavision Reader classes.
"""
from __future__ import annotations
from metavision_core.event_io.h5_io import HDF5EventsReader
from metavision_core.event_io.py_reader import EventDatReader
from metavision_core.event_io.raw_reader import RawReaderBase
import numpy as np
__all__: list[str] = ['EventDatReader', 'EventsIterator', 'HDF5EventsReader', 'RawReaderBase', 'np']
class EventsIterator:
    """
    
        EventsIterator is a small convenience class to iterate through either a camera, a RAW file,
        an HDF5 event file or a DAT file.
    
        Note that, as every Python iterator, you can consume an EventsIterator only once.
    
        Attributes:
            reader : class handling the file or camera.
            delta_t (int): Duration of served event slice in us.
            max_duration (int): If not None, maximal duration of the iteration in us.
            end_ts (int): If max_duration is not None, last timestamp to consider.
            relative_timestamps (boolean): Whether the timestamp of served events are relative to the current
                reader timestamp, or since the beginning of the recording.
    
        Args:
            input_path (str): Path to the file to read. If `path` is an empty string or a camera serial number it will
                              try to open that camera instead.
            start_ts (int): First timestamp to consider (in us). If mode is "delta_t" or "mixed", start_ts must be a
                            multiple of delta_t, otherwise a ValueError is thrown.
            mode (string): Load by timeslice or number of events. Either "delta_t", "n_events" or "mixed",
                where mixed uses both delta_t and n_events and chooses the first met criterion.
            delta_t (int): Duration of served event slice in us.
            n_events (int): Number of events in the timeslice.
            max_duration (int): If not None, maximal duration of the iteration in us.
            relative_timestamps (boolean): Whether the timestamp of served events are relative to the current
                reader timestamp, or since the beginning of the recording.
            **kwargs: Arbitrary keyword arguments passed to the underlying RawReaderBase or
                EventDatReader.
    
        Examples:
            >>> for ev in EventsIterator("beautiful_record.raw", delta_t=1000000, max_duration=1e6*60):
            >>>     print("Rate : {:.2f}Mev/s".format(ev.size * 1e-6))
        
    """
    @classmethod
    def from_device(cls, device, start_ts = 0, n_events = 10000, delta_t = 50000, mode = 'delta_t', max_duration = None, relative_timestamps = False, **kwargs):
        """
        Alternate way of constructing an EventsIterator from an already initialized HAL device.
        
                Note that it is not recommended to leave a device in the global scope, so either create the HAL device in a
                function or, delete explicitly afterwards. In some cameras this could result in an undefined behaviour.
        
                Args:
                    device (device): Hal device object initialized independently.
                    start_ts (int): First timestamp to consider.
                    mode (string): Load by timeslice or number of events. Either "delta_t" or "n_events"
                    delta_t (int): Duration of served event slice in us.
                    n_events (int): Number of events in the timeslice.
                    max_duration (int): If not None, maximal duration of the iteration in us.
                    relative_timestamps (boolean): Whether the timestamp of served events are relative to the current
                        reader timestamp, or since the beginning of the recording.
                    **kwargs: Arbitrary keyword arguments passed to the underlying RawReaderBase.
        
                Examples:
                    >>> from metavision_core.event_io.raw_reader import initiate_device
                    >>> device = initiate_device(path=args.input_path)
                    >>> # call any methods on device
                    >>> mv_it = EventsIterator.from_device(device=device)
                    >>> del device  # do not leave the device variable in the global scope
                
        """
    def __del__(self):
        ...
    def __init__(self, input_path, start_ts = 0, mode = 'delta_t', delta_t = 10000, n_events = 10000, max_duration = None, relative_timestamps = False, **kwargs):
        ...
    def __iter__(self):
        ...
    def __repr__(self):
        ...
    def _init_readers(self, input_path, **kwargs):
        ...
    def get_current_time(self):
        ...
    def get_ext_trigger_events(self):
        """
        
                Returns a copy of all external trigger events that have been loaded until now in the record
                
        """
    def get_size(self):
        """
        Function returning the size of the imager which produced the events.
        
                Returns:
                    Tuple of int (height, width) which might be (None, None)
        """
