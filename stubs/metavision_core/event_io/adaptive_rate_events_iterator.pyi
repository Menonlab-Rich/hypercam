"""

Adaptive rate events iterator built around the EventsIterator class
"""
from __future__ import annotations
from metavision_core.event_io.events_iterator import EventsIterator
from metavision_sdk_core import AdaptiveRateEventsSplitterAlgorithm
import os as os
__all__: list[str] = ['AdaptiveRateEventsIterator', 'AdaptiveRateEventsSplitterAlgorithm', 'EventsIterator', 'os']
class AdaptiveRateEventsIterator:
    """
    
        AdaptiveRateEventsIterator is small convenience class to iterate through a recording
    
        It will produce reasonably sharp slices of events of variable time duration and variable number of events,
        depending on the content of the stream itself.
    
        Internally, it uses a compation of variance per event as a criterion for the sharpness of the current slice
        of events.
        An additional criterion is the proportion of active pixels containing both positive and negative events.
    
        Args:
            input_path (str): Path to the file to read
            thr_var_per_event (float): minimum variance per pixel value to reach before considering splitting the slice.
            downsampling_factor (int): performs a downsampling of the input before computing the statistics. Original
                                       coordinates will be multiplied by 2**(-downsampling_factor)
    
    
        Examples:
            >>> for events in AdaptiveRateEventsIterator("beautiful_record.raw"):
            >>>     assert events.size > 0
            >>>     start_ts = events[0]["t"]
            >>>     end_ts = events[-1]["t"]
            >>>     print("frame: {} -> {}   delta_t: {}   fps: {}   nb_ev: {}".format(start_ts, end_ts,
                                                                                       end_ts - start_ts,
                                                                                       1e6 / (end_ts - start_ts),
                                                                                       events.size))
        
    """
    def __init__(self, input_path, thr_var_per_event = 0.0005, downsampling_factor = 2):
        ...
    def __iter__(self):
        ...
    def __next__(self):
        ...
    def get_size(self):
        ...
