"""
Python bindings for the Metavision RawCutter class
"""
from __future__ import annotations
__all__: list[str] = ['RawCutter']
class RawCutter:
    def __init__(self) -> None:
        ...
    def cut_file(self, file: str, start_us: int, end_us: int) -> bool:
        """
        Cut the raw file between start_us and end_us (in microseconds).
        """
    def set_events_to_read(self, n_events: int) -> None:
        """
        Set the number of events to read per buffer.
        """
    def set_output_file_path(self, path: str) -> None:
        """
        Explicitly set the output raw file path.
        """
