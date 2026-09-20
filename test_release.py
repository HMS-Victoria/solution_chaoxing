"""Offline regression: no real input is sent; real desktop acceptance is separate."""
import os
from pathlib import Path
import runpy
import threading
from unittest.mock import patch


module = runpy.run_path(str(Path(__file__).with_name("type_at_cursor.pyw")))
App = module["App"]
globals_ = App._run.__globals__


def run(text, enter=True, sent=None, pid=None, stopped=False):
    app = App.__new__(App)
    app._stop = threading.Event()
    if stopped:
        app._stop.set()
    app._finish = False
    app._msg = None
    app._msg_lock = threading.Lock()
    batches = []
    def fake_send(events):
        batches.append(events)
        return len(events) if sent is None else sent
    with patch.dict(globals_, send=fake_send,
                    foreground_pid=lambda: os.getpid() + 1 if pid is None else pid):
        app._run(text, 0, 0, enter)
    assert app._finish
    return app._msg, batches


module["selftest"]()
msg, events = run("中\n😀")
assert msg == "完成：已输入 3 个字符" and [len(e) for e in events] == [2, 2, 4]
msg, events = run("中\n😀", enter=False)
assert msg == "完成：已输入 3 个字符" and [len(e) for e in events] == [2, 4]
assert "系统拒绝" in run("😀", sent=1)[0]
assert "系统拒绝" in run("中", sent=0)[0]
msg, events = run("不应发送", pid=os.getpid())
assert "已取消" in msg and not events
msg, events = run("不应发送", stopped=True)
assert msg == "已取消" and not events
print("PASS: Unicode, newline skip, partial/rejected input, own-window guard, cancellation")

# A worker update arriving while Tk renders the previous message must survive.
from types import SimpleNamespace
app = App.__new__(App)
app._msg_lock = threading.Lock()
app._msg = "countdown"
app._finish = False
app.status = SimpleNamespace(config=lambda **kwargs: app._post("completed"))
app.root = SimpleNamespace(after=lambda *args: None)
app._poll_hotkey = lambda: None
app._pump()
assert app._msg == "completed"
print("PASS: worker completion/stop status survives concurrent UI render")