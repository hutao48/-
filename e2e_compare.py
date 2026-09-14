# -*- coding: utf-8 -*-
"""同一次运行：实时检测 + 存盘，随后离线重放对比"""
import time
import threading
import numpy as np
import winsound
import wave

from instruments import build_lyre21
from detection import NoteDetector
from audio_capture import AudioCapture, default_loopback_id
from e2e_test import make_wav

SR = 48000

if __name__ == "__main__":
    lyre = build_lyre21("风物之诗琴")
    events = [(60, 0.35), (60, 0.35), (67, 0.35), (67, 0.35),
              (69, 0.35), (69, 0.35), (67, 0.7),
              (65, 0.35), (65, 0.35), (64, 0.35), (64, 0.35),
              (62, 0.35), (62, 0.35), (60, 0.7)]
    wav = "e2e_twinkle.wav"
    make_wav(wav, events)

    threading.Thread(target=lambda: winsound.PlaySound(wav, winsound.SND_FILENAME),
                     daemon=True).start()
    time.sleep(0.3)

    det_live = NoteDetector(lyre, sr=SR, sensitivity=0.6)
    chunks = []
    live_evs = []
    with AudioCapture(device_id=default_loopback_id(), is_loopback=True) as cap:
        t0 = time.time()
        while time.time() - t0 < 7.0:
            b = cap.read_block()
            if b is None:
                continue
            chunks.append(b)
            live_evs.extend(det_live.feed(b)["note_events"])
    det_live.feed(np.zeros(SR, dtype=np.float32))

    print("== 实时检测 ==")
    for e in live_evs:
        print("  %6.2fs %s %-4s %6.0fms" % (e['t'], e['key'], e['name'], e['dur_ms']))

    audio = np.concatenate(chunks)
    with wave.open("e2e_capture2.wav", "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((audio * 32767).astype(np.int16).tobytes())

    print("== 离线重放同一段 ==")
    det_off = NoteDetector(lyre, sr=SR, sensitivity=0.6, sim_clock=True)
    off_evs = []
    off_evs.extend(det_off.feed(audio)["note_events"])
    off_evs.extend(det_off.feed(np.zeros(SR, dtype=np.float32))["note_events"])
    for e in off_evs:
        print("  %6.2fs %s %-4s %6.0fms" % (e['t'], e['key'], e['name'], e['dur_ms']))
