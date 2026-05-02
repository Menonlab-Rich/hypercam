"""

cpu + cuda kernels for gpu simulation of cutoff
"""
from __future__ import annotations
import math as math
from numba.core.decorators import njit
from numba import cuda
__all__: list[str] = ['cuda', 'math', 'njit']
def _cpu_kernel_dynamic_moving_average(*args, **kwargs):
    """
    
        Dynamic Blurring of sequence + Log-space conversion
        (CPU code)
        
    """
def _cuda_kernel_dynamic_moving_average(*args, **kwargs):
    """
    
        Dynamic Blurring of sequence + Log-space conversion
        (GPU code)
        
    """
