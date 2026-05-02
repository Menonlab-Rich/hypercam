from __future__ import annotations
import metavision_sdk_base
import os
import typing
__all__: list[str] = ['CameraDescription', 'ConnectionType', 'Deprecated', 'Device', 'DeviceConfig', 'DeviceConfigOption', 'DeviceDiscovery', 'I_AntiFlickerModule', 'I_CameraSynchronization', 'I_Decoder', 'I_DigitalCrop', 'I_DigitalEventMask', 'I_ErcModule', 'I_EventDecoder_EventCD', 'I_EventDecoder_EventExtTrigger', 'I_EventFrameDecoder_RawEventFrameDiff', 'I_EventFrameDecoder_RawEventFrameHisto', 'I_EventRateActivityFilterModule', 'I_EventTrailFilterModule', 'I_EventsStream', 'I_Geometry', 'I_HALSoftwareInfo', 'I_HW_Identification', 'I_HW_Register', 'I_LL_Biases', 'I_Monitoring', 'I_PixelMask', 'I_PluginSoftwareInfo', 'I_ROI', 'I_RoiPixelMask', 'I_TriggerIn', 'I_TriggerOut', 'LL_Bias_Info', 'PluginCameraDescription', 'RawBuffer', 'RawFileConfig', 'RawFileHeader', 'SensorInfo', 'get_hal_software_info']
class CameraDescription(PluginCameraDescription):
    @property
    def integrator_name(self) -> str:
        ...
    @property
    def plugin_name(self) -> str:
        ...
class ConnectionType:
    """
    Members:
    
      MIPI_LINK
    
      USB_LINK
    
      NETWORK_LINK
    
      PROPRIETARY_LINK
    """
    MIPI_LINK: typing.ClassVar[ConnectionType]  # value = <ConnectionType.MIPI_LINK: 1>
    NETWORK_LINK: typing.ClassVar[ConnectionType]  # value = <ConnectionType.NETWORK_LINK: 3>
    PROPRIETARY_LINK: typing.ClassVar[ConnectionType]  # value = <ConnectionType.PROPRIETARY_LINK: 4>
    USB_LINK: typing.ClassVar[ConnectionType]  # value = <ConnectionType.USB_LINK: 2>
    __members__: typing.ClassVar[dict[str, ConnectionType]]  # value = {'MIPI_LINK': <ConnectionType.MIPI_LINK: 1>, 'USB_LINK': <ConnectionType.USB_LINK: 2>, 'NETWORK_LINK': <ConnectionType.NETWORK_LINK: 3>, 'PROPRIETARY_LINK': <ConnectionType.PROPRIETARY_LINK: 4>}
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
class Deprecated(Exception):
    pass
class Device:
    def get_i_antiflicker_module(self) -> I_AntiFlickerModule:
        ...
    def get_i_camera_synchronization(self) -> I_CameraSynchronization:
        ...
    def get_i_digital_crop(self) -> I_DigitalCrop:
        ...
    def get_i_digital_event_mask(self) -> I_DigitalEventMask:
        ...
    def get_i_erc_module(self) -> I_ErcModule:
        ...
    def get_i_event_cd_decoder(self) -> I_EventDecoder_EventCD:
        ...
    def get_i_event_ext_trigger_decoder(self) -> I_EventDecoder_EventExtTrigger:
        ...
    def get_i_event_frame_diff_decoder(self) -> I_EventFrameDecoder_RawEventFrameDiff:
        ...
    def get_i_event_frame_histo_decoder(self) -> I_EventFrameDecoder_RawEventFrameHisto:
        ...
    def get_i_event_rate(self) -> I_EventRateActivityFilterModule:
        ...
    def get_i_event_trail_filter_module(self) -> I_EventTrailFilterModule:
        ...
    def get_i_events_stream(self) -> I_EventsStream:
        ...
    def get_i_events_stream_decoder(self) -> I_Decoder:
        ...
    def get_i_geometry(self) -> I_Geometry:
        ...
    def get_i_hal_software_info(self) -> I_HALSoftwareInfo:
        ...
    def get_i_hw_identification(self) -> I_HW_Identification:
        ...
    def get_i_hw_register(self) -> I_HW_Register:
        ...
    def get_i_ll_biases(self) -> I_LL_Biases:
        ...
    def get_i_monitoring(self) -> I_Monitoring:
        ...
    def get_i_plugin_software_info(self) -> I_PluginSoftwareInfo:
        ...
    def get_i_roi(self) -> I_ROI:
        ...
    def get_i_roi_pixel_mask(self) -> I_RoiPixelMask:
        ...
    def get_i_trigger_in(self) -> I_TriggerIn:
        ...
    def get_i_trigger_out(self) -> I_TriggerOut:
        ...
class DeviceConfig:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_biases_range_check_bypass_key() -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def get_format_key() -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def __init__(self) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: DeviceConfig) -> None:
        ...
    def biases_range_check_bypass(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def enable_biases_range_check_bypass(self, enabled: bool) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def format(self) -> str:
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
    def get_bool(self, key: str, def: bool = True) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_double(self, key: str, def: float = 0.0) -> float:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_int(self, key: str, def: int = 0) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def set(self, key: str, value: bool) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def set(self, key: str, value: str) -> None:
        """
        Sets a value for a named key in the config dictionary This is an overloaded member function, provided for convenience. It differs from the above function only in what argument(s) it accepts.
        """
    @typing.overload
    def set(self, key: str, value: int) -> None:
        """
        Sets a value for a named key in the config dictionary This is an overloaded member function, provided for convenience. It differs from the above function only in what argument(s) it accepts.
        """
    @typing.overload
    def set(self, key: str, value: float) -> None:
        """
        Sets a value for a named key in the config dictionary This is an overloaded member function, provided for convenience. It differs from the above function only in what argument(s) it accepts.
        """
    def set_format(self, format: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class DeviceConfigOption:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class Type:
        """
        Members:
        
          INVALID
        
          BOOLEAN
        
          INT
        
          DOUBLE
        
          STRING
        """
        BOOLEAN: typing.ClassVar[DeviceConfigOption.Type]  # value = <Type.BOOLEAN: 1>
        DOUBLE: typing.ClassVar[DeviceConfigOption.Type]  # value = <Type.DOUBLE: 3>
        INT: typing.ClassVar[DeviceConfigOption.Type]  # value = <Type.INT: 2>
        INVALID: typing.ClassVar[DeviceConfigOption.Type]  # value = <Type.INVALID: 0>
        STRING: typing.ClassVar[DeviceConfigOption.Type]  # value = <Type.STRING: 4>
        __members__: typing.ClassVar[dict[str, DeviceConfigOption.Type]]  # value = {'INVALID': <Type.INVALID: 0>, 'BOOLEAN': <Type.BOOLEAN: 1>, 'INT': <Type.INT: 2>, 'DOUBLE': <Type.DOUBLE: 3>, 'STRING': <Type.STRING: 4>}
        def __eq__(self, other: typing.Any) -> bool:
            ...
        def __ge__(self, other: typing.Any) -> bool:
            ...
        def __getstate__(self) -> int:
            ...
        def __gt__(self, other: typing.Any) -> bool:
            ...
        def __hash__(self) -> int:
            ...
        def __index__(self) -> int:
            ...
        def __init__(self, value: int) -> None:
            ...
        def __int__(self) -> int:
            ...
        def __le__(self, other: typing.Any) -> bool:
            ...
        def __lt__(self, other: typing.Any) -> bool:
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
    @typing.overload
    def __init__(self) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: bool) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: int, arg1: int, arg2: int) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: float, arg1: float, arg2: float) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: list[str], arg1: str) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: DeviceConfigOption) -> None:
        ...
    def get_default_value(self) -> typing.Any:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_range(self) -> typing.Any:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_values(self) -> list[str]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def type(self) -> DeviceConfigOption.Type:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class DeviceDiscovery:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def list() -> list[str]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def list_available_sources() -> list[...]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def list_available_sources_local() -> list[...]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def list_available_sources_remote() -> list[...]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def list_device_config_options(serial: str) -> dict[str, ...]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def list_local() -> list[str]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def list_remote() -> list[str]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def open(serial: str) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def open(serial: str, config: ...) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def open_raw_file(raw_file: os.PathLike) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def open_raw_file(raw_file: os.PathLike, file_config: ...) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_AntiFlickerModule:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class AntiFlickerMode:
        """
        Members:
        
          BandStop
        
          BandPass
        """
        BandPass: typing.ClassVar[I_AntiFlickerModule.AntiFlickerMode]  # value = <AntiFlickerMode.BandPass: 0>
        BandStop: typing.ClassVar[I_AntiFlickerModule.AntiFlickerMode]  # value = <AntiFlickerMode.BandStop: 1>
        __members__: typing.ClassVar[dict[str, I_AntiFlickerModule.AntiFlickerMode]]  # value = {'BandStop': <AntiFlickerMode.BandStop: 1>, 'BandPass': <AntiFlickerMode.BandPass: 0>}
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
    def enable(self, b: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_band_high_frequency(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_band_low_frequency(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_duty_cycle(self) -> float:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_filtering_mode(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_frequency_band(self) -> tuple[int, int]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_duty_cycle(self) -> float:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_frequency(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_start_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_stop_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_duty_cycle(self) -> float:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_frequency(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_start_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_stop_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_start_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_stop_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_enabled(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_duty_cycle(self, percent_activity: float) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_filtering_mode(self, arg0: ...) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_frequency_band(self, min_freq: int, max_freq: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_start_threshold(self, threshold: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_stop_threshold(self, threshold: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_CameraSynchronization:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_mode(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_mode_master(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_mode_slave(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_mode_standalone(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_Decoder:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def add_time_callback(self, cb: typing.Any) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def decode(self, arg0: typing.Any) -> None:
        """
        Decodes raw data. Identifies the events in the buffer and dispatches it to the instance Event Decoder corresponding to each event type
        
        Args:
            RawData: Numpy array of Events
        """
    @typing.overload
    def decode(self, RawData: ..., std: ...) -> None:
        """
        Decodes raw data. Identifies the events in the buffer and dispatches it to the instance Event Decoder corresponding to each event type
        
        Args:
            RawData: Array of events
        """
    def get_last_timestamp(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def remove_callback(self, callback_id: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_DigitalCrop:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def enable(self, arg0: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_window_region(self) -> tuple[int, int, int, int]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_enabled(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_window_region(self, arg0: tuple[int, int, int, int], arg1: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_DigitalEventMask:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_pixel_masks(self) -> list[...]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_ErcModule:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def enable(self, b: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def erc_from_file(self, arg0: str) -> None:
        ...
    def get_cd_event_count(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_cd_event_rate(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_count_period(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_cd_event_count(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_cd_event_rate(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_cd_event_count(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_cd_event_rate(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_enabled(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_cd_event_count(self, event_count: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_cd_event_rate(self, events_per_sec: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_EventDecoder_EventCD:
    def add_event_buffer_callback(self, arg0: typing.Any) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def add_event_buffer_native_callback(self, arg0: typing.Callable[[metavision_sdk_base._EventCD_decode, metavision_sdk_base._EventCD_decode], None]) -> int:
        """
        const Metavision::EventCD * end)`.
        """
    def add_event_buffer_nocopy_callback(self, arg0: typing.Any) -> int:
        ...
    def remove_callback(self, arg0: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_EventDecoder_EventExtTrigger:
    def add_event_buffer_callback(self, arg0: typing.Any) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def add_event_buffer_native_callback(self, arg0: typing.Callable[[metavision_sdk_base._EventExtTrigger_decode, metavision_sdk_base._EventExtTrigger_decode], None]) -> int:
        """
        const Metavision::EventExtTrigger * end)`.
        """
    def remove_callback(self, arg0: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_EventFrameDecoder_RawEventFrameDiff:
    def add_event_frame_callback(self, arg0: typing.Any) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def decode(self, RawData: typing.Any) -> None:
        """
        Decodes raw data. Identifies the events in the buffer and dispatches it to the instance Event Decoder corresponding to each event type
        
        Args:
            RawData: Numpy array of Event Frames
        """
    def get_height(self) -> int:
        """
        get height
        """
    def get_width(self) -> int:
        """
        get width
        """
    def remove_callback(self, arg0: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_EventFrameDecoder_RawEventFrameHisto:
    def add_event_frame_callback(self, arg0: typing.Any) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def decode(self, RawData: typing.Any) -> None:
        """
        Decodes raw data. Identifies the events in the buffer and dispatches it to the instance Event Decoder corresponding to each event type
        
        Args:
            RawData: Numpy array of Event Frames
        """
    def get_height(self) -> int:
        """
        get height
        """
    def get_width(self) -> int:
        """
        get width
        """
    def remove_callback(self, arg0: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_EventRateActivityFilterModule:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class thresholds:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
        lower_bound_start: int
        lower_bound_stop: int
        upper_bound_start: int
        upper_bound_stop: int
    def enable(self, enable_filter: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_thresholds(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_thresholds(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_thresholds(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_enabled(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_thresholds_supported(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_thresholds(self, threshold_ev_s: ...) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_EventTrailFilterModule:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class Type:
        """
        Members:
        
          TRAIL
        
          STC_CUT_TRAIL
        
          STC_KEEP_TRAIL
        """
        STC_CUT_TRAIL: typing.ClassVar[I_EventTrailFilterModule.Type]  # value = <Type.STC_CUT_TRAIL: 1>
        STC_KEEP_TRAIL: typing.ClassVar[I_EventTrailFilterModule.Type]  # value = <Type.STC_KEEP_TRAIL: 2>
        TRAIL: typing.ClassVar[I_EventTrailFilterModule.Type]  # value = <Type.TRAIL: 0>
        __members__: typing.ClassVar[dict[str, I_EventTrailFilterModule.Type]]  # value = {'TRAIL': <Type.TRAIL: 0>, 'STC_CUT_TRAIL': <Type.STC_CUT_TRAIL: 1>, 'STC_KEEP_TRAIL': <Type.STC_KEEP_TRAIL: 2>}
        def __eq__(self, other: typing.Any) -> bool:
            ...
        def __ge__(self, other: typing.Any) -> bool:
            ...
        def __getstate__(self) -> int:
            ...
        def __gt__(self, other: typing.Any) -> bool:
            ...
        def __hash__(self) -> int:
            ...
        def __index__(self) -> int:
            ...
        def __init__(self, value: int) -> None:
            ...
        def __int__(self) -> int:
            ...
        def __le__(self, other: typing.Any) -> bool:
            ...
        def __lt__(self, other: typing.Any) -> bool:
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
    def enable(self, state: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_available_types(self) -> set[I_EventTrailFilterModule.Type]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_min_supported_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_threshold(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_type(self) -> I_EventTrailFilterModule.Type:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_enabled(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_threshold(self, threshold: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_type(self, type: I_EventTrailFilterModule.Type) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_EventsStream:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_latest_raw_data(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def log_raw_data(self, f: str) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def poll_buffer(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def start(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def stop(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def stop_log_raw_data(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def wait_next_buffer(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_Geometry:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_height(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_width(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_HALSoftwareInfo:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_software_info(self) -> metavision_sdk_base.SoftwareInfo:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_HW_Identification:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_available_data_encoding_formats(self) -> list[str]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_connection_type(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_current_data_encoding_format(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_device_config_options(self) -> dict[str, ...]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_header(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_integrator(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_sensor_info(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_serial(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_system_info(self) -> dict:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_HW_Register:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @typing.overload
    def read_register(self, address: int) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def read_register(self, address: str) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def read_register(self, address: str, bitfield: str) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def write_register(self, address: int, v: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def write_register(self, address: str, v: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def write_register(self, address: str, bitfield: str, v: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_LL_Biases:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get(self, bias_name: str) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_all_biases(self) -> dict:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_bias_info(self, bias_name: str) -> ...:
        """
        Gets bias metadata.
        
            :bias_name: Name of the bias whose metadata to get
        
            :return: Metadata of the bias
        """
    def set(self, bias_name: str, bias_value: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_Monitoring:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_illumination(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_pixel_dead_time(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_temperature(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_PixelMask:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_mask(self) -> tuple[int, int, bool]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_mask(self, arg0: int, arg1: int, arg2: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_PluginSoftwareInfo:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_plugin_integrator_name(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_plugin_name(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_software_info(self) -> metavision_sdk_base.SoftwareInfo:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_ROI:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class Mode:
        """
        Members:
        
          ROI
        
          RONI
        """
        ROI: typing.ClassVar[I_ROI.Mode]  # value = <Mode.ROI: 0>
        RONI: typing.ClassVar[I_ROI.Mode]  # value = <Mode.RONI: 1>
        __members__: typing.ClassVar[dict[str, I_ROI.Mode]]  # value = {'ROI': <Mode.ROI: 0>, 'RONI': <Mode.RONI: 1>}
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
    class Window:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
        height: int
        width: int
        x: int
        y: int
        @typing.overload
        def __init__(self, arg0: I_ROI.Window) -> None:
            ...
        @typing.overload
        def __init__(self, arg0: int, arg1: int, arg2: int, arg3: int) -> None:
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
    def enable(self, enable: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_max_supported_windows_count(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_lines(self, cols: list, rows: list) -> None:
        ...
    def set_mode(self, mode: ...) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_window(self, roi: ...) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_windows(self, roi_list: list) -> None:
        ...
class I_RoiPixelMask:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def apply_pixels(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_pixel(self, arg0: int, arg1: int, arg2: bool) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_TriggerIn:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class Channel:
        """
        Members:
        
          MAIN
        
          AUX
        
          LOOPBACK
        """
        AUX: typing.ClassVar[I_TriggerIn.Channel]  # value = <Channel.AUX: 1>
        LOOPBACK: typing.ClassVar[I_TriggerIn.Channel]  # value = <Channel.LOOPBACK: 2>
        MAIN: typing.ClassVar[I_TriggerIn.Channel]  # value = <Channel.MAIN: 0>
        __members__: typing.ClassVar[dict[str, I_TriggerIn.Channel]]  # value = {'MAIN': <Channel.MAIN: 0>, 'AUX': <Channel.AUX: 1>, 'LOOPBACK': <Channel.LOOPBACK: 2>}
        def __eq__(self, other: typing.Any) -> bool:
            ...
        def __ge__(self, other: typing.Any) -> bool:
            ...
        def __getstate__(self) -> int:
            ...
        def __gt__(self, other: typing.Any) -> bool:
            ...
        def __hash__(self) -> int:
            ...
        def __index__(self) -> int:
            ...
        def __init__(self, value: int) -> None:
            ...
        def __int__(self) -> int:
            ...
        def __le__(self, other: typing.Any) -> bool:
            ...
        def __lt__(self, other: typing.Any) -> bool:
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
    def disable(self, channel: I_TriggerIn.Channel) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def enable(self, channel: I_TriggerIn.Channel) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_available_channels(self) -> dict[I_TriggerIn.Channel, int]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_enabled(self, channel: I_TriggerIn.Channel) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class I_TriggerOut:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def disable(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def enable(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_duty_cycle(self, period_ratio: float) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_period(self, period_us: int) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class LL_Bias_Info:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def get_bias_allowed_range(self) -> tuple[int, int]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_bias_range(self) -> tuple[int, int]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_bias_recommended_range(self) -> tuple[int, int]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_category(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_description(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_modifiable(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class PluginCameraDescription:
    @property
    def connection(self) -> ConnectionType:
        ...
    @property
    def serial(self) -> str:
        ...
class RawBuffer:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def size(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class RawFileConfig:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @typing.overload
    def __init__(self) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: RawFileConfig) -> None:
        ...
    @property
    def build_index(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @build_index.setter
    def build_index(self, arg0: bool) -> None:
        ...
    @property
    def do_time_shifting(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @do_time_shifting.setter
    def do_time_shifting(self, arg0: bool) -> None:
        ...
    @property
    def n_events_to_read(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @n_events_to_read.setter
    def n_events_to_read(self, arg0: int) -> None:
        ...
    @property
    def n_read_buffers(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @n_read_buffers.setter
    def n_read_buffers(self, arg0: int) -> None:
        ...
class RawFileHeader(metavision_sdk_base.GenericHeader):
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @typing.overload
    def __init__(self) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: RawFileHeader) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: dict) -> None:
        """
        Args:
            dict (dictionary): a python dictionary holding key value pairs of string types.
        """
    def get_camera_integrator_name(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_plugin_integrator_name(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_plugin_name(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_camera_integrator_name(self, integrator_name: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_plugin_integrator_name(self, integrator_name: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_plugin_name(self, plugin_name: str) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class SensorInfo:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @property
    def major_version(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def minor_version(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def name(self) -> str:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
def get_hal_software_info() -> metavision_sdk_base.SoftwareInfo:
    ...
