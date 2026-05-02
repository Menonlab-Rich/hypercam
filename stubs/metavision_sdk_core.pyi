from __future__ import annotations
import metavision_sdk_base
import numpy
import numpy.dtypes
import typing
__all__: list[str] = ['AdaptiveRateEventsSplitterAlgorithm', 'Auxiliary', 'Background', 'BaseFrameGenerationAlgorithm', 'ColorPalette', 'ColorType', 'ContrastMapGenerationAlgorithm', 'CoolWarm', 'Dark', 'EventBbox', 'EventBboxBuffer', 'EventPreprocessor', 'EventRescalerAlgorithm', 'EventTrackedBox', 'EventTrackedBoxBuffer', 'EventsIntegrationAlgorithm', 'FlipXAlgorithm', 'FlipYAlgorithm', 'Gray', 'Light', 'MostRecentTimestampBuffer', 'Negative', 'OnDemandFrameGenerationAlgorithm', 'PeriodicFrameGenerationAlgorithm', 'PolarityFilterAlgorithm', 'PolarityInverterAlgorithm', 'Positive', 'RawEventFrameConverter', 'RoiFilterAlgorithm', 'RoiMaskAlgorithm', 'RollingEventBufferConfig', 'RollingEventBufferMode', 'RollingEventCDBuffer', 'RotateEventsAlgorithm', 'SharedCdEventsBufferProducer', 'StreamLoggerAlgorithm', 'TransposeEventsAlgorithm', 'getColor', 'hsv2rgb', 'rgb2hsv']
class AdaptiveRateEventsSplitterAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, height: int, width: int, thr_var_per_event: float = 0.0005, downsampling_factor: int = 2) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> bool:
        """
        Takes a chunk of events (numpy array of EventCD) and updates the internal state of the EventsSplitter. Returns True if the frame is ready, False otherwise.
        """
    @typing.overload
    def process_events(self, events_buf: metavision_sdk_base.EventCDBuffer) -> bool:
        """
        Takes a chunk of events (EventCDBuffer) and updates the internal state of the EventsSplitter. Returns True if the frame is ready, False otherwise.
        """
    def retrieve_events(self, events_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        Retrieves the events (EventCDBuffer) and reinitializes the state of the EventsSplitter.
        """
class BaseFrameGenerationAlgorithm:
    @staticmethod
    def bg_color_default() -> tuple:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    @typing.overload
    def generate_frame(events: numpy.ndarray[metavision_sdk_base._EventCD_decode], frame: numpy.ndarray, accumulation_time_us: int = 0, palette: ColorPalette = ...) -> None:
        """
        Stand-alone (static) method to generate a frame from events
        
           All events in the interval ]t - dt, t] are used where t the timestamp of the last event in the buffer, and dt is accumulation_time_us. If accumulation_time_us is kept to 0, all input events are used.
           If there is no events, a frame filled with the background color will be generated
        
           :events: Numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory
           :frame: Pre-allocated frame that will be filled with CD events. It must have the same geometry as the input event source, and the color corresponding to the given palette (3 channels by default)
           :accumulation_time_us: Time range of events to update the frame with (in us). 0 to use all events.
           :palette: The Prophesee's color palette to use
        """
    @staticmethod
    @typing.overload
    def generate_frame(events: ..., frame: numpy.ndarray, accumulation_time_us: int = 0, palette: ColorPalette = ...) -> None:
        """
        Stand-alone (static) method to generate a frame from events
        
           All events in the interval ]t - dt, t] are used where t the timestamp of the last event in the buffer, and dt is accumulation_time_us. If accumulation_time_us is kept to 0, all input events are used.
           If there is no events, a frame filled with the background color will be generated
        
           :events: Numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory
           :frame: Pre-allocated frame that will be filled with CD events. It must have the same geometry as the input event source, and the color corresponding to the given palette (3 channels by default)
           :accumulation_time_us: Time range of events to update the frame with (in us). 0 to use all events.
           :palette: The Prophesee's color palette to use
        """
    @staticmethod
    def off_color_default() -> tuple:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def on_color_default() -> tuple:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_dimension(self) -> tuple:
        """
        Gets the frame's dimension, a tuple (height, width, channels)
        """
    def set_color_palette(self, palette: ColorPalette) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_colors(self, background_color: list[int], on_color: list[int], off_color: list[int], colored: bool = True) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class ColorPalette:
    """
    Members:
    
      Light
    
      Dark
    
      CoolWarm
    
      Gray
    """
    CoolWarm: typing.ClassVar[ColorPalette]  # value = <ColorPalette.CoolWarm: 2>
    Dark: typing.ClassVar[ColorPalette]  # value = <ColorPalette.Dark: 1>
    Gray: typing.ClassVar[ColorPalette]  # value = <ColorPalette.Gray: 3>
    Light: typing.ClassVar[ColorPalette]  # value = <ColorPalette.Light: 0>
    __members__: typing.ClassVar[dict[str, ColorPalette]]  # value = {'Light': <ColorPalette.Light: 0>, 'Dark': <ColorPalette.Dark: 1>, 'CoolWarm': <ColorPalette.CoolWarm: 2>, 'Gray': <ColorPalette.Gray: 3>}
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
class ColorType:
    """
    Members:
    
      Background
    
      Positive
    
      Negative
    
      Auxiliary
    """
    Auxiliary: typing.ClassVar[ColorType]  # value = <ColorType.Auxiliary: 3>
    Background: typing.ClassVar[ColorType]  # value = <ColorType.Background: 0>
    Negative: typing.ClassVar[ColorType]  # value = <ColorType.Negative: 2>
    Positive: typing.ClassVar[ColorType]  # value = <ColorType.Positive: 1>
    __members__: typing.ClassVar[dict[str, ColorType]]  # value = {'Background': <ColorType.Background: 0>, 'Positive': <ColorType.Positive: 1>, 'Negative': <ColorType.Negative: 2>, 'Auxiliary': <ColorType.Auxiliary: 3>}
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
class ContrastMapGenerationAlgorithm:
    def __init__(self, width: int, height: int, contrast_on: float = 1.2000000476837158, contrast_off: float = -1.0) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def generate(self, frame: numpy.ndarray) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def generate(self, frame: numpy.ndarray, tonemapping_factor: float, tonemapping_bias: float) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def process_events(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        Processes a buffer of events for later frame generation
        
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory
        """
    def reset(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class EventBboxBuffer:
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
    def _buffer_info(self) -> metavision_sdk_base._BufferInfo:
        ...
    def numpy(self, copy: bool = False) -> numpy.ndarray[...]:
        """
           :copy: if True, allocates new memory and returns a copy of the events. If False, use the same memory
        """
    def resize(self, size: int) -> None:
        """
        resizes the buffer to the specified size
        
           :size: the new size of the buffer
        """
class EventPreprocessor:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def create_DiffProcessor(input_event_width: int, input_event_height: int, max_incr_per_pixel: float = 5, clip_value_after_normalization: float = 1.0, scale_width: float = 1.0, scale_height: float = 1.0) -> EventPreprocessor:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def create_EventCubeProcessor(delta_t: int, input_event_width: int, input_event_height: int, num_utbins: int, split_polarity: bool, max_incr_per_pixel: float = 63.75, clip_value_after_normalization: float = 1.0, scale_width: float = 1.0, scale_height: float = 1.0) -> EventPreprocessor:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def create_HardwareDiffProcessor(input_event_width: int, input_event_height: int, min_val: int, max_val: int, allow_rollover: bool = True) -> EventPreprocessor:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def create_HardwareHistoProcessor(input_event_width: int, input_event_height: int, neg_saturation: int = 255, pos_saturation: int = 255) -> EventPreprocessor:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def create_HistoProcessor(input_event_width: int, input_event_height: int, max_incr_per_pixel: float = 5, clip_value_after_normalization: float = 1.0, use_CHW: bool = True, scale_width: float = 1.0, scale_height: float = 1.0) -> EventPreprocessor:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def create_TimeSurfaceProcessor(input_event_width: int, input_event_height: int, split_polarity: bool = True) -> EventPreprocessor:
        """
                                        Creates a TimeSurfaceProcessor instance.
        
                                            :input_event_width: Width of the input event stream.
                                            :input_event_height: Height of the input event stream.
                                            :split_polarity: (optional) If True, polarities will be managed separately in the
                                                             TimeSurface. Else, a single channel will be used for both
                                                             polarities.
        """
    def get_frame_channels(self) -> int:
        """
        Returns the number of channels of the output frame.
        """
    def get_frame_height(self) -> int:
        """
        Returns the height of the output frame.
        """
    def get_frame_shape(self) -> list[int]:
        """
        Returns the frame shape.
        """
    def get_frame_size(self) -> int:
        """
        Returns the number of values in the output frame.
        """
    def get_frame_width(self) -> int:
        """
        Returns the width of the output frame.
        """
    def init_output_tensor(self) -> numpy.ndarray:
        ...
    def is_CHW(self) -> bool:
        """
        Returns true if the output tensor shape has CHW layout.
        """
    def process_events(self, cur_frame_start_ts: int, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], frame_tensor_np: numpy.ndarray) -> None:
        """
        Takes a chunk of events (numpy array of EventCD) and updates the frame_tensor (numpy array of float)
        """
class EventRescalerAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, scale_width: float, scale_height: float) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input/output.
        This method should only be used when the number of output events is the same as the number of input events
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't') used as input/output. Its content will be overwritten
        """
class EventTrackedBoxBuffer:
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
    def _buffer_info(self) -> metavision_sdk_base._BufferInfo:
        ...
    def numpy(self, copy: bool = False) -> numpy.ndarray[...]:
        """
           :copy: if True, allocates new memory and returns a copy of the events. If False, use the same memory
        """
    def resize(self, size: int) -> None:
        """
        resizes the buffer to the specified size
        
           :size: the new size of the buffer
        """
class EventsIntegrationAlgorithm:
    def __init__(self, width: int, height: int, decay_time: int = 1000000, contrast_on: float = 1.2000000476837158, contrast_off: float = -1.0, tonemapping_max_ev_count: int = 5, gaussian_blur_kernel_radius: int = 1, diffusion_weight: float = 0.0) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def generate(self, frame: numpy.ndarray) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def process_events(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        Processes a buffer of events for later frame generation
        
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory
        """
    def reset(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class FlipXAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    width_minus_one: int
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, width_minus_one: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input/output.
        This method should only be used when the number of output events is the same as the number of input events
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't') used as input/output. Its content will be overwritten
        """
class FlipYAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    height_minus_one: int
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, height_minus_one: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input/output.
        This method should only be used when the number of output events is the same as the number of input events
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't') used as input/output. Its content will be overwritten
        """
class MostRecentTimestampBuffer:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __buffer__(self, flags):
        """
        Return a buffer object that exposes the underlying memory of the object.
        """
    def __init__(self, rows: int, cols: int, channels: int = 1) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def __release_buffer__(self, buffer):
        """
        Release the buffer object that exposes the underlying memory of the object.
        """
    def _buffer_info(self) -> metavision_sdk_base._BufferInfo:
        ...
    def generate_img_time_surface(self, last_ts: int, delta_t: int, out: numpy.ndarray) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def generate_img_time_surface_collapsing_channels(self, last_ts: int, delta_t: int, out: numpy.ndarray) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def max_across_channels_at(self, y: int, x: int) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def numpy(self, copy: bool = False) -> numpy.ndarray[numpy.int64]:
        """
        Converts to a numpy array
        """
    def set_to(self, ts: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def channels(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def cols(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def rows(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class OnDemandFrameGenerationAlgorithm(BaseFrameGenerationAlgorithm):
    def __init__(self, width: int, height: int, accumulation_time_us: int = 10000, palette: ColorPalette = ...) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def generate(self, ts: int, frame: numpy.ndarray) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_accumulation_time_us(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def process_events(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        Processes a buffer of events for later frame generation
        
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory
        """
    def set_accumulation_time_us(self, accumulation_time_us: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class PeriodicFrameGenerationAlgorithm(BaseFrameGenerationAlgorithm):
    def __init__(self, sensor_width: int, sensor_height: int, accumulation_time_us: int = 10000, fps: float = 0.0, palette: ColorPalette = ...) -> None:
        """
        Inherits BaseFrameGenerationAlgorithm. Algorithm that generates frames from events at a fixed rate (fps). The reference clock used is the one of the input events
        
        Args:
            sensor_width (int): Sensor's width (in pixels)
            sensor_height (int): Sensor's height (in pixels)
            accumulation_time_us (timestamp): Accumulation time (in us) (@ref set_accumulation_time_us)
            fps (float): The fps at which to generate the frames. The time reference used is the one from the input events (@ref set_fps) 
            palette (ColorPalette): The Prophesee's color palette to use (@ref set_color_palette)
        @throw std::invalid_argument If the input fps is not positive or if the input accumulation time is not strictly positive
        """
    def force_generate(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_accumulation_time_us(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_fps(self) -> float:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def process_events(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        Processes a buffer of events for later frame generation
        
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory
        """
    def reset(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_accumulation_time_us(self, accumulation_time_us: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_fps(self, fps: float) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_output_callback(self, arg0: typing.Any) -> None:
        """
        Sets a callback to retrieve the frame
        """
    def skip_frames_up_to(self, ts: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class PolarityFilterAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    polarity: int
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, polarity: int = 0) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input/output.
        This should only be used when the number of output events is the same as the number of input events
           :events_buf: Buffer of events used as input/output. Its content will be overwritten. It can be converted to a numpy structured array using .numpy()
        """
class PolarityInverterAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input/output.
        This method should only be used when the number of output events is the same as the number of input events
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't') used as input/output. Its content will be overwritten
        """
class RawEventFrameConverter:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self, height: int, width: int, use_CHW: bool = False) -> None:
        """
        Creates a RawEventFrameConverter
        """
    def convert_diff(self, arg0: metavision_sdk_base.RawEventFrameDiff) -> numpy.ndarray[numpy.int8]:
        """
        Converts a RawEventFrameDiff into a proper diff frame
        """
    def convert_histo(self, arg0: metavision_sdk_base.RawEventFrameHisto) -> numpy.ndarray[numpy.uint8]:
        """
        Converts a RawEventFrameHisto into a proper histo frame
        """
    def set_CHW(self) -> None:
        """
        Set histo output format to CHW
        """
    def set_HWC(self) -> None:
        """
        Set histo output format to HWC
        """
class RoiFilterAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, x0: int, y0: int, x1: int, y1: int, output_relative_coordinates: bool = False) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def is_resetting(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input/output.
        This should only be used when the number of output events is the same as the number of input events
           :events_buf: Buffer of events used as input/output. Its content will be overwritten. It can be converted to a numpy structured array using .numpy()
        """
    @property
    def x0(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @x0.setter
    def x0(self, arg1: int) -> None:
        ...
    @property
    def x1(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @x1.setter
    def x1(self, arg1: int) -> None:
        ...
    @property
    def y0(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @y0.setter
    def y0(self, arg1: int) -> None:
        ...
    @property
    def y1(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @y1.setter
    def y1(self, arg1: int) -> None:
        ...
class RoiMaskAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, pixel_mask: numpy.ndarray[numpy.float64]) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def enable_rectangle(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def max_height(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def max_width(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def pixel_mask(self) -> numpy.ndarray[numpy.float64]:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    def process_events_(self, events_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input/output.
        This should only be used when the number of output events is the same as the number of input events
           :events_buf: Buffer of events used as input/output. Its content will be overwritten. It can be converted to a numpy structured array using .numpy()
        """
    def set_pixel_mask(self, mask: numpy.ndarray[numpy.float64]) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class RollingEventBufferConfig:
    delta_n_events: int
    delta_ts: int
    mode: RollingEventBufferMode
    @staticmethod
    def make_n_events(*args, **kwargs) -> RollingEventBufferConfig:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @staticmethod
    def make_n_us(*args, **kwargs) -> RollingEventBufferConfig:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def __init__(self) -> None:
        ...
class RollingEventBufferMode:
    """
    Members:
    
      N_US
    
      N_EVENTS
    """
    N_EVENTS: typing.ClassVar[RollingEventBufferMode]  # value = <RollingEventBufferMode.N_EVENTS: 1>
    N_US: typing.ClassVar[RollingEventBufferMode]  # value = <RollingEventBufferMode.N_US: 0>
    __members__: typing.ClassVar[dict[str, RollingEventBufferMode]]  # value = {'N_US': <RollingEventBufferMode.N_US: 0>, 'N_EVENTS': <RollingEventBufferMode.N_EVENTS: 1>}
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
class RollingEventCDBuffer:
    def __init__(self, arg0: RollingEventBufferConfig) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def __iter__(self) -> typing.Iterator:
        ...
    def capacity(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def clear(self) -> None:
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
    @typing.overload
    def insert_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        This function inserts events from a numpy array into the rolling buffer based on the current mode (N_US or N_EVENTS)
            :input_np: input chunk of events
        """
    @typing.overload
    def insert_events(self, input_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This function inserts events from an event buffer into the rolling buffer based on the current mode (N_US or N_EVENTS)
            :input_buf: input chunk of events
        """
    def size(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class RotateEventsAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self, width_minus_one: int, height_minus_one: int, rotation: float) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events_(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input/output.
        This method should only be used when the number of output events is the same as the number of input events
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't') used as input/output. Its content will be overwritten
        """
    @typing.overload
    def process_events_(self, events_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input/output.
        This should only be used when the number of output events is the same as the number of input events
           :events_buf: Buffer of events used as input/output. Its content will be overwritten. It can be converted to a numpy structured array using .numpy()
        """
    def set_rotation(self, new_angle: float) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    @property
    def height_minus_one(self) -> int:
        ...
    @height_minus_one.setter
    def height_minus_one(self) -> int:
        ...
    @property
    def width_minus_one(self) -> int:
        ...
    @width_minus_one.setter
    def width_minus_one(self) -> int:
        ...
class SharedCdEventsBufferProducer:
    """
    This class splits incoming events into buffers either by number of events or by time slice (in us)
    
    Incoming events are put in buffer contained in a pool of shared vectors until the buffer is completeThen a python callback specified by the user is called on the buffer of events.
    """
    def __init__(self, callback: typing.Any, event_count: int = 0, time_slice_us: int = 10000, buffers_pool_size: int = 64, buffers_preallocation_size: int = 0) -> None:
        """
        Args:
            callback (function): python callback taking as input an int coding the last timestamp of the buffer
                and a numpy buffer of EventCD.
            event_count (int): number of events in each buffer
            time_slice_us (int): duration of the buffer in us.
            buffers_pool_size (int): Number of shared pointers available in the pool at start. They will be 
                 increased if necessary automatically. Can be left as is in most cases.
            buffers_preallocation_size (int): initialization size of vectors in the memory pool. Here again,
                this can be left alone in most uses.
        """
    def flush(self) -> None:
        """
        Flushes the last buffers when the file is done, producing a last incomplete buffer.
        """
    def get_process_events_callback(self) -> typing.Callable[[metavision_sdk_base._EventCD_decode, metavision_sdk_base._EventCD_decode], None]:
        """
        Returns a callback to be passed to the event_cd decoder from Metavision HAL.
        """
    def get_processing_n_events(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_processing_n_us(self) -> int:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def process_events(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        Processes a buffer of events for later frame generation
        
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory
        """
    def reset(self) -> None:
        """
        Resets the buffer.
        """
    def set_processing_mixed(self, delta_n_events: int, delta_ts: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_processing_n_events(self, delta_n_events: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_processing_n_us(self, delta_ts: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class StreamLoggerAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __init__(self, filename: str, width: int, height: int) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def change_destination(self, filename: ..., reset_ts: bool = True) -> None:
        ...
    def close(self) -> None:
        ...
    def enable(self, state: bool, reset_ts: bool = True, split_time_seconds: int = -1) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_native_process_cd_events_callback(self) -> typing.Callable[[metavision_sdk_base._EventCD_decode, metavision_sdk_base._EventCD_decode], None]:
        """
        Returns a callback to be passed to the event_cd decoder from Metavision HAL.
        """
    def get_native_process_ext_trigger_events_callback(self) -> typing.Callable[[metavision_sdk_base._EventExtTrigger_decode, metavision_sdk_base._EventExtTrigger_decode], None]:
        """
        Returns a callback to be passed to the event_ext_trigger decoder from Metavision HAL.
        """
    def get_split_time_seconds(self) -> int:
        ...
    def is_enable(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def process_events(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], ts: int) -> None:
        """
        Processes a buffer of events for later frame generation
        
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory   :ts: array of events' timestamp
        """
class TransposeEventsAlgorithm:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def get_empty_output_buffer() -> metavision_sdk_base.EventCDBuffer:
        """
        This function returns an empty buffer of events of the correct type, which can later on be used as output_buf when calling `process_events()`
        """
    def __init__(self) -> None:
        ...
    @typing.overload
    def process_events(self, input_np: numpy.ndarray[metavision_sdk_base._EventCD_decode], output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input and writes the results into the specified output event buffer
           :input_np: input chunk of events (numpy structured array whose fields are ('x', 'y', 'p', 't'). Note that this order is mandatory)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events(self, input_buf: metavision_sdk_base.EventCDBuffer, output_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input and writes the results into a distinct output event buffer
           :input_buf: input chunk of events (event buffer)
           :output_buf: output buffer of events. It can be converted to a numpy structured array using .numpy()
        """
    @typing.overload
    def process_events_(self, events_np: numpy.ndarray[metavision_sdk_base._EventCD_decode]) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes a numpy array as input/output.
        This method should only be used when the number of output events is the same as the number of input events
           :events_np: numpy structured array of events whose fields are ('x', 'y', 'p', 't') used as input/output. Its content will be overwritten
        """
    @typing.overload
    def process_events_(self, events_buf: metavision_sdk_base.EventCDBuffer) -> None:
        """
        This method is used to apply the current algorithm on a chunk of events. It takes an event buffer as input/output.
        This should only be used when the number of output events is the same as the number of input events
           :events_buf: Buffer of events used as input/output. Its content will be overwritten. It can be converted to a numpy structured array using .numpy()
        """
def getColor(palette: ColorPalette, type: ColorType) -> tuple:
    ...
def hsv2rgb(h: float, s: float, v: float) -> tuple:
    ...
def rgb2hsv(r: float, g: float, b: float) -> tuple:
    ...
Auxiliary: ColorType  # value = <ColorType.Auxiliary: 3>
Background: ColorType  # value = <ColorType.Background: 0>
CoolWarm: ColorPalette  # value = <ColorPalette.CoolWarm: 2>
Dark: ColorPalette  # value = <ColorPalette.Dark: 1>
EventBbox: numpy.dtypes.VoidDType  # value = dtype({'names': ['t', 'x', 'y', 'w', 'h', 'class_id', 'track_id', 'class_confidence'], 'formats': ['<i8', '<f4', '<f4', '<f4', '<f4', '<u4', '<u4', '<f4'], 'offsets': [0, 8, 12, 16, 20, 24, 28, 32], 'itemsize': 40})
EventTrackedBox: numpy.dtypes.VoidDType  # value = dtype({'names': ['t', 'x', 'y', 'w', 'h', 'class_id', 'track_id', 'class_confidence', 'tracking_confidence', 'last_detection_update_time', 'nb_detections'], 'formats': ['<i8', '<f4', '<f4', '<f4', '<f4', '<u4', '<i4', '<f4', '<f4', '<i8', '<i4'], 'offsets': [0, 8, 12, 16, 20, 24, 28, 32, 36, 40, 48], 'itemsize': 56})
Gray: ColorPalette  # value = <ColorPalette.Gray: 3>
Light: ColorPalette  # value = <ColorPalette.Light: 0>
Negative: ColorType  # value = <ColorType.Negative: 2>
Positive: ColorType  # value = <ColorType.Positive: 1>
