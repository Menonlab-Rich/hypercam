"""
Spatio-Temporal Contrast Filter for Event-based data
"""
from __future__ import annotations
import numpy
import typing
__all__: list[str] = ['SpatioTemporalContrastAlgorithm']
class SpatioTemporalContrastAlgorithm:
    cut_trail: bool
    inverse: bool
    threshold: int
    @staticmethod
    def get_empty_output_buffer() -> ...:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, width: int, height: int, threshold: int, cut_trail: bool = True, inverse: bool = False) -> None:
        ...
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[...], output_buf: ...) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: ..., output_buf: ...) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_np: numpy.ndarray[...]) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input/output.
        This method should only be used when the number of output events is the same as the number of input events
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't') used as input/output. Its content will be overwritten
        """
