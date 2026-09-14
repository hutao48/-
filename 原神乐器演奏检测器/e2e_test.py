# -*- coding: utf-8 -*-
"""端到端测试：生成 WAV → 系统扬声器播放 → WASAPI 回环采集 → 检测
验证真实链路（含系统音量、混音、设备驱动等环节）。"""
import time
import threading
import numpy as np
import winsound

from instruments import build_lyre21, midi_to_name
from detection import NoteDetector
from audio_capture import AudioCapture, default_loopback_id

SR = 48000


def synth_note(midi, dur_s, sr=SR, amp=0.5, decay=4.0):
    f0 = 440.0 * 2 ** ((midi - 69) / 12.0)
    t = np.arange(int(dur_s * sr)) / sr
    env = np.exp(-decay * t)
    sig = np.zeros_like(t)
    for k, a in [(1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1)]:
        sig += a * np.sin(2 * np.pi * f0 * k * t)
    return (amp * sig * env).astype(np.float32)


def make_wav(path, events, gap=0.02, amp=0.35):
    chunks = []
    for notes, dur in events:
        if isinstance(notes, int):
            notes = [notes]
        n = max(len(synth_note(m, dur, amp=amp)) for m in notes)
        mix = np.zeros(n, dtype=np.float32)
        for m in notes:
            s = synth_note(m, dur, amp=amp)
            mix[:len(s)] += s
        chunks.append(mix)
        chunks.append(np.zeros(int(gap * SR), dtype=np.float32))
    audio = np.concatenate(chunks)
    pcm = (audio * 32767).astype(np.int16)
    import wave
    with wave.open(path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    return audio


if __name__ == "__main__":
    lyre = build_lyre21("风物之诗琴")
    # 小星星：C C G G A A G(长) | F F E E D D C(长)
    events = [(60, 0.35), (60, 0.35), (67, 0.35), (67, 0.35),
              (69, 0.35), (69, 0.35), (67, 0.7),
              (65, 0.35), (65, 0.35), (64, 0.35), (64, 0.35),
              (62, 0.35), (62, 0.35), (60, 0.7)]
    wav = "e2e_twinkle.wav"
    total = make_wav(wav, events)

    # 后台线程播放
    def play():
        winsound.PlaySound(wav, winsound.SND_FILENAME)

    t = threading.Thread(target=play, daemon=True)
    t.start()
    time.sleep(0.3)  # 等播放器就绪

    det = NoteDetector(lyre, sr=SR, sensitivity=0.6)
    dev = default_loopback_id()
    print("回环设备:", dev)
    found = []
    with AudioCapture(device_id=dev, is_loopback=True) as cap:
        t0 = time.time()
        while time.time() - t0 < len(total) / SR + 1.5:
            block = cap.read_block()
            if block is None:
                continue
            res = det.feed(block)
            found.extend(res["note_events"])
    # 释放残留
    det.feed(np.zeros(SR, dtype=np.float32))

    print("检测到", len(found), "个音符:")
    for ev in found:
        print(f"  {ev['t']:6.2f}s  键 {ev['key']}  {ev['name']:<4} {ev['dur_ms']:6.0f} ms")
    print("BPM:", det._current_bpm())
    print("调性:", det._current_tonality_text())
