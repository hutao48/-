# -*- coding: utf-8 -*-
"""可选诊断日志：设置环境变量 GID_DEBUG=1 后，将运行状态写入 app.log 便于排查。"""
import os
import threading

_LOCK = threading.Lock()


def dbg(msg):
    if not os.environ.get("GID_DEBUG"):
        return
    try:
        log_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                               "GenshinInstrumentDetector")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "app.log")
        with _LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"[DBG] {msg}\n")
    except Exception:
        pass
