# -*- coding: utf-8 -*-
"""
音频采集：WASAPI 回环（监听扬声器输出，可检测本机任何应用播放的声音）
+ 物理麦克风（可检测其他设备/外部声源）。
基于 soundcard 库（MediaFoundation WASAPI）。
"""
import soundcard as sc
import numpy as np

SAMPLE_RATE = 48000
BLOCK = 2048


def list_sources():
    """返回 [(id, name, is_loopback), ...] 可采集设备：
    优先列出各扬声器的回环（扬声器输出），再列出麦克风。"""
    sources = []
    seen = set()
    try:
        for mic in sc.all_microphones(include_loopback=True):
            if mic.id not in seen:
                seen.add(mic.id)
                sources.append((mic.id, mic.name, "loopback" if "loopback" in str(mic).lower() else "mic"))
    except Exception:
        pass
    return sources


def default_loopback_id():
    """默认输出设备对应的回环采集 id"""
    try:
        mic = sc.get_microphone(id=str(sc.default_speaker().id), include_loopback=True)
        return mic.id
    except Exception:
        return None


class AudioCapture:
    """包装 soundcard 采集：with 用法，逐块返回单声道 float32"""

    def __init__(self, device_id=None, is_loopback=True):
        self.device_id = device_id
        self.is_loopback = is_loopback
        self._recorder = None

    def open(self):
        if self.device_id:
            mic = sc.get_microphone(id=self.device_id, include_loopback=True)
        else:
            mic = sc.default_microphone()
        self._recorder = mic.recorder(samplerate=SAMPLE_RATE, channels=2, blocksize=BLOCK)
        self._recorder.__enter__()
        return self

    def close(self):
        if self._recorder is not None:
            try:
                self._recorder.__exit__(None, None, None)
            except Exception:
                pass
            self._recorder = None

    def read_block(self):
        """读取一块音频，返回单声道 float32 (BLOCK,)，失败返回 None"""
        try:
            data = self._recorder.record(numframes=BLOCK)
            if data is None:
                return None
            data = np.asarray(data, dtype=np.float32)
            if data.ndim == 2 and data.shape[1] >= 1:
                data = data.mean(axis=1)
            if data.size == 0:
                return None
            return data.astype(np.float32)
        except Exception:
            return None

    def __enter__(self):
        return self.open()

    def __exit__(self, *a):
        self.close()
