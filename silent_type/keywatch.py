"""Wake the key watcher when a key changes, so it can sleep the rest of the time.

Windows Raw Input delivers a message to a hidden window each time a keyboard key
goes down or up (`RIDEV_INPUTSINK`, so even when another app has focus). It is not
a keyboard hook: it sits beside the typing path, not in it, so a busy or stalled
Silent Type can never delay, drop or alter a keystroke. The messages carry no key
codes here; they only wake the watcher, which then reads the key state as before.
The same wait also covers the "open the window" request from a second launch.
"""

import ctypes as C
import logging
import threading
from ctypes import wintypes as W

LOG = logging.getLogger(__name__)

WM_INPUT = 0x00FF
WM_QUIT = 0x0012
HWND_MESSAGE = -3
RIDEV_INPUTSINK = 0x00000100
QS_ALLINPUT = 0x04FF
PM_REMOVE = 0x0001
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0

LRESULT = C.c_ssize_t
WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
user32 = C.WinDLL("user32", use_last_error=True)
kernel32 = C.WinDLL("kernel32", use_last_error=True)


class WNDCLASS(C.Structure):
    _fields_ = [
        ("style", W.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", C.c_int),
        ("cbWndExtra", C.c_int),
        ("hInstance", W.HINSTANCE),
        ("hIcon", W.HICON),
        ("hCursor", W.HANDLE),
        ("hbrBackground", W.HBRUSH),
        ("lpszMenuName", W.LPCWSTR),
        ("lpszClassName", W.LPCWSTR),
    ]


class RAWINPUTDEVICE(C.Structure):
    _fields_ = [
        ("usUsagePage", W.USHORT),
        ("usUsage", W.USHORT),
        ("dwFlags", W.DWORD),
        ("hwndTarget", W.HWND),
    ]


user32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [C.POINTER(WNDCLASS)]
user32.RegisterClassW.restype = W.ATOM
user32.UnregisterClassW.argtypes = [W.LPCWSTR, W.HINSTANCE]
user32.CreateWindowExW.argtypes = [
    W.DWORD,
    W.LPCWSTR,
    W.LPCWSTR,
    W.DWORD,
    C.c_int,
    C.c_int,
    C.c_int,
    C.c_int,
    W.HWND,
    W.HMENU,
    W.HINSTANCE,
    W.LPVOID,
]
user32.CreateWindowExW.restype = W.HWND
user32.DestroyWindow.argtypes = [W.HWND]
user32.RegisterRawInputDevices.argtypes = [C.POINTER(RAWINPUTDEVICE), W.UINT, W.UINT]
user32.RegisterRawInputDevices.restype = W.BOOL
user32.PeekMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT]
user32.PeekMessageW.restype = W.BOOL
user32.DispatchMessageW.argtypes = [C.POINTER(W.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.MsgWaitForMultipleObjects.argtypes = [W.DWORD, C.POINTER(W.HANDLE), W.BOOL, W.DWORD, W.DWORD]
user32.MsgWaitForMultipleObjects.restype = W.DWORD
user32.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.PostMessageW.restype = W.BOOL
kernel32.GetModuleHandleW.argtypes = [W.LPCWSTR]
kernel32.GetModuleHandleW.restype = W.HMODULE


class KeyWatch:
    """Sets `wake` whenever a keyboard key changes, and calls `on_open` for an open request."""

    def __init__(self, wake, open_event=None, on_open=lambda: None, name="SilentTypeKeyWatch"):
        self.wake = wake
        self.open_event = open_event
        self.on_open = on_open
        self.name = name
        self.active = False
        self.heard = False
        self.hwnd = None
        self.stopping = threading.Event()
        self.started = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self, timeout=3):
        """Returns True when Raw Input is registered; False means the caller should poll."""
        self.thread.start()
        self.started.wait(timeout)
        return self.active

    def stop(self):
        self.stopping.set()
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_QUIT, 0, 0)

    def window_proc(self, hwnd, message, wparam, lparam):
        if message == WM_INPUT:
            if not self.heard:
                self.heard = True
                LOG.info("Raw Input key messages are arriving")
            self.wake.set()
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def run(self):
        instance = kernel32.GetModuleHandleW(None)
        proc = WNDPROC(self.window_proc)  # kept referenced for the life of the window
        window_class = WNDCLASS(lpfnWndProc=proc, hInstance=instance, lpszClassName=self.name)
        registered = False
        try:
            if not user32.RegisterClassW(C.byref(window_class)):
                raise C.WinError(C.get_last_error())
            registered = True
            self.hwnd = user32.CreateWindowExW(
                0, self.name, self.name, 0, 0, 0, 0, 0, HWND_MESSAGE, None, instance, None
            )
            if not self.hwnd:
                raise C.WinError(C.get_last_error())
            device = RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, self.hwnd)  # generic desktop, keyboard
            if not user32.RegisterRawInputDevices(C.byref(device), 1, C.sizeof(device)):
                raise C.WinError(C.get_last_error())
            self.active = True
        except OSError:
            LOG.exception("Raw Input unavailable; falling back to polling")
        finally:
            self.started.set()
        try:
            if self.active:
                self.pump()
        finally:
            self.active = False
            if self.hwnd:
                user32.DestroyWindow(self.hwnd)
                self.hwnd = None
            if registered:
                user32.UnregisterClassW(self.name, instance)

    def pump(self):
        handles = (W.HANDLE * 1)(self.open_event) if self.open_event else None
        count = 1 if handles else 0
        message = W.MSG()
        while not self.stopping.is_set():
            result = user32.MsgWaitForMultipleObjects(count, handles, False, INFINITE, QS_ALLINPUT)
            if count and result == WAIT_OBJECT_0:
                # The event is auto-reset, so waiting consumed the request: act on it here.
                self.on_open()
                self.wake.set()
            while user32.PeekMessageW(C.byref(message), None, 0, 0, PM_REMOVE):
                if message.message == WM_QUIT:
                    return
                user32.DispatchMessageW(C.byref(message))
