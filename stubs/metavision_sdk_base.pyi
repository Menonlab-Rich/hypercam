from __future__ import annotations
import numpy
import numpy.dtypes
import typing
__all__: list[str] = ['EventCD', 'EventCDBuffer', 'EventExtTrigger', 'EventExtTriggerBuffer', 'GenericHeader', 'RawEventFrameDiff', 'RawEventFrameHisto', 'SoftwareInfo']
class EventCDBuffer:
    def __buffer__(self, flags):
        """
        Return a buffer object that exposes the underlying memory of the object.
        """
    def __init__(self, size: int = 0) -> None:
        """
        Constructor
        """
    def __release_buffer__(self, buffer):
        """
        Release the buffer object that exposes the underlying memory of the object.
        """
    def _buffer_info(self) -> buffer_info:
        ...
    def numpy(self, copy: bool = False) -> numpy.ndarray[_EventCD_decode]:
        """
           :copy: if True, allocates new memory and returns a copy of the events. If False, use the same memory
        """
    def resize(self, size: int) -> None:
        """
        resizes the buffer to the specified size
        
           :size: the new size of the buffer
        """
class EventExtTriggerBuffer:
    def __buffer__(self, flags):
        """
        Return a buffer object that exposes the underlying memory of the object.
        """
    def __init__(self, size: int = 0) -> None:
        """
        Constructor
        """
    def __release_buffer__(self, buffer):
        """
        Release the buffer object that exposes the underlying memory of the object.
        """
    def _buffer_info(self) -> buffer_info:
        ...
    def numpy(self, copy: bool = False) -> numpy.ndarray[_EventExtTrigger_decode]:
        """
           :copy: if True, allocates new memory and returns a copy of the events. If False, use the same memory
        """
    def resize(self, size: int) -> None:
        """
        resizes the buffer to the specified size
        
           :size: the new size of the buffer
        """
class GenericHeader:
    @typing.overload
    def __init__(self) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: dict) -> None:
        """
        Args:
         dict (dictionary): a python dictionary holding key value pairs of string types.
        """
    @typing.overload
    def __init__(self, arg0: str) -> None:
        """
        Args:
         filename (str): name of the file to open
        """
    def add_date(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def empty(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_date(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_field(self, key: str) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_header_map(self) -> dict[str, str]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def remove_date(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def remove_field(self, key: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_field(self, key: str, value: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def to_string(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class RawEventFrameDiff:
    def __init__(self, height: int, width: int) -> None:
        ...
    def buffer_size(self) -> int:
        ...
    def numpy(self) -> numpy.ndarray[numpy.int8]:
        """
        Converts to a numpy array
        """
class RawEventFrameHisto:
    def __init__(self, height: int, width: int) -> None:
        ...
    def buffer_size(self) -> int:
        ...
class SoftwareInfo:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self, version_major: int, version_minor: int, version_patch: int, version_suffix_string: str, vcs_branch: str, vcs_commit: str, vcs_date: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_vcs_branch(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_vcs_commit(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_vcs_date(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_version(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_version_major(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_version_minor(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_version_patch(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_version_suffix(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class _BufferInfo:
    format: str
    itemsize: int
    ndim: int
    shape: list[int]
    size: int
    strides: list[int]
    def __init__(self) -> None:
        ...
    def ptr(self) -> int:
        ...
    def ptr_hex(self) -> str:
        ...
    def to_dict(self) -> dict:
        ...
class _EventCD_decode:
    def __init__(self, arg0: int, arg1: int, arg2: int, arg3: int) -> None:
        ...
class _EventExtTrigger_decode:
    def __init__(self, arg0: int, arg1: int, arg2: int) -> None:
        ...
def _buffer_info(arg0: numpy.ndarray) -> _BufferInfo:
    ...
EventCD: numpy.dtypes.VoidDType  # value = dtype({'names': ['x', 'y', 'p', 't'], 'formats': ['<u2', '<u2', '<i2', '<i8'], 'offsets': [0, 2, 4, 8], 'itemsize': 16})
EventExtTrigger: numpy.dtypes.VoidDType  # value = dtype({'names': ['p', 't', 'id'], 'formats': ['<i2', '<i8', '<i2'], 'offsets': [0, 8, 16], 'itemsize': 24})
