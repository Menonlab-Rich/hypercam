"""

Function to visualize events
"""
from __future__ import annotations
from numba.core.decorators import jit
import numpy as np
import numpy
__all__: list[str] = ['BG_COLOR', 'NEG_COLOR', 'POS_COLOR', 'jit', 'np', 'viz_events']
def _viz_events(*args, **kwargs):
    ...
def viz_events(events, height, width, img = None):
    """
    Creates a RGB frame representing the events given as input.
        Args:
            events (np.ndarray): structured array containing events
            height (int): Height of the sensor in pixels
            width (int): width of the sensor in pixels
            img (np.ndarray): optional image of size (height, width, 3) and dtype unint8 to avoid reallocation
        Returns:
            output_array (np.ndarray): Array of shape (height, width, 3)
        
    """
BG_COLOR: numpy.ndarray  # value = array([30, 37, 52], dtype=uint8)
NEG_COLOR: numpy.ndarray  # value = array([ 64, 126, 201], dtype=uint8)
POS_COLOR: numpy.ndarray  # value = array([216, 223, 236], dtype=uint8)
