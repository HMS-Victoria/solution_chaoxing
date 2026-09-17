# -*- coding: utf-8 -*-
"""输入到光标 —— 把一段文本当成键盘输入，打到你鼠标光标所在的输入框里。

网页禁止粘贴，拦的是 paste 事件。本工具用 SendInput + KEYEVENTF_UNICODE 在
操作系统层注入按键：浏览器收到的是普通键盘输入（不产生 paste 事件，且
event.isTrusted 为 true），所以对"禁止粘贴"的输入框一样有效。中文和 emoji
直接送 Unicode 码点，不需要输入法。

用法：把文本粘到窗口里（本工具自己不拦粘贴）→ 点一下目标输入框 → 按 F8。
自检：py -3.9 type_at_cursor.pyw --selftest
"""

import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

# ----------------------------------------------------------------- Win32 定义

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_F8 = 0x77

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    # Union 里必须带上 MOUSEINPUT：它是最大的成员，决定了 x64 下 INPUT == 40 字节。
    # 少写一个成员会让 sizeof(INPUT) 变小，SendInput 直接返回 0 且不报错。
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wintypes.HWND  # 不设 restype 会被截成 32 位
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD


# ----------------------------------------------------------------- 纯函数部分

def normalize(text):
    """统一换行，否则 \\r\\n 会被当成两次回车。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def units(ch):
    """字符 → UTF-16 码元序列（非 BMP 字符自动拆成代理对）。"""
    b = ch.encode("utf-16-le")
    return tuple(int.from_bytes(b[i:i + 2], "little") for i in range(0, len(b), 2))


def _uni_key(unit, up):
    return INPUT(type=INPUT_KEYBOARD,
                 u=_INPUTUNION(ki=KEYBDINPUT(wVk=0, wScan=unit,
                                             dwFlags=KEYEVENTF_UNICODE
                                                     | (KEYEVENTF_KEYUP if up else 0),
                                             time=0, dwExtraInfo=0)))


def _vk_key(vk, up):
    return INPUT(type=INPUT_KEYBOARD,
                 u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=0,
                                             dwFlags=(KEYEVENTF_KEYUP if up else 0),
                                             time=0, dwExtraInfo=0)))


def key_events(ch, enter_for_newline=True):
    """一个字符 → 一串按键事件（按下+抬起放在同一次 SendInput 里提交）。"""
    if ch == "\n":
        # 浏览器 textarea 只认回车键，直接发 Unicode 的 \\n 经常被丢掉
        return [_vk_key(VK_RETURN, False), _vk_key(VK_RETURN, True)] if enter_for_newline else []
    out = []
    for unit in units(ch):
        out.append(_uni_key(unit, False))
        out.append(_uni_key(unit, True))
    return out


def send(events):
    """返回成功注入的事件数；0 表示被系统拒绝（多半是 UIPI：目标窗口是管理员权限）。"""
    if not events:
        return 0
    array = (INPUT * len(events))(*events)
    return user32.SendInput(len(events), array, ctypes.sizeof(INPUT))


def foreground_pid():
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


def selftest():
    expect = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(INPUT) == expect, "sizeof(INPUT)=%d，应为 %d" % (ctypes.sizeof(INPUT), expect)
    assert units("A") == (0x41,)
    assert units("中") == (0x4E2D,)
    assert units("\U0001F600") == (0xD83D, 0xDE00)
    assert normalize("a\r\nb\rc\n") == "a\nb\nc\n"
    assert len(key_events("\n")) == 2
    assert key_events("\n", enter_for_newline=False) == []
    assert len(key_events("\U0001F600")) == 4
    assert len(key_events("A")) == 2
    print("ok")


# ------------------------------------------------------------------- 界面部分

tk = None  # 延迟导入，见 main()：tkinter 缺失时也要能把错误弹出来


class App:
    def __init__(self, root):
        self.root = root
        self._msg = None          # 子线程 → 主线程只通过这两个标志传话
        self._finish = False      # （子线程绝不碰控件，Tk 不是线程安全的）
        self._busy = False
        self._hotkey_down = False
        self._stop = threading.Event()

        root.title("输入到光标")
        root.minsize(560, 400)

        top = tk.Frame(root)
        top.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        self.text = tk.Text(top, wrap="word", undo=True, height=12)
        bar = tk.Scrollbar(top, command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        self.text.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.text.bind("<Control-a>", self._select_all)
        self.text.focus_set()

        opts = tk.Frame(root)
        opts.pack(fill="x", padx=10)
        tk.Label(opts, text="倒计时").pack(side="left")
        self.delay = tk.Spinbox(opts, from_=0, to=10, width=4)
        self.delay.pack(side="left", padx=(4, 2))
        tk.Label(opts, text="秒").pack(side="left")
        tk.Label(opts, text="每字符间隔").pack(side="left", padx=(16, 0))
        self.interval = tk.Spinbox(opts, from_=0, to=200, increment=5, width=5)
        self.interval.pack(side="left", padx=(4, 2))
        tk.Label(opts, text="毫秒").pack(side="left")
        self.enter_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="换行按回车", variable=self.enter_var).pack(side="left", padx=(16, 0))
        self.delay.delete(0, "end")
        self.delay.insert(0, "3")
        self.interval.delete(0, "end")
        self.interval.insert(0, "25")

        row = tk.Frame(root)
        row.pack(fill="x", padx=10, pady=(8, 4))
        self.start_btn = tk.Button(row, text="开始输入", width=12, command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = tk.Button(row, text="停止", width=8, state="disabled",
                                  command=self._stop_clicked)
        self.stop_btn.pack(side="left", padx=6)
        tk.Button(row, text="清空", width=8,
                  command=lambda: self.text.delete("1.0", "end")).pack(side="left")
        self.status = tk.Label(row, text="把文本粘进来，然后按 F8", anchor="w")
        self.status.pack(side="left", padx=12)

        tk.Label(root, justify="left", fg="#555",
                 text="用法：把文本粘到上面的框里（本工具自己不拦粘贴）→  点一下目标输入框  →  按 F8。\n"
                      "F8 是全局的，不用切窗口；本窗口自己有焦点时不触发，免得把字打进自己。"
                 ).pack(fill="x", padx=10, pady=(0, 10))

        self._pump()

    # ---- 主线程：每 80ms 收一次子线程的消息，顺便查 F8 ----
    def _pump(self):
        if self._msg is not None:
            self.status.config(text=self._msg)
            self._msg = None
        if self._finish:
            self._finish = False
            self._busy = False
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
        self._poll_hotkey()
        self.root.after(80, self._pump)

    def _post(self, msg):
        self._msg = msg

    def _select_all(self, _event):
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _num(self, spinbox, default):
        try:
            return float(spinbox.get())
        except (ValueError, TypeError):
            return default

    def _poll_hotkey(self):
        # ponytail: 轮询而不是键盘钩子，代价是 F8 仍会被前台程序收到（浏览器里 F8
        # 没有默认行为，无妨）。真需要吞掉这个键，再换 WH_KEYBOARD_LL + 消息循环。
        down = bool(user32.GetAsyncKeyState(VK_F8) & 0x8000)
        if down and not self._hotkey_down:
            self._hotkey_down = True
            if not self._busy:
                if foreground_pid() == os.getpid():
                    self._post("本窗口有焦点，请先点一下目标输入框再按 F8")
                else:
                    self._start(0.6)
        elif not down:
            self._hotkey_down = False

    def _start(self, delay=None):
        if self._busy:
            return
        text = normalize(self.text.get("1.0", "end-1c"))  # end-1c：Tk 永远多给一个换行
        if not text:
            self._post("文本框是空的")
            return
        if delay is None:
            delay = self._num(self.delay, 3.0)
        interval = max(0.0, self._num(self.interval, 25.0)) / 1000.0
        enter = bool(self.enter_var.get())
        self._stop.clear()
        self._busy = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        threading.Thread(target=self._run, args=(text, delay, interval, enter),
                         daemon=True).start()

    def _stop_clicked(self):
        self._stop.set()
        self._post("正在停止…")

    # ---- 子线程：倒计时 + 注入，绝不直接碰控件 ----
    def _run(self, text, delay, interval, enter):
        try:
            remain = delay
            while remain > 0 and not self._stop.is_set():
                time.sleep(min(0.1, remain))
                remain -= 0.1
                self._post("%.0f 秒后开始输入…" % max(remain, 0))
            if self._stop.is_set():
                self._post("已取消")
                return
            if foreground_pid() == os.getpid():
                self._post("焦点还在本工具上，已取消：请先点一下目标输入框，或用 F8")
                return
            total = len(text)
            for i, ch in enumerate(text, 1):
                if self._stop.is_set():
                    self._post("已中止（%d/%d）" % (i - 1, total))
                    return
                if send(key_events(ch, enter)) == 0:
                    self._post("输入被系统拒绝（错误 %d）：目标窗口可能以管理员身份运行，"
                               "请以管理员身份重新启动本工具" % ctypes.get_last_error())
                    return
                if interval >= 0.01 or i == total or i % 20 == 0:
                    self._post("已输入 %d/%d" % (i, total))
                if interval:
                    time.sleep(interval)
            self._post("完成：已输入 %d 个字符" % total)
        except Exception as exc:
            self._post("出错：%r" % (exc,))
        finally:
            self._finish = True


def main():
    global tk
    if "--selftest" in sys.argv:
        selftest()
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 高分屏下别糊
    except Exception:
        pass
    import tkinter
    tk = tkinter
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # pythonw 没有控制台，崩溃必须能看见，否则就是"双击没反应"
        import tempfile
        import traceback
        path = os.path.join(tempfile.gettempdir(), "type_at_cursor.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        ctypes.windll.user32.MessageBoxW(None, "启动失败，详情见：\n" + path, "输入到光标", 0x10)
        raise
