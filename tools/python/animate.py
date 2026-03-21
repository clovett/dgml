import argparse
import ctypes
import os
import time
import sys
from ctypes import wintypes, c_uint64

from sqlalchemy import false

from dgml import DirectedGraph

class WindowsHelpers:
    # Win32 constants
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    VK_LBUTTON = 0x01
    VK_CONTROL = 0x11
    VK_V = 0x56
    VK_A = 0x41
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    SW_SHOW = 5

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    OpenClipboard = user32.OpenClipboard
    OpenClipboard.argtypes = [wintypes.HWND]
    OpenClipboard.restype = wintypes.BOOL

    CloseClipboard = user32.CloseClipboard
    CloseClipboard.argtypes = []
    CloseClipboard.restype = wintypes.BOOL

    EmptyClipboard = user32.EmptyClipboard
    EmptyClipboard.argtypes = []
    EmptyClipboard.restype = wintypes.BOOL

    SetClipboardData = user32.SetClipboardData
    SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    SetClipboardData.restype = wintypes.HANDLE

    GetCursorPos = user32.GetCursorPos
    GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    GetCursorPos.restype = wintypes.BOOL

    WindowFromPoint = user32.WindowFromPoint
    WindowFromPoint.argtypes = [POINT]
    WindowFromPoint.restype = wintypes.HWND

    GetAsyncKeyState = user32.GetAsyncKeyState
    GetAsyncKeyState.argtypes = [wintypes.INT]
    GetAsyncKeyState.restype = wintypes.SHORT

    IsWindow = user32.IsWindow
    IsWindow.argtypes = [wintypes.HWND]
    IsWindow.restype = wintypes.BOOL

    SetForegroundWindow = user32.SetForegroundWindow
    SetForegroundWindow.argtypes = [wintypes.HWND]
    SetForegroundWindow.restype = wintypes.BOOL

    ShowWindow = user32.ShowWindow
    ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    ShowWindow.restype = wintypes.BOOL

    SetCursorPos = user32.SetCursorPos
    SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    SetCursorPos.restype = wintypes.BOOL

    ULONG_PTR = c_uint64

    mouse_event = user32.mouse_event
    mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ULONG_PTR]
    mouse_event.restype = None

    keybd_event = user32.keybd_event
    keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ULONG_PTR]
    keybd_event.restype = None

    GlobalAlloc = kernel32.GlobalAlloc
    GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    GlobalAlloc.restype = wintypes.HGLOBAL

    GlobalLock = kernel32.GlobalLock
    GlobalLock.argtypes = [wintypes.HGLOBAL]
    GlobalLock.restype = ctypes.c_void_p

    GlobalUnlock = kernel32.GlobalUnlock
    GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    GlobalUnlock.restype = wintypes.BOOL

    @classmethod
    def input_event_sleep(cls):
        time.sleep(0.1)

    @classmethod
    def set_clipboard_text(cls, text: str) -> None:
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = cls.GlobalAlloc(cls.GMEM_MOVEABLE, len(data))
        if not handle:
            raise OSError("GlobalAlloc failed")

        ptr = cls.GlobalLock(handle)
        if not ptr:
            raise OSError("GlobalLock failed")

        ctypes.memmove(ptr, data, len(data))
        cls.GlobalUnlock(handle)

        if not cls.OpenClipboard(None):
            raise OSError("OpenClipboard failed")

        try:
            if not cls.EmptyClipboard():
                raise OSError("EmptyClipboard failed")
            if not cls.SetClipboardData(cls.CF_UNICODETEXT, handle):
                raise OSError("SetClipboardData failed")
            # Clipboard owns handle after successful SetClipboardData.
            handle = None
        finally:
            cls.CloseClipboard()

    @classmethod
    def send_key(cls, vk_code: int, key_up: bool = False) -> None:
        flags = 0x0002 if key_up else 0
        cls.keybd_event(vk_code, 0, flags, 0)

    @classmethod
    def send_hotkey(cls, *keys: int) -> None:
        for key in keys:
            cls.send_key(key, key_up=False)
        for key in reversed(keys):
            cls.send_key(key, key_up=True)

    @classmethod
    def wait_for_target_click(cls) -> tuple[int, int, int]:
        print("Move the mouse over the target window and click the left mouse button...")
        was_down = False
        got_down = False
        hwnd = None
        x = 0
        y = 0
        while True:
            state = cls.GetAsyncKeyState(cls.VK_LBUTTON)
            is_down = (state & 0x8000) != 0
            if is_down and not was_down:
                got_down = True
                point = cls.POINT()
                if not cls.GetCursorPos(ctypes.byref(point)):
                    raise OSError("GetCursorPos failed")
                hwnd = cls.WindowFromPoint(point)
                if not hwnd:
                    raise RuntimeError("Could not find a window under cursor")
                print(f"Captured window handle: {hwnd} at ({point.x}, {point.y})")
                x = point.x
                y = point.y

            if not is_down and got_down:
                # wait for mouse up before returning.
                return hwnd, x, y

            cls.input_event_sleep()

    @classmethod
    def activate_window(cls, hwnd: int) -> None:
        if not cls.IsWindow(hwnd):
            raise RuntimeError("Captured target window is no longer valid")

        cls.ShowWindow(hwnd, cls.SW_SHOW)
        cls.SetForegroundWindow(hwnd)
        cls.input_event_sleep()

    @classmethod
    def left_click(cls, x: int, y: int) -> None:
        # Click to ensure the target window has focus before keyboard input.
        cls.SetCursorPos(x, y)
        cls.input_event_sleep()
        cls.mouse_event(cls.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        cls.mouse_event(cls.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        cls.input_event_sleep()


def list_dgml_files(folder: str) -> list[str]:
    files = []
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        if os.path.isfile(full) and name.lower().endswith(".dgml"):
            files.append(full)
    return files


def animate_folder(folder: str, delay: float) -> None:
    dgml_files = list_dgml_files(folder)
    if not dgml_files:
        raise RuntimeError(f"No .dgml files found in '{folder}'")

    print(f"Found {len(dgml_files)} DGML files")
    hwnd, x, y = WindowsHelpers.wait_for_target_click()

    hwnd2, x2, y2 = WindowsHelpers.wait_for_target_click()
    print("Starting animation... Press Ctrl+C to stop.")

    previous: DirectedGraph | None = None

    for index, path in enumerate(dgml_files, start=1):

        start = time.time()
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        has_changes = False
        graph = DirectedGraph()
        graph.load_dgml(path)

        if previous is not None:
            diff = graph.compare(previous)
            previous = graph
            if not diff.is_empty():
                has_changes = True

        previous = graph

        if not has_changes:
            print(f"[{index}/{len(dgml_files)}] No changes from previous, skipping {os.path.basename(path)}")
            continue

        WindowsHelpers.set_clipboard_text(content)
        WindowsHelpers.activate_window(hwnd)
        WindowsHelpers.left_click(x, y)
        WindowsHelpers.left_click(x2, y2)
        WindowsHelpers.send_hotkey(WindowsHelpers.VK_CONTROL, WindowsHelpers.VK_V)

        print(f"[{index}/{len(dgml_files)}] Pasted {os.path.basename(path)}")
        if index < len(dgml_files):
            end = time.time()
            elapsed = end - start
            remaining = max(0, delay - elapsed)
            time.sleep(remaining)

    print("Animation complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Animate DGML snapshots by pasting each file into a selected window"
    )
    parser.add_argument(
        "folder",
        default=".",
        help="Folder containing DGML files (default: current folder)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between frames (default: 1.0)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    folder = os.path.realpath(args.folder)

    if not os.path.isdir(folder):
        print(f"Folder does not exist: {folder}")
        return 1
    if args.delay < 0:
        print("--delay must be >= 0")
        return 1

    try:
        animate_folder(folder, args.delay)
    except KeyboardInterrupt:
        print("Stopped by user")
        return 130
    except Exception as ex:
        print(f"Error: {ex}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
