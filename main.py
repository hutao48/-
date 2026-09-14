# -*- coding: utf-8 -*-
"""原神乐器演奏检测器 —— 程序入口"""
import os
import sys
import threading
import traceback


def _setup_logging():
    """将未捕获异常写入日志文件，便于排查问题"""
    try:
        log_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                               "GenshinInstrumentDetector")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "app.log")

        def hook(exc_type, exc_value, exc_tb):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("=" * 60 + "\n")
                f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
            sys.__excepthook__(exc_type, exc_value, exc_tb)

        sys.excepthook = hook

        def thread_hook(args):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("=" * 60 + "\n[工作线程异常]\n")
                f.write("".join(traceback.format_exception(args.exc_type, args.exc_value,
                                                           args.exc_traceback)))

        threading.excepthook = thread_hook
    except Exception:
        pass


def main():
    _setup_logging()
    from ui_main import main as ui_main
    ui_main()


if __name__ == "__main__":
    main()
