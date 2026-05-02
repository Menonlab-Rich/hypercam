from __future__ import annotations
import numpy
import typing
__all__: list[str] = ['BaseWindow', 'EventLoop', 'KEY_0', 'KEY_1', 'KEY_2', 'KEY_3', 'KEY_4', 'KEY_5', 'KEY_6', 'KEY_7', 'KEY_8', 'KEY_9', 'KEY_A', 'KEY_APOSTROPHE', 'KEY_B', 'KEY_BACKSLASH', 'KEY_BACKSPACE', 'KEY_C', 'KEY_CAPS_LOCK', 'KEY_COMMA', 'KEY_D', 'KEY_DELETE', 'KEY_DOWN', 'KEY_E', 'KEY_END', 'KEY_ENTER', 'KEY_EQUAL', 'KEY_ESCAPE', 'KEY_F', 'KEY_F1', 'KEY_F10', 'KEY_F11', 'KEY_F12', 'KEY_F13', 'KEY_F14', 'KEY_F15', 'KEY_F16', 'KEY_F17', 'KEY_F18', 'KEY_F19', 'KEY_F2', 'KEY_F20', 'KEY_F21', 'KEY_F22', 'KEY_F23', 'KEY_F24', 'KEY_F25', 'KEY_F3', 'KEY_F4', 'KEY_F5', 'KEY_F6', 'KEY_F7', 'KEY_F8', 'KEY_F9', 'KEY_G', 'KEY_GRAVE_ACCENT', 'KEY_H', 'KEY_HOME', 'KEY_I', 'KEY_INSERT', 'KEY_J', 'KEY_K', 'KEY_KP_0', 'KEY_KP_1', 'KEY_KP_2', 'KEY_KP_3', 'KEY_KP_4', 'KEY_KP_5', 'KEY_KP_6', 'KEY_KP_7', 'KEY_KP_8', 'KEY_KP_9', 'KEY_KP_ADD', 'KEY_KP_DECIMAL', 'KEY_KP_DIVIDE', 'KEY_KP_ENTER', 'KEY_KP_EQUAL', 'KEY_KP_MULTIPLY', 'KEY_KP_SUBTRACT', 'KEY_L', 'KEY_LAST', 'KEY_LEFT', 'KEY_LEFT_ALT', 'KEY_LEFT_BRACKET', 'KEY_LEFT_CONTROL', 'KEY_LEFT_SHIFT', 'KEY_LEFT_SUPER', 'KEY_M', 'KEY_MENU', 'KEY_MINUS', 'KEY_N', 'KEY_NUM_LOCK', 'KEY_O', 'KEY_P', 'KEY_PAGE_DOWN', 'KEY_PAGE_UP', 'KEY_PAUSE', 'KEY_PERIOD', 'KEY_PRINT_SCREEN', 'KEY_Q', 'KEY_R', 'KEY_RIGHT', 'KEY_RIGHT_ALT', 'KEY_RIGHT_BRACKET', 'KEY_RIGHT_CONTROL', 'KEY_RIGHT_SHIFT', 'KEY_RIGHT_SUPER', 'KEY_S', 'KEY_SCROLL_LOCK', 'KEY_SEMICOLON', 'KEY_SLASH', 'KEY_SPACE', 'KEY_T', 'KEY_TAB', 'KEY_U', 'KEY_UNKNOWN', 'KEY_UP', 'KEY_V', 'KEY_W', 'KEY_WORLD_1', 'KEY_WORLD_2', 'KEY_X', 'KEY_Y', 'KEY_Z', 'MOUSE_BUTTON_1', 'MOUSE_BUTTON_2', 'MOUSE_BUTTON_3', 'MOUSE_BUTTON_4', 'MOUSE_BUTTON_5', 'MOUSE_BUTTON_6', 'MOUSE_BUTTON_7', 'MOUSE_BUTTON_8', 'MOUSE_BUTTON_LAST', 'MOUSE_BUTTON_LEFT', 'MOUSE_BUTTON_MIDDLE', 'MOUSE_BUTTON_RIGHT', 'MTWindow', 'PRESS', 'RELEASE', 'REPEAT', 'UIAction', 'UIKeyEvent', 'UIMouseButton', 'Window']
class BaseWindow:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    class RenderMode:
        """
        Members:
        
          GRAY
        
          BGR
        """
        BGR: typing.ClassVar[BaseWindow.RenderMode]  # value = <RenderMode.BGR: 1>
        GRAY: typing.ClassVar[BaseWindow.RenderMode]  # value = <RenderMode.GRAY: 0>
        __members__: typing.ClassVar[dict[str, BaseWindow.RenderMode]]  # value = {'GRAY': <RenderMode.GRAY: 0>, 'BGR': <RenderMode.BGR: 1>}
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
    BGR: typing.ClassVar[BaseWindow.RenderMode]  # value = <RenderMode.BGR: 1>
    GRAY: typing.ClassVar[BaseWindow.RenderMode]  # value = <RenderMode.GRAY: 0>
    def get_rendering_mode(self) -> ...:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def get_size(self) -> tuple:
        """
        Returns the tuple (widh, height)
        """
    def poll_events(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_close_flag(self) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_cursor_pos_callback(self, arg0: typing.Any) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_keyboard_callback(self, arg0: typing.Any) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def set_mouse_callback(self, arg0: typing.Any) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def should_close(self) -> bool:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class EventLoop:
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    @staticmethod
    def poll_and_dispatch(sleep_time_ms: int = 0) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
    def __init__(self) -> None:
        ...
class MTWindow(BaseWindow):
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __enter__(self, *args) -> MTWindow:
        """
        Method that is invoked on entry to the body of the 'with' statement
        """
    def __exit__(self, *args) -> None:
        """
        Method that is invoked on exit from the body of the 'with' statement
        """
    def __init__(self, title: str, width: int, height: int, mode: BaseWindow.RenderMode, open_directly: bool = False) -> None:
        ...
    def destroy(self) -> None:
        """
        Destroys the window. This method has to be called after closing the window if this class has been constructed using open_directly=True.
        """
    def show_async(self, image: numpy.ndarray, auto_poll: bool = True) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
class UIAction:
    """
    Members:
    
      RELEASE
    
      PRESS
    
      REPEAT
    """
    PRESS: typing.ClassVar[UIAction]  # value = <UIAction.PRESS: 1>
    RELEASE: typing.ClassVar[UIAction]  # value = <UIAction.RELEASE: 0>
    REPEAT: typing.ClassVar[UIAction]  # value = <UIAction.REPEAT: 2>
    __members__: typing.ClassVar[dict[str, UIAction]]  # value = {'RELEASE': <UIAction.RELEASE: 0>, 'PRESS': <UIAction.PRESS: 1>, 'REPEAT': <UIAction.REPEAT: 2>}
    def __and__(self, other: typing.Any) -> typing.Any:
        ...
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
    def __invert__(self) -> typing.Any:
        ...
    def __le__(self, other: typing.Any) -> bool:
        ...
    def __lt__(self, other: typing.Any) -> bool:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __or__(self, other: typing.Any) -> typing.Any:
        ...
    def __rand__(self, other: typing.Any) -> typing.Any:
        ...
    def __repr__(self) -> str:
        ...
    def __ror__(self, other: typing.Any) -> typing.Any:
        ...
    def __rxor__(self, other: typing.Any) -> typing.Any:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    def __xor__(self, other: typing.Any) -> typing.Any:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class UIKeyEvent:
    """
    Members:
    
      KEY_UNKNOWN
    
      KEY_SPACE
    
      KEY_APOSTROPHE
    
      KEY_COMMA
    
      KEY_MINUS
    
      KEY_PERIOD
    
      KEY_SLASH
    
      KEY_0
    
      KEY_1
    
      KEY_2
    
      KEY_3
    
      KEY_4
    
      KEY_5
    
      KEY_6
    
      KEY_7
    
      KEY_8
    
      KEY_9
    
      KEY_SEMICOLON
    
      KEY_EQUAL
    
      KEY_A
    
      KEY_B
    
      KEY_C
    
      KEY_D
    
      KEY_E
    
      KEY_F
    
      KEY_G
    
      KEY_H
    
      KEY_I
    
      KEY_J
    
      KEY_K
    
      KEY_L
    
      KEY_M
    
      KEY_N
    
      KEY_O
    
      KEY_P
    
      KEY_Q
    
      KEY_R
    
      KEY_S
    
      KEY_T
    
      KEY_U
    
      KEY_V
    
      KEY_W
    
      KEY_X
    
      KEY_Y
    
      KEY_Z
    
      KEY_LEFT_BRACKET
    
      KEY_BACKSLASH
    
      KEY_RIGHT_BRACKET
    
      KEY_GRAVE_ACCENT
    
      KEY_WORLD_1
    
      KEY_WORLD_2
    
      KEY_ESCAPE
    
      KEY_ENTER
    
      KEY_TAB
    
      KEY_BACKSPACE
    
      KEY_INSERT
    
      KEY_DELETE
    
      KEY_RIGHT
    
      KEY_LEFT
    
      KEY_DOWN
    
      KEY_UP
    
      KEY_PAGE_UP
    
      KEY_PAGE_DOWN
    
      KEY_HOME
    
      KEY_END
    
      KEY_CAPS_LOCK
    
      KEY_SCROLL_LOCK
    
      KEY_NUM_LOCK
    
      KEY_PRINT_SCREEN
    
      KEY_PAUSE
    
      KEY_F1
    
      KEY_F2
    
      KEY_F3
    
      KEY_F4
    
      KEY_F5
    
      KEY_F6
    
      KEY_F7
    
      KEY_F8
    
      KEY_F9
    
      KEY_F10
    
      KEY_F11
    
      KEY_F12
    
      KEY_F13
    
      KEY_F14
    
      KEY_F15
    
      KEY_F16
    
      KEY_F17
    
      KEY_F18
    
      KEY_F19
    
      KEY_F20
    
      KEY_F21
    
      KEY_F22
    
      KEY_F23
    
      KEY_F24
    
      KEY_F25
    
      KEY_KP_0
    
      KEY_KP_1
    
      KEY_KP_2
    
      KEY_KP_3
    
      KEY_KP_4
    
      KEY_KP_5
    
      KEY_KP_6
    
      KEY_KP_7
    
      KEY_KP_8
    
      KEY_KP_9
    
      KEY_KP_DECIMAL
    
      KEY_KP_DIVIDE
    
      KEY_KP_MULTIPLY
    
      KEY_KP_SUBTRACT
    
      KEY_KP_ADD
    
      KEY_KP_ENTER
    
      KEY_KP_EQUAL
    
      KEY_LEFT_SHIFT
    
      KEY_LEFT_CONTROL
    
      KEY_LEFT_ALT
    
      KEY_LEFT_SUPER
    
      KEY_RIGHT_SHIFT
    
      KEY_RIGHT_CONTROL
    
      KEY_RIGHT_ALT
    
      KEY_RIGHT_SUPER
    
      KEY_MENU
    
      KEY_LAST
    """
    KEY_0: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_0: 48>
    KEY_1: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_1: 49>
    KEY_2: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_2: 50>
    KEY_3: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_3: 51>
    KEY_4: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_4: 52>
    KEY_5: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_5: 53>
    KEY_6: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_6: 54>
    KEY_7: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_7: 55>
    KEY_8: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_8: 56>
    KEY_9: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_9: 57>
    KEY_A: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_A: 65>
    KEY_APOSTROPHE: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_APOSTROPHE: 39>
    KEY_B: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_B: 66>
    KEY_BACKSLASH: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_BACKSLASH: 92>
    KEY_BACKSPACE: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_BACKSPACE: 259>
    KEY_C: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_C: 67>
    KEY_CAPS_LOCK: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_CAPS_LOCK: 280>
    KEY_COMMA: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_COMMA: 44>
    KEY_D: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_D: 68>
    KEY_DELETE: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_DELETE: 261>
    KEY_DOWN: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_DOWN: 264>
    KEY_E: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_E: 69>
    KEY_END: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_END: 269>
    KEY_ENTER: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_ENTER: 257>
    KEY_EQUAL: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_EQUAL: 61>
    KEY_ESCAPE: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_ESCAPE: 256>
    KEY_F: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F: 70>
    KEY_F1: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F1: 290>
    KEY_F10: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F10: 299>
    KEY_F11: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F11: 300>
    KEY_F12: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F12: 301>
    KEY_F13: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F13: 302>
    KEY_F14: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F14: 303>
    KEY_F15: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F15: 304>
    KEY_F16: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F16: 305>
    KEY_F17: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F17: 306>
    KEY_F18: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F18: 307>
    KEY_F19: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F19: 308>
    KEY_F2: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F2: 291>
    KEY_F20: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F20: 309>
    KEY_F21: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F21: 310>
    KEY_F22: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F22: 311>
    KEY_F23: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F23: 312>
    KEY_F24: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F24: 313>
    KEY_F25: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F25: 314>
    KEY_F3: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F3: 292>
    KEY_F4: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F4: 293>
    KEY_F5: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F5: 294>
    KEY_F6: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F6: 295>
    KEY_F7: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F7: 296>
    KEY_F8: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F8: 297>
    KEY_F9: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_F9: 298>
    KEY_G: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_G: 71>
    KEY_GRAVE_ACCENT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_GRAVE_ACCENT: 96>
    KEY_H: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_H: 72>
    KEY_HOME: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_HOME: 268>
    KEY_I: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_I: 73>
    KEY_INSERT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_INSERT: 260>
    KEY_J: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_J: 74>
    KEY_K: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_K: 75>
    KEY_KP_0: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_0: 320>
    KEY_KP_1: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_1: 321>
    KEY_KP_2: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_2: 322>
    KEY_KP_3: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_3: 323>
    KEY_KP_4: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_4: 324>
    KEY_KP_5: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_5: 325>
    KEY_KP_6: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_6: 326>
    KEY_KP_7: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_7: 327>
    KEY_KP_8: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_8: 328>
    KEY_KP_9: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_9: 329>
    KEY_KP_ADD: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_ADD: 334>
    KEY_KP_DECIMAL: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_DECIMAL: 330>
    KEY_KP_DIVIDE: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_DIVIDE: 331>
    KEY_KP_ENTER: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_ENTER: 335>
    KEY_KP_EQUAL: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_EQUAL: 336>
    KEY_KP_MULTIPLY: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_MULTIPLY: 332>
    KEY_KP_SUBTRACT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_KP_SUBTRACT: 333>
    KEY_L: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_L: 76>
    KEY_LAST: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_MENU: 348>
    KEY_LEFT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_LEFT: 263>
    KEY_LEFT_ALT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_LEFT_ALT: 342>
    KEY_LEFT_BRACKET: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_LEFT_BRACKET: 91>
    KEY_LEFT_CONTROL: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_LEFT_CONTROL: 341>
    KEY_LEFT_SHIFT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_LEFT_SHIFT: 340>
    KEY_LEFT_SUPER: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_LEFT_SUPER: 343>
    KEY_M: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_M: 77>
    KEY_MENU: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_MENU: 348>
    KEY_MINUS: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_MINUS: 45>
    KEY_N: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_N: 78>
    KEY_NUM_LOCK: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_NUM_LOCK: 282>
    KEY_O: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_O: 79>
    KEY_P: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_P: 80>
    KEY_PAGE_DOWN: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_PAGE_DOWN: 267>
    KEY_PAGE_UP: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_PAGE_UP: 266>
    KEY_PAUSE: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_PAUSE: 284>
    KEY_PERIOD: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_PERIOD: 46>
    KEY_PRINT_SCREEN: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_PRINT_SCREEN: 283>
    KEY_Q: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_Q: 81>
    KEY_R: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_R: 82>
    KEY_RIGHT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_RIGHT: 262>
    KEY_RIGHT_ALT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_RIGHT_ALT: 346>
    KEY_RIGHT_BRACKET: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_RIGHT_BRACKET: 93>
    KEY_RIGHT_CONTROL: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_RIGHT_CONTROL: 345>
    KEY_RIGHT_SHIFT: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_RIGHT_SHIFT: 344>
    KEY_RIGHT_SUPER: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_RIGHT_SUPER: 347>
    KEY_S: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_S: 83>
    KEY_SCROLL_LOCK: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_SCROLL_LOCK: 281>
    KEY_SEMICOLON: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_SEMICOLON: 59>
    KEY_SLASH: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_SLASH: 47>
    KEY_SPACE: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_SPACE: 32>
    KEY_T: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_T: 84>
    KEY_TAB: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_TAB: 258>
    KEY_U: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_U: 85>
    KEY_UNKNOWN: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_UNKNOWN: -1>
    KEY_UP: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_UP: 265>
    KEY_V: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_V: 86>
    KEY_W: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_W: 87>
    KEY_WORLD_1: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_WORLD_1: 161>
    KEY_WORLD_2: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_WORLD_2: 162>
    KEY_X: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_X: 88>
    KEY_Y: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_Y: 89>
    KEY_Z: typing.ClassVar[UIKeyEvent]  # value = <UIKeyEvent.KEY_Z: 90>
    __members__: typing.ClassVar[dict[str, UIKeyEvent]]  # value = {'KEY_UNKNOWN': <UIKeyEvent.KEY_UNKNOWN: -1>, 'KEY_SPACE': <UIKeyEvent.KEY_SPACE: 32>, 'KEY_APOSTROPHE': <UIKeyEvent.KEY_APOSTROPHE: 39>, 'KEY_COMMA': <UIKeyEvent.KEY_COMMA: 44>, 'KEY_MINUS': <UIKeyEvent.KEY_MINUS: 45>, 'KEY_PERIOD': <UIKeyEvent.KEY_PERIOD: 46>, 'KEY_SLASH': <UIKeyEvent.KEY_SLASH: 47>, 'KEY_0': <UIKeyEvent.KEY_0: 48>, 'KEY_1': <UIKeyEvent.KEY_1: 49>, 'KEY_2': <UIKeyEvent.KEY_2: 50>, 'KEY_3': <UIKeyEvent.KEY_3: 51>, 'KEY_4': <UIKeyEvent.KEY_4: 52>, 'KEY_5': <UIKeyEvent.KEY_5: 53>, 'KEY_6': <UIKeyEvent.KEY_6: 54>, 'KEY_7': <UIKeyEvent.KEY_7: 55>, 'KEY_8': <UIKeyEvent.KEY_8: 56>, 'KEY_9': <UIKeyEvent.KEY_9: 57>, 'KEY_SEMICOLON': <UIKeyEvent.KEY_SEMICOLON: 59>, 'KEY_EQUAL': <UIKeyEvent.KEY_EQUAL: 61>, 'KEY_A': <UIKeyEvent.KEY_A: 65>, 'KEY_B': <UIKeyEvent.KEY_B: 66>, 'KEY_C': <UIKeyEvent.KEY_C: 67>, 'KEY_D': <UIKeyEvent.KEY_D: 68>, 'KEY_E': <UIKeyEvent.KEY_E: 69>, 'KEY_F': <UIKeyEvent.KEY_F: 70>, 'KEY_G': <UIKeyEvent.KEY_G: 71>, 'KEY_H': <UIKeyEvent.KEY_H: 72>, 'KEY_I': <UIKeyEvent.KEY_I: 73>, 'KEY_J': <UIKeyEvent.KEY_J: 74>, 'KEY_K': <UIKeyEvent.KEY_K: 75>, 'KEY_L': <UIKeyEvent.KEY_L: 76>, 'KEY_M': <UIKeyEvent.KEY_M: 77>, 'KEY_N': <UIKeyEvent.KEY_N: 78>, 'KEY_O': <UIKeyEvent.KEY_O: 79>, 'KEY_P': <UIKeyEvent.KEY_P: 80>, 'KEY_Q': <UIKeyEvent.KEY_Q: 81>, 'KEY_R': <UIKeyEvent.KEY_R: 82>, 'KEY_S': <UIKeyEvent.KEY_S: 83>, 'KEY_T': <UIKeyEvent.KEY_T: 84>, 'KEY_U': <UIKeyEvent.KEY_U: 85>, 'KEY_V': <UIKeyEvent.KEY_V: 86>, 'KEY_W': <UIKeyEvent.KEY_W: 87>, 'KEY_X': <UIKeyEvent.KEY_X: 88>, 'KEY_Y': <UIKeyEvent.KEY_Y: 89>, 'KEY_Z': <UIKeyEvent.KEY_Z: 90>, 'KEY_LEFT_BRACKET': <UIKeyEvent.KEY_LEFT_BRACKET: 91>, 'KEY_BACKSLASH': <UIKeyEvent.KEY_BACKSLASH: 92>, 'KEY_RIGHT_BRACKET': <UIKeyEvent.KEY_RIGHT_BRACKET: 93>, 'KEY_GRAVE_ACCENT': <UIKeyEvent.KEY_GRAVE_ACCENT: 96>, 'KEY_WORLD_1': <UIKeyEvent.KEY_WORLD_1: 161>, 'KEY_WORLD_2': <UIKeyEvent.KEY_WORLD_2: 162>, 'KEY_ESCAPE': <UIKeyEvent.KEY_ESCAPE: 256>, 'KEY_ENTER': <UIKeyEvent.KEY_ENTER: 257>, 'KEY_TAB': <UIKeyEvent.KEY_TAB: 258>, 'KEY_BACKSPACE': <UIKeyEvent.KEY_BACKSPACE: 259>, 'KEY_INSERT': <UIKeyEvent.KEY_INSERT: 260>, 'KEY_DELETE': <UIKeyEvent.KEY_DELETE: 261>, 'KEY_RIGHT': <UIKeyEvent.KEY_RIGHT: 262>, 'KEY_LEFT': <UIKeyEvent.KEY_LEFT: 263>, 'KEY_DOWN': <UIKeyEvent.KEY_DOWN: 264>, 'KEY_UP': <UIKeyEvent.KEY_UP: 265>, 'KEY_PAGE_UP': <UIKeyEvent.KEY_PAGE_UP: 266>, 'KEY_PAGE_DOWN': <UIKeyEvent.KEY_PAGE_DOWN: 267>, 'KEY_HOME': <UIKeyEvent.KEY_HOME: 268>, 'KEY_END': <UIKeyEvent.KEY_END: 269>, 'KEY_CAPS_LOCK': <UIKeyEvent.KEY_CAPS_LOCK: 280>, 'KEY_SCROLL_LOCK': <UIKeyEvent.KEY_SCROLL_LOCK: 281>, 'KEY_NUM_LOCK': <UIKeyEvent.KEY_NUM_LOCK: 282>, 'KEY_PRINT_SCREEN': <UIKeyEvent.KEY_PRINT_SCREEN: 283>, 'KEY_PAUSE': <UIKeyEvent.KEY_PAUSE: 284>, 'KEY_F1': <UIKeyEvent.KEY_F1: 290>, 'KEY_F2': <UIKeyEvent.KEY_F2: 291>, 'KEY_F3': <UIKeyEvent.KEY_F3: 292>, 'KEY_F4': <UIKeyEvent.KEY_F4: 293>, 'KEY_F5': <UIKeyEvent.KEY_F5: 294>, 'KEY_F6': <UIKeyEvent.KEY_F6: 295>, 'KEY_F7': <UIKeyEvent.KEY_F7: 296>, 'KEY_F8': <UIKeyEvent.KEY_F8: 297>, 'KEY_F9': <UIKeyEvent.KEY_F9: 298>, 'KEY_F10': <UIKeyEvent.KEY_F10: 299>, 'KEY_F11': <UIKeyEvent.KEY_F11: 300>, 'KEY_F12': <UIKeyEvent.KEY_F12: 301>, 'KEY_F13': <UIKeyEvent.KEY_F13: 302>, 'KEY_F14': <UIKeyEvent.KEY_F14: 303>, 'KEY_F15': <UIKeyEvent.KEY_F15: 304>, 'KEY_F16': <UIKeyEvent.KEY_F16: 305>, 'KEY_F17': <UIKeyEvent.KEY_F17: 306>, 'KEY_F18': <UIKeyEvent.KEY_F18: 307>, 'KEY_F19': <UIKeyEvent.KEY_F19: 308>, 'KEY_F20': <UIKeyEvent.KEY_F20: 309>, 'KEY_F21': <UIKeyEvent.KEY_F21: 310>, 'KEY_F22': <UIKeyEvent.KEY_F22: 311>, 'KEY_F23': <UIKeyEvent.KEY_F23: 312>, 'KEY_F24': <UIKeyEvent.KEY_F24: 313>, 'KEY_F25': <UIKeyEvent.KEY_F25: 314>, 'KEY_KP_0': <UIKeyEvent.KEY_KP_0: 320>, 'KEY_KP_1': <UIKeyEvent.KEY_KP_1: 321>, 'KEY_KP_2': <UIKeyEvent.KEY_KP_2: 322>, 'KEY_KP_3': <UIKeyEvent.KEY_KP_3: 323>, 'KEY_KP_4': <UIKeyEvent.KEY_KP_4: 324>, 'KEY_KP_5': <UIKeyEvent.KEY_KP_5: 325>, 'KEY_KP_6': <UIKeyEvent.KEY_KP_6: 326>, 'KEY_KP_7': <UIKeyEvent.KEY_KP_7: 327>, 'KEY_KP_8': <UIKeyEvent.KEY_KP_8: 328>, 'KEY_KP_9': <UIKeyEvent.KEY_KP_9: 329>, 'KEY_KP_DECIMAL': <UIKeyEvent.KEY_KP_DECIMAL: 330>, 'KEY_KP_DIVIDE': <UIKeyEvent.KEY_KP_DIVIDE: 331>, 'KEY_KP_MULTIPLY': <UIKeyEvent.KEY_KP_MULTIPLY: 332>, 'KEY_KP_SUBTRACT': <UIKeyEvent.KEY_KP_SUBTRACT: 333>, 'KEY_KP_ADD': <UIKeyEvent.KEY_KP_ADD: 334>, 'KEY_KP_ENTER': <UIKeyEvent.KEY_KP_ENTER: 335>, 'KEY_KP_EQUAL': <UIKeyEvent.KEY_KP_EQUAL: 336>, 'KEY_LEFT_SHIFT': <UIKeyEvent.KEY_LEFT_SHIFT: 340>, 'KEY_LEFT_CONTROL': <UIKeyEvent.KEY_LEFT_CONTROL: 341>, 'KEY_LEFT_ALT': <UIKeyEvent.KEY_LEFT_ALT: 342>, 'KEY_LEFT_SUPER': <UIKeyEvent.KEY_LEFT_SUPER: 343>, 'KEY_RIGHT_SHIFT': <UIKeyEvent.KEY_RIGHT_SHIFT: 344>, 'KEY_RIGHT_CONTROL': <UIKeyEvent.KEY_RIGHT_CONTROL: 345>, 'KEY_RIGHT_ALT': <UIKeyEvent.KEY_RIGHT_ALT: 346>, 'KEY_RIGHT_SUPER': <UIKeyEvent.KEY_RIGHT_SUPER: 347>, 'KEY_MENU': <UIKeyEvent.KEY_MENU: 348>, 'KEY_LAST': <UIKeyEvent.KEY_MENU: 348>}
    def __and__(self, other: typing.Any) -> typing.Any:
        ...
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
    def __invert__(self) -> typing.Any:
        ...
    def __le__(self, other: typing.Any) -> bool:
        ...
    def __lt__(self, other: typing.Any) -> bool:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __or__(self, other: typing.Any) -> typing.Any:
        ...
    def __rand__(self, other: typing.Any) -> typing.Any:
        ...
    def __repr__(self) -> str:
        ...
    def __ror__(self, other: typing.Any) -> typing.Any:
        ...
    def __rxor__(self, other: typing.Any) -> typing.Any:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    def __xor__(self, other: typing.Any) -> typing.Any:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class UIMouseButton:
    """
    Members:
    
      MOUSE_BUTTON_1
    
      MOUSE_BUTTON_2
    
      MOUSE_BUTTON_3
    
      MOUSE_BUTTON_4
    
      MOUSE_BUTTON_5
    
      MOUSE_BUTTON_6
    
      MOUSE_BUTTON_7
    
      MOUSE_BUTTON_8
    
      MOUSE_BUTTON_LAST
    
      MOUSE_BUTTON_LEFT
    
      MOUSE_BUTTON_RIGHT
    
      MOUSE_BUTTON_MIDDLE
    """
    MOUSE_BUTTON_1: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_1: 0>
    MOUSE_BUTTON_2: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_2: 1>
    MOUSE_BUTTON_3: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_3: 2>
    MOUSE_BUTTON_4: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_4: 3>
    MOUSE_BUTTON_5: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_5: 4>
    MOUSE_BUTTON_6: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_6: 5>
    MOUSE_BUTTON_7: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_7: 6>
    MOUSE_BUTTON_8: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_8: 7>
    MOUSE_BUTTON_LAST: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_8: 7>
    MOUSE_BUTTON_LEFT: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_1: 0>
    MOUSE_BUTTON_MIDDLE: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_3: 2>
    MOUSE_BUTTON_RIGHT: typing.ClassVar[UIMouseButton]  # value = <UIMouseButton.MOUSE_BUTTON_2: 1>
    __members__: typing.ClassVar[dict[str, UIMouseButton]]  # value = {'MOUSE_BUTTON_1': <UIMouseButton.MOUSE_BUTTON_1: 0>, 'MOUSE_BUTTON_2': <UIMouseButton.MOUSE_BUTTON_2: 1>, 'MOUSE_BUTTON_3': <UIMouseButton.MOUSE_BUTTON_3: 2>, 'MOUSE_BUTTON_4': <UIMouseButton.MOUSE_BUTTON_4: 3>, 'MOUSE_BUTTON_5': <UIMouseButton.MOUSE_BUTTON_5: 4>, 'MOUSE_BUTTON_6': <UIMouseButton.MOUSE_BUTTON_6: 5>, 'MOUSE_BUTTON_7': <UIMouseButton.MOUSE_BUTTON_7: 6>, 'MOUSE_BUTTON_8': <UIMouseButton.MOUSE_BUTTON_8: 7>, 'MOUSE_BUTTON_LAST': <UIMouseButton.MOUSE_BUTTON_8: 7>, 'MOUSE_BUTTON_LEFT': <UIMouseButton.MOUSE_BUTTON_1: 0>, 'MOUSE_BUTTON_RIGHT': <UIMouseButton.MOUSE_BUTTON_2: 1>, 'MOUSE_BUTTON_MIDDLE': <UIMouseButton.MOUSE_BUTTON_3: 2>}
    def __and__(self, other: typing.Any) -> typing.Any:
        ...
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
    def __invert__(self) -> typing.Any:
        ...
    def __le__(self, other: typing.Any) -> bool:
        ...
    def __lt__(self, other: typing.Any) -> bool:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __or__(self, other: typing.Any) -> typing.Any:
        ...
    def __rand__(self, other: typing.Any) -> typing.Any:
        ...
    def __repr__(self) -> str:
        ...
    def __ror__(self, other: typing.Any) -> typing.Any:
        ...
    def __rxor__(self, other: typing.Any) -> typing.Any:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    def __xor__(self, other: typing.Any) -> typing.Any:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Window(BaseWindow):
    """
    ###########################################
    #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
    ###########################################
    """
    def __enter__(self, *args) -> Window:
        """
        Method that is invoked on entry to the body of the 'with' statement
        """
    def __exit__(self, *args) -> None:
        """
        Method that is invoked on exit from the body of the 'with' statement
        """
    def __init__(self, title: str, width: int, height: int, mode: BaseWindow.RenderMode, open_directly: bool = False) -> None:
        ...
    def destroy(self) -> None:
        """
        Destroys the window. This method has to be called after closing the window if this class has been constructed using open_directly=True.
        """
    def show(self, image: numpy.ndarray, auto_poll: bool = True) -> None:
        """
        ###########################################
        #  PYTHON BINDINGS WITHOUT DOCUMENTATION  #
        ###########################################
        """
KEY_0: UIKeyEvent  # value = <UIKeyEvent.KEY_0: 48>
KEY_1: UIKeyEvent  # value = <UIKeyEvent.KEY_1: 49>
KEY_2: UIKeyEvent  # value = <UIKeyEvent.KEY_2: 50>
KEY_3: UIKeyEvent  # value = <UIKeyEvent.KEY_3: 51>
KEY_4: UIKeyEvent  # value = <UIKeyEvent.KEY_4: 52>
KEY_5: UIKeyEvent  # value = <UIKeyEvent.KEY_5: 53>
KEY_6: UIKeyEvent  # value = <UIKeyEvent.KEY_6: 54>
KEY_7: UIKeyEvent  # value = <UIKeyEvent.KEY_7: 55>
KEY_8: UIKeyEvent  # value = <UIKeyEvent.KEY_8: 56>
KEY_9: UIKeyEvent  # value = <UIKeyEvent.KEY_9: 57>
KEY_A: UIKeyEvent  # value = <UIKeyEvent.KEY_A: 65>
KEY_APOSTROPHE: UIKeyEvent  # value = <UIKeyEvent.KEY_APOSTROPHE: 39>
KEY_B: UIKeyEvent  # value = <UIKeyEvent.KEY_B: 66>
KEY_BACKSLASH: UIKeyEvent  # value = <UIKeyEvent.KEY_BACKSLASH: 92>
KEY_BACKSPACE: UIKeyEvent  # value = <UIKeyEvent.KEY_BACKSPACE: 259>
KEY_C: UIKeyEvent  # value = <UIKeyEvent.KEY_C: 67>
KEY_CAPS_LOCK: UIKeyEvent  # value = <UIKeyEvent.KEY_CAPS_LOCK: 280>
KEY_COMMA: UIKeyEvent  # value = <UIKeyEvent.KEY_COMMA: 44>
KEY_D: UIKeyEvent  # value = <UIKeyEvent.KEY_D: 68>
KEY_DELETE: UIKeyEvent  # value = <UIKeyEvent.KEY_DELETE: 261>
KEY_DOWN: UIKeyEvent  # value = <UIKeyEvent.KEY_DOWN: 264>
KEY_E: UIKeyEvent  # value = <UIKeyEvent.KEY_E: 69>
KEY_END: UIKeyEvent  # value = <UIKeyEvent.KEY_END: 269>
KEY_ENTER: UIKeyEvent  # value = <UIKeyEvent.KEY_ENTER: 257>
KEY_EQUAL: UIKeyEvent  # value = <UIKeyEvent.KEY_EQUAL: 61>
KEY_ESCAPE: UIKeyEvent  # value = <UIKeyEvent.KEY_ESCAPE: 256>
KEY_F: UIKeyEvent  # value = <UIKeyEvent.KEY_F: 70>
KEY_F1: UIKeyEvent  # value = <UIKeyEvent.KEY_F1: 290>
KEY_F10: UIKeyEvent  # value = <UIKeyEvent.KEY_F10: 299>
KEY_F11: UIKeyEvent  # value = <UIKeyEvent.KEY_F11: 300>
KEY_F12: UIKeyEvent  # value = <UIKeyEvent.KEY_F12: 301>
KEY_F13: UIKeyEvent  # value = <UIKeyEvent.KEY_F13: 302>
KEY_F14: UIKeyEvent  # value = <UIKeyEvent.KEY_F14: 303>
KEY_F15: UIKeyEvent  # value = <UIKeyEvent.KEY_F15: 304>
KEY_F16: UIKeyEvent  # value = <UIKeyEvent.KEY_F16: 305>
KEY_F17: UIKeyEvent  # value = <UIKeyEvent.KEY_F17: 306>
KEY_F18: UIKeyEvent  # value = <UIKeyEvent.KEY_F18: 307>
KEY_F19: UIKeyEvent  # value = <UIKeyEvent.KEY_F19: 308>
KEY_F2: UIKeyEvent  # value = <UIKeyEvent.KEY_F2: 291>
KEY_F20: UIKeyEvent  # value = <UIKeyEvent.KEY_F20: 309>
KEY_F21: UIKeyEvent  # value = <UIKeyEvent.KEY_F21: 310>
KEY_F22: UIKeyEvent  # value = <UIKeyEvent.KEY_F22: 311>
KEY_F23: UIKeyEvent  # value = <UIKeyEvent.KEY_F23: 312>
KEY_F24: UIKeyEvent  # value = <UIKeyEvent.KEY_F24: 313>
KEY_F25: UIKeyEvent  # value = <UIKeyEvent.KEY_F25: 314>
KEY_F3: UIKeyEvent  # value = <UIKeyEvent.KEY_F3: 292>
KEY_F4: UIKeyEvent  # value = <UIKeyEvent.KEY_F4: 293>
KEY_F5: UIKeyEvent  # value = <UIKeyEvent.KEY_F5: 294>
KEY_F6: UIKeyEvent  # value = <UIKeyEvent.KEY_F6: 295>
KEY_F7: UIKeyEvent  # value = <UIKeyEvent.KEY_F7: 296>
KEY_F8: UIKeyEvent  # value = <UIKeyEvent.KEY_F8: 297>
KEY_F9: UIKeyEvent  # value = <UIKeyEvent.KEY_F9: 298>
KEY_G: UIKeyEvent  # value = <UIKeyEvent.KEY_G: 71>
KEY_GRAVE_ACCENT: UIKeyEvent  # value = <UIKeyEvent.KEY_GRAVE_ACCENT: 96>
KEY_H: UIKeyEvent  # value = <UIKeyEvent.KEY_H: 72>
KEY_HOME: UIKeyEvent  # value = <UIKeyEvent.KEY_HOME: 268>
KEY_I: UIKeyEvent  # value = <UIKeyEvent.KEY_I: 73>
KEY_INSERT: UIKeyEvent  # value = <UIKeyEvent.KEY_INSERT: 260>
KEY_J: UIKeyEvent  # value = <UIKeyEvent.KEY_J: 74>
KEY_K: UIKeyEvent  # value = <UIKeyEvent.KEY_K: 75>
KEY_KP_0: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_0: 320>
KEY_KP_1: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_1: 321>
KEY_KP_2: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_2: 322>
KEY_KP_3: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_3: 323>
KEY_KP_4: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_4: 324>
KEY_KP_5: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_5: 325>
KEY_KP_6: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_6: 326>
KEY_KP_7: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_7: 327>
KEY_KP_8: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_8: 328>
KEY_KP_9: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_9: 329>
KEY_KP_ADD: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_ADD: 334>
KEY_KP_DECIMAL: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_DECIMAL: 330>
KEY_KP_DIVIDE: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_DIVIDE: 331>
KEY_KP_ENTER: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_ENTER: 335>
KEY_KP_EQUAL: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_EQUAL: 336>
KEY_KP_MULTIPLY: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_MULTIPLY: 332>
KEY_KP_SUBTRACT: UIKeyEvent  # value = <UIKeyEvent.KEY_KP_SUBTRACT: 333>
KEY_L: UIKeyEvent  # value = <UIKeyEvent.KEY_L: 76>
KEY_LAST: UIKeyEvent  # value = <UIKeyEvent.KEY_MENU: 348>
KEY_LEFT: UIKeyEvent  # value = <UIKeyEvent.KEY_LEFT: 263>
KEY_LEFT_ALT: UIKeyEvent  # value = <UIKeyEvent.KEY_LEFT_ALT: 342>
KEY_LEFT_BRACKET: UIKeyEvent  # value = <UIKeyEvent.KEY_LEFT_BRACKET: 91>
KEY_LEFT_CONTROL: UIKeyEvent  # value = <UIKeyEvent.KEY_LEFT_CONTROL: 341>
KEY_LEFT_SHIFT: UIKeyEvent  # value = <UIKeyEvent.KEY_LEFT_SHIFT: 340>
KEY_LEFT_SUPER: UIKeyEvent  # value = <UIKeyEvent.KEY_LEFT_SUPER: 343>
KEY_M: UIKeyEvent  # value = <UIKeyEvent.KEY_M: 77>
KEY_MENU: UIKeyEvent  # value = <UIKeyEvent.KEY_MENU: 348>
KEY_MINUS: UIKeyEvent  # value = <UIKeyEvent.KEY_MINUS: 45>
KEY_N: UIKeyEvent  # value = <UIKeyEvent.KEY_N: 78>
KEY_NUM_LOCK: UIKeyEvent  # value = <UIKeyEvent.KEY_NUM_LOCK: 282>
KEY_O: UIKeyEvent  # value = <UIKeyEvent.KEY_O: 79>
KEY_P: UIKeyEvent  # value = <UIKeyEvent.KEY_P: 80>
KEY_PAGE_DOWN: UIKeyEvent  # value = <UIKeyEvent.KEY_PAGE_DOWN: 267>
KEY_PAGE_UP: UIKeyEvent  # value = <UIKeyEvent.KEY_PAGE_UP: 266>
KEY_PAUSE: UIKeyEvent  # value = <UIKeyEvent.KEY_PAUSE: 284>
KEY_PERIOD: UIKeyEvent  # value = <UIKeyEvent.KEY_PERIOD: 46>
KEY_PRINT_SCREEN: UIKeyEvent  # value = <UIKeyEvent.KEY_PRINT_SCREEN: 283>
KEY_Q: UIKeyEvent  # value = <UIKeyEvent.KEY_Q: 81>
KEY_R: UIKeyEvent  # value = <UIKeyEvent.KEY_R: 82>
KEY_RIGHT: UIKeyEvent  # value = <UIKeyEvent.KEY_RIGHT: 262>
KEY_RIGHT_ALT: UIKeyEvent  # value = <UIKeyEvent.KEY_RIGHT_ALT: 346>
KEY_RIGHT_BRACKET: UIKeyEvent  # value = <UIKeyEvent.KEY_RIGHT_BRACKET: 93>
KEY_RIGHT_CONTROL: UIKeyEvent  # value = <UIKeyEvent.KEY_RIGHT_CONTROL: 345>
KEY_RIGHT_SHIFT: UIKeyEvent  # value = <UIKeyEvent.KEY_RIGHT_SHIFT: 344>
KEY_RIGHT_SUPER: UIKeyEvent  # value = <UIKeyEvent.KEY_RIGHT_SUPER: 347>
KEY_S: UIKeyEvent  # value = <UIKeyEvent.KEY_S: 83>
KEY_SCROLL_LOCK: UIKeyEvent  # value = <UIKeyEvent.KEY_SCROLL_LOCK: 281>
KEY_SEMICOLON: UIKeyEvent  # value = <UIKeyEvent.KEY_SEMICOLON: 59>
KEY_SLASH: UIKeyEvent  # value = <UIKeyEvent.KEY_SLASH: 47>
KEY_SPACE: UIKeyEvent  # value = <UIKeyEvent.KEY_SPACE: 32>
KEY_T: UIKeyEvent  # value = <UIKeyEvent.KEY_T: 84>
KEY_TAB: UIKeyEvent  # value = <UIKeyEvent.KEY_TAB: 258>
KEY_U: UIKeyEvent  # value = <UIKeyEvent.KEY_U: 85>
KEY_UNKNOWN: UIKeyEvent  # value = <UIKeyEvent.KEY_UNKNOWN: -1>
KEY_UP: UIKeyEvent  # value = <UIKeyEvent.KEY_UP: 265>
KEY_V: UIKeyEvent  # value = <UIKeyEvent.KEY_V: 86>
KEY_W: UIKeyEvent  # value = <UIKeyEvent.KEY_W: 87>
KEY_WORLD_1: UIKeyEvent  # value = <UIKeyEvent.KEY_WORLD_1: 161>
KEY_WORLD_2: UIKeyEvent  # value = <UIKeyEvent.KEY_WORLD_2: 162>
KEY_X: UIKeyEvent  # value = <UIKeyEvent.KEY_X: 88>
KEY_Y: UIKeyEvent  # value = <UIKeyEvent.KEY_Y: 89>
KEY_Z: UIKeyEvent  # value = <UIKeyEvent.KEY_Z: 90>
MOUSE_BUTTON_1: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_1: 0>
MOUSE_BUTTON_2: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_2: 1>
MOUSE_BUTTON_3: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_3: 2>
MOUSE_BUTTON_4: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_4: 3>
MOUSE_BUTTON_5: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_5: 4>
MOUSE_BUTTON_6: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_6: 5>
MOUSE_BUTTON_7: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_7: 6>
MOUSE_BUTTON_8: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_8: 7>
MOUSE_BUTTON_LAST: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_8: 7>
MOUSE_BUTTON_LEFT: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_1: 0>
MOUSE_BUTTON_MIDDLE: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_3: 2>
MOUSE_BUTTON_RIGHT: UIMouseButton  # value = <UIMouseButton.MOUSE_BUTTON_2: 1>
PRESS: UIAction  # value = <UIAction.PRESS: 1>
RELEASE: UIAction  # value = <UIAction.RELEASE: 0>
REPEAT: UIAction  # value = <UIAction.REPEAT: 2>
