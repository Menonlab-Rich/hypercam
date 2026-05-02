from __future__ import annotations
import metavision_hal
import metavision_sdk_base
import numpy
import os
import typing
__all__: list[str] = ['Camera', 'CameraStreamSlicer', 'FileConfigHints', 'HDF5EventFileWriter', 'IDENTITY', 'MET_AUTOMATIC', 'MET_N_EVENTS', 'MET_N_US', 'MIXED', 'NOT_MET', 'N_EVENTS', 'N_US', 'RAWEvt2EventFileWriter', 'RValueCamera', 'ReslicingConditionStatus', 'ReslicingConditionType', 'Slice', 'SliceCondition', 'SyncedCameraStreamsSlicer', 'SyncedCameraSystemBuilder', 'SyncedCameraSystemFactory', 'SyncedSlice']
class Camera:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def from_file(file_path: os.PathLike, hints: FileConfigHints = ...) -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def from_first_available() -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def from_first_available(config: metavision_hal.DeviceConfig) -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def from_serial(serial: str) -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def from_serial(serial: str, config: metavision_hal.DeviceConfig) -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_device(self) -> metavision_hal.Device:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def height(self) -> int:
        """
        Returns the height of the camera
        """
    def load(self, path: os.PathLike) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def move(self) -> RValueCamera:
        ...
    def save(self, path: os.PathLike) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def width(self) -> int:
        """
        Returns the width of the camera
        """
class CameraStreamSlicer:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self, rvalue_camera: RValueCamera, slice_condition: SliceCondition = ..., max_queue_size: int = 5) -> None:
        ...
    def __iter__(self) -> typing.Iterator:
        ...
    def begin(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def camera(self) -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class FileConfigHints:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get(self, key: str, def: str = '') -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def max_memory(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def max_memory(self, max_memory: int) -> FileConfigHints:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def max_memory(self, max_read_per_op: int) -> FileConfigHints:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def max_read_per_op(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def real_time_playback(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def real_time_playback(self, enabled: bool) -> FileConfigHints:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set(self, key: str, value: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def time_shift(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def time_shift(self, enabled: bool) -> FileConfigHints:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class HDF5EventFileWriter:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self, path: os.PathLike = '', metadata_map: dict[str, str] = {}) -> None:
        ...
    def add_cd_events(self, events: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        Adds an array of EventCD to write to the file
        
        Args:
            events: numpy array of EventCD
        """
    def add_ext_trigger_events(self, events: numpy.ndarray[metavision_sdk_base._EventExtTrigger_decode]) -> None:
        """
        Adds an array of EventExtTrigger to write to the file
        
        Args:
            events: numpy array of EventExtTrigger
        """
    def add_metadata(self, key: str, value: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def add_metadata_map_from_camera(self, camera: Camera) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def close(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def flush(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_open(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def open(self, path: os.PathLike) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class RAWEvt2EventFileWriter:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self, stream_width: int, stream_height: int, path: os.PathLike = ..., enable_trigger_support: bool = False, metadata_map: dict[str, str] = {}, max_events_add_latency: int = 9223372036854775807) -> None:
        ...
    def add_cd_events(self, events: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        Adds an array of EventCD to write to the file
        
        Args:
            events: numpy array of EventCD
        """
    def add_ext_trigger_events(self, events: numpy.ndarray[metavision_sdk_base._EventExtTrigger_decode]) -> None:
        """
        Adds an array of EventExtTrigger to write to the file
        
        Args:
            events: numpy array of EventExtTrigger
        """
    def add_metadata(self, key: str, value: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def close(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def flush(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_open(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def open(self, path: os.PathLike) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class RValueCamera:
    pass
class ReslicingConditionStatus:
    """
    Members:
    
      NOT_MET
    
      MET_AUTOMATIC
    
      MET_N_EVENTS
    
      MET_N_US
    """
    MET_AUTOMATIC: typing.ClassVar[ReslicingConditionStatus]  # value = <ReslicingConditionStatus.MET_AUTOMATIC: 1>
    MET_N_EVENTS: typing.ClassVar[ReslicingConditionStatus]  # value = <ReslicingConditionStatus.MET_N_EVENTS: 2>
    MET_N_US: typing.ClassVar[ReslicingConditionStatus]  # value = <ReslicingConditionStatus.MET_N_US: 3>
    NOT_MET: typing.ClassVar[ReslicingConditionStatus]  # value = <ReslicingConditionStatus.NOT_MET: 0>
    __members__: typing.ClassVar[dict[str, ReslicingConditionStatus]]  # value = {'NOT_MET': <ReslicingConditionStatus.NOT_MET: 0>, 'MET_AUTOMATIC': <ReslicingConditionStatus.MET_AUTOMATIC: 1>, 'MET_N_EVENTS': <ReslicingConditionStatus.MET_N_EVENTS: 2>, 'MET_N_US': <ReslicingConditionStatus.MET_N_US: 3>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class ReslicingConditionType:
    """
    Members:
    
      IDENTITY
    
      N_EVENTS
    
      N_US
    
      MIXED
    """
    IDENTITY: typing.ClassVar[ReslicingConditionType]  # value = <ReslicingConditionType.IDENTITY: 0>
    MIXED: typing.ClassVar[ReslicingConditionType]  # value = <ReslicingConditionType.MIXED: 3>
    N_EVENTS: typing.ClassVar[ReslicingConditionType]  # value = <ReslicingConditionType.N_EVENTS: 1>
    N_US: typing.ClassVar[ReslicingConditionType]  # value = <ReslicingConditionType.N_US: 2>
    __members__: typing.ClassVar[dict[str, ReslicingConditionType]]  # value = {'IDENTITY': <ReslicingConditionType.IDENTITY: 0>, 'N_EVENTS': <ReslicingConditionType.N_EVENTS: 1>, 'N_US': <ReslicingConditionType.N_US: 2>, 'MIXED': <ReslicingConditionType.MIXED: 3>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Slice:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    __hash__: typing.ClassVar[None] = None
    def __eq__(self, other: Slice) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def __init__(self) -> None:
        ...
    @property
    def events(self) -> numpy.ndarray[metavision_sdk_base._EventCD_decode]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def n_events(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def status(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def t(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def triggers(self) -> numpy.ndarray[metavision_sdk_base._EventExtTrigger_decode]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class SliceCondition:
    delta_n_events: int
    delta_ts: int
    type: ReslicingConditionType
    @staticmethod
    def make_identity() -> SliceCondition:
        ...
    @staticmethod
    def make_mixed(delta_ts: int, delta_n_events: int) -> SliceCondition:
        ...
    @staticmethod
    def make_n_events(delta_n_events: int) -> SliceCondition:
        ...
    @staticmethod
    def make_n_us(delta_ts: int) -> SliceCondition:
        ...
    def __init__(self) -> None:
        ...
    def is_tracking_duration(self) -> bool:
        ...
    def is_tracking_events_count(self) -> bool:
        ...
class SyncedCameraStreamsSlicer:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self, camera: RValueCamera, Cameras: list, slice_condition: SliceCondition = ..., max_queue_size: int = 5) -> None:
        ...
    def __iter__(self) -> typing.Iterator:
        ...
    def begin(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def master(self) -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def slave(self, i: int) -> Camera:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def slaves_count(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class SyncedCameraSystemBuilder:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self) -> None:
        ...
    def add_live_camera_parameters(self, serial_number: str, device_config: metavision_hal.DeviceConfig = ..., settings_file_path: os.PathLike | None = None) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def add_record_path(self, record_path: os.PathLike) -> SyncedCameraSystemBuilder:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def build(self) -> tuple[Camera, list[Camera]]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_file_config_hints(self, file_config_hints: FileConfigHints) -> SyncedCameraSystemBuilder:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_record(self, record: bool) -> SyncedCameraSystemBuilder:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_record_dir(self, record_dir: os.PathLike) -> SyncedCameraSystemBuilder:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class SyncedCameraSystemFactory:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class LiveCameraParameters:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
        def __init__(self) -> None:
            ...
        @property
        def device_config(self) -> metavision_hal.DeviceConfig:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @device_config.setter
        def device_config(self, arg0: metavision_hal.DeviceConfig) -> None:
            ...
        @property
        def serial_number(self) -> str:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @serial_number.setter
        def serial_number(self, arg0: str) -> None:
            ...
        @property
        def settings_file_path(self) -> os.PathLike | None:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @settings_file_path.setter
        def settings_file_path(self, arg0: os.PathLike | None) -> None:
            ...
    class LiveParameters:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
        def __init__(self) -> None:
            ...
        @property
        def master_parameters(self) -> SyncedCameraSystemFactory.LiveCameraParameters:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @master_parameters.setter
        def master_parameters(self, arg0: SyncedCameraSystemFactory.LiveCameraParameters) -> None:
            ...
        @property
        def record(self) -> bool:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @record.setter
        def record(self, arg0: bool) -> None:
            ...
        @property
        def record_dir(self) -> os.PathLike | None:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @record_dir.setter
        def record_dir(self, arg0: os.PathLike | None) -> None:
            ...
        @property
        def slave_parameters(self) -> list[SyncedCameraSystemFactory.LiveCameraParameters]:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @slave_parameters.setter
        def slave_parameters(self, arg0: list[SyncedCameraSystemFactory.LiveCameraParameters]) -> None:
            ...
    class OfflineParameters:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
        def __init__(self) -> None:
            ...
        @property
        def file_config_hints(self) -> FileConfigHints:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @file_config_hints.setter
        def file_config_hints(self, arg0: FileConfigHints) -> None:
            ...
        @property
        def master_file_path(self) -> os.PathLike:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @master_file_path.setter
        def master_file_path(self, arg0: os.PathLike) -> None:
            ...
        @property
        def slave_file_paths(self) -> list[os.PathLike]:
            """
            ###########################################
            #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
            ###########################################
            """
        @slave_file_paths.setter
        def slave_file_paths(self, arg0: list[os.PathLike]) -> None:
            ...
    @staticmethod
    @typing.overload
    def build(parameters: ...) -> tuple[Camera, list[Camera]]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def build(parameters: ...) -> tuple[Camera, list[Camera]]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def __init__(self) -> None:
        ...
class SyncedSlice:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    __hash__: typing.ClassVar[None] = None
    def __eq__(self, other: SyncedSlice) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def __init__(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def master_events(self) -> numpy.ndarray[metavision_sdk_base._EventCD_decode]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def master_triggers(self) -> numpy.ndarray[metavision_sdk_base._EventExtTrigger_decode]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def n_events(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def slave_events(self) -> list:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def status(self) -> ReslicingConditionStatus:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def t(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
IDENTITY: ReslicingConditionType  # value = <ReslicingConditionType.IDENTITY: 0>
MET_AUTOMATIC: ReslicingConditionStatus  # value = <ReslicingConditionStatus.MET_AUTOMATIC: 1>
MET_N_EVENTS: ReslicingConditionStatus  # value = <ReslicingConditionStatus.MET_N_EVENTS: 2>
MET_N_US: ReslicingConditionStatus  # value = <ReslicingConditionStatus.MET_N_US: 3>
MIXED: ReslicingConditionType  # value = <ReslicingConditionType.MIXED: 3>
NOT_MET: ReslicingConditionStatus  # value = <ReslicingConditionStatus.NOT_MET: 0>
N_EVENTS: ReslicingConditionType  # value = <ReslicingConditionType.N_EVENTS: 1>
N_US: ReslicingConditionType  # value = <ReslicingConditionType.N_US: 2>
