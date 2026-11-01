"""Windows-only live target inspection, pointer and click-through highlight.

No remote control: user always clicks. Screenshot is only sent to loopback Ollama.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import io
import queue
import sys
import threading
import time

IS_WINDOWS=sys.platform=='win32'

def windows_only():
    if not IS_WINDOWS:
        raise RuntimeError('Live desktop guidance is supported on Windows only.')

def enable_dpi():
    if not IS_WINDOWS:return
    try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:ctypes.windll.user32.SetProcessDPIAware()
        except Exception:pass


def foreground_info():
    windows_only()
    user=ctypes.windll.user32
    user.GetForegroundWindow.restype=wintypes.HWND
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    hwnd=user.GetForegroundWindow()
    if not hwnd:raise RuntimeError('No foreground window found. Open the application and retry.')
    rect=wintypes.RECT()
    if not user.GetWindowRect(hwnd,ctypes.byref(rect)):
        raise RuntimeError('Could not read window bounds.')
    if rect.right-rect.left<100 or rect.bottom-rect.top<90:
        raise RuntimeError('Selected application window is too small. Maximize it and retry.')
    buf=ctypes.create_unicode_buffer(500)
    user.GetWindowTextW(hwnd,buf,len(buf))
    title=buf.value
    if 'kiko' in title.casefold() and any(x in title.casefold() for x in ('chrome','edge','—',' - ')):
        raise RuntimeError('KIKO is in front. Switch to the app you want help with, then press Ctrl+Alt+K.')
    return hwnd,title,(rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top)


def snapshot(bounds, hwnd=None):
    """Capture the selected window, not the KIKO browser sitting in front.

    Pillow 11.2+ supports grabbing a HWND on Windows. If that backend cannot
    capture a custom fullscreen window, fall back to visible-screen capture;
    the UI must never pretend this fallback is the requested window.
    """
    windows_only()
    from PIL import ImageGrab
    x,y,w,h=bounds
    img=None
    if hwnd:
        try:
            img=ImageGrab.grab(window=int(hwnd))
            if img.width<80 or img.height<80 or abs(img.width/w-img.height/h)>1.5:
                img=None
        except (OSError,ValueError,TypeError):
            img=None
    if img is None:
        # If KIKO is foreground, a normal screenshot could show the browser,
        # not the requested app. Fail clearly rather than generate wrong clicks.
        try:
            active, title, _=foreground_info()
            if hwnd and active!=hwnd and is_kiko_browser(title):
                raise RuntimeError('This app cannot be captured while KIKO is in front. Switch to the app and press Ctrl+Alt+K once.')
        except RuntimeError:
            raise
        img=ImageGrab.grab(bbox=(x,y,x+w,y+h),all_screens=True)
    # max-size preserves the screen's aspect ratio. Model coordinates normalized to 0..1000.
    img.thumbnail((1060,790))
    stream=io.BytesIO()
    img.convert('RGB').save(stream,format='JPEG',quality=70,optimize=True)
    return stream.getvalue()


def accessible_controls(hwnd, bounds, limit=200):
    windows_only()
    try:import uiautomation as auto
    except ImportError:return []
    try:root=auto.ControlFromHandle(hwnd)
    except Exception:return []
    controls=[]
    stack=[(root,0)]
    left,top,width,height=bounds
    while stack and len(controls)<limit:
        obj,depth=stack.pop()
        try:
            if bool(getattr(obj,'IsPassword',False)):continue
            name=(obj.Name or '').strip()
            ctype=(obj.ControlTypeName or '')
            rect=obj.BoundingRectangle
            x,y,w,h=int(rect.left),int(rect.top),int(rect.right-rect.left),int(rect.bottom-rect.top)
            if name and w>5 and h>5 and x>=left-20 and y>=top-20 and x+w<=left+width+20 and y+h<=top+height+20:
                controls.append(dict(id=len(controls)+1,name=name[:90],type=ctype[:55],rect=(x,y,w,h)))
            if depth<7:
                # Avoid blocking forever on poorly-behaved apps.
                children=obj.GetChildren()
                stack.extend((c,depth+1) for c in reversed(children[:45]))
        except Exception:continue
    return controls


def move_pointer(x,y):
    windows_only()
    u=ctypes.windll.user32
    if not u.SetCursorPos(int(x),int(y)):
        raise RuntimeError('Windows refused to move the pointer.')

class Highlight:
    """A click-through ring shown above the target for ~12 seconds.

    If Tk cannot render a transparent overlay, moving the pointer still works.
    """
    def __init__(self):
        self.queue=queue.Queue()
        self.started=False
    def start(self):
        if not IS_WINDOWS or self.started:return
        self.started=True
        threading.Thread(target=self._loop,daemon=True,name='KIKO overlay').start()
    def show(self,x,y,rect=None):
        self.start()
        self.queue.put((int(x),int(y),rect))
    def _loop(self):
        try:
            import tkinter as tk
            root=tk.Tk()
            root.withdraw()
            bg='#090909'
            win=tk.Toplevel(root)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes('-topmost',True)
            win.attributes('-transparentcolor',bg)
            canvas=tk.Canvas(win,bg=bg,highlightthickness=0,bd=0)
            canvas.pack(fill='both',expand=True)
            expiry=[0]
            def poll():
                try:
                    while True:
                        x,y,rect=self.queue.get_nowait()
                        radius=48
                        # Use SetWindowPos for correct negative monitor coordinates.
                        win.geometry(f'{radius*2}x{radius*2}+100+100')
                        win.update_idletasks()
                        hwnd=win.winfo_id()
                        user=ctypes.windll.user32
                        user.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int]
                        user.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_long]
                        user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
                        ex=user.GetWindowLongW(hwnd,-20)
                        user.SetWindowLongW(hwnd,-20,ex|0x20|0x80)  # click-through, tool window
                        win.deiconify()
                        user.SetWindowPos(hwnd,-1,x-radius,y-radius,radius*2,radius*2,0x0010)
                        canvas.delete('all')
                        canvas.create_oval(7,7,89,89,outline='#C7FF3D',width=7)
                        canvas.create_oval(21,21,75,75,outline='#6D4CFF',width=3)
                        canvas.create_text(48,48,text='+',fill='#C7FF3D',font=('Arial',22,'bold'))
                        expiry[0]=time.monotonic()+12
                except queue.Empty:pass
                if expiry[0] and time.monotonic()>expiry[0]:
                    win.withdraw();expiry[0]=0
                root.after(110,poll)
            root.after(110,poll)
            root.mainloop()
        except Exception as e:
            print('Overlay unavailable; pointer movement still works:',str(e)[:120],flush=True)


def hotkey_loop(on_press, ready_callback=None):
    """Register Ctrl+Alt+K globally on the background thread."""
    if not IS_WINDOWS:return
    user=ctypes.windll.user32
    MOD_ALT,MOD_CONTROL=1,2
    VK_K=ord('K')
    registered=bool(user.RegisterHotKey(None,351,MOD_ALT|MOD_CONTROL,VK_K))
    if ready_callback:ready_callback(registered)
    if not registered:
        print('Hotkey unavailable: use Capture in 3 seconds in the KIKO browser.',flush=True)
        return
    try:
        msg=wintypes.MSG()
        while user.GetMessageW(ctypes.byref(msg),None,0,0)>0:
            if msg.message==0x0312 and msg.wParam==351:
                on_press()
            user.TranslateMessage(ctypes.byref(msg))
            user.DispatchMessageW(ctypes.byref(msg))
    finally:user.UnregisterHotKey(None,351)


def window_info(hwnd):
    """Read the bounds of a specified HWND; does not require it to have focus."""
    windows_only()
    user = ctypes.windll.user32
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindow.argtypes = [wintypes.HWND]
    if not hwnd or not user.IsWindow(hwnd):
        raise RuntimeError('The selected window closed. Try again.')
    rect = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError('Could not locate the window on screen.')
    title = ctypes.create_unicode_buffer(512)
    user.GetWindowTextW(hwnd, title, len(title))
    bounds = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    if bounds[2] < 100 or bounds[3] < 90:
        raise RuntimeError('The window is minimized or too small to guide. Restore it first.')
    return hwnd, title.value, bounds


def list_visible_windows():
    """Top-level visible windows; used to locate Settings without an app picker."""
    if not IS_WINDOWS:
        return []
    user = ctypes.windll.user32
    CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [CALLBACK, wintypes.LPARAM]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    found = []
    @CALLBACK
    def visit(hwnd, _):
        if user.IsWindowVisible(hwnd) and user.GetWindowTextLengthW(hwnd) > 0:
            try:
                item = window_info(hwnd)
                if item[2][2] > 240 and item[2][3] > 160:
                    found.append(item)
            except (RuntimeError, OSError):
                pass
        return True
    user.EnumWindows(visit, 0)
    return found


def find_settings_window(topic=None):
    """Prefer Settings windows matching the requested page; fall back to Settings."""
    windows_only()
    desired = {
        'bluetooth': ('bluetooth',), 'wifi': ('wi-fi', 'network'),
        'text': ('text size', 'accessibility'), 'display': ('display',),
        'sound': ('sound',), 'mouse': ('mouse',), 'notifications': ('notifications',)
    }.get(topic, ())
    candidates = []
    for hwnd, title, bounds in list_visible_windows():
        name = title.casefold()
        score = (12 if 'settings' in name else 0) + (7 if any(x in name for x in desired) else 0)
        if score:
            candidates.append((score, hwnd, title, bounds))
    candidates.sort(reverse=True, key=lambda x: x[0])
    return candidates[0][1:] if candidates else None


def is_kiko_browser(title):
    name = title.casefold()
    return ('kiko' in name and any(x in name for x in ('chrome', 'edge', 'brave', 'firefox', '—', ' - ')))


def raise_for_guidance(hwnd):
    """Bring an explicitly requested app to the top; never force keyboard input."""
    windows_only()
    user = ctypes.windll.user32
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user.ShowWindow(hwnd, 9)  # SW_RESTORE
    flags = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
    user.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, flags)  # TOPMOST briefly
    user.SetWindowPos(hwnd, wintypes.HWND(-2), 0, 0, 0, 0, flags)  # NOTOPMOST afterwards


def mouse_is_down():
    if not IS_WINDOWS: return False
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)


def cursor_position():
    windows_only()
    pos = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pos)):
        return None
    return int(pos.x), int(pos.y)


def find_app_window(app_name: str):
    """Best matching visible top-level window by installed app display name.

    UIA inspection uses this HWND and does not need the browser tab to be foreground.
    """
    if not IS_WINDOWS or not app_name:
        return None
    import difflib
    name=app_name.casefold().strip()
    candidates=[]
    for hwnd,title,bounds in list_visible_windows():
        if is_kiko_browser(title):continue
        low=title.casefold().strip()
        if not low:continue
        ratio=difflib.SequenceMatcher(None,name,low).ratio()
        score = (1.0 if name == low else .88 if name in low else .83 if low in name else ratio*.7)
        if score >= .56: candidates.append((score,hwnd,title,bounds))
    if not candidates: return None
    candidates.sort(key=lambda x:x[0],reverse=True)
    return candidates[0][1:]
