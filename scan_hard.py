# -*- coding: utf-8 -*-
"""全音域扫描（困难版）：合成弱基频/强谐波音色，模拟真实拨弦乐器。
用法: python scan_hard.py [sens]
"""
import sys, numpy as np
from instruments import build_lyre21, midi_to_name
from detection import NoteDetector

SR = 48000
BLOCK = 2048
sens = float(sys.argv[1]) if len(sys.argv) > 1 else 0.55

inst = build_lyre21("风物之诗琴")
det = NoteDetector(inst, sr=SR, sensitivity=sens, sim_clock=True)

notes = inst.pitch_keys()
total_secs = len(notes) * 0.7
n_samples = int(total_secs * SR)
audio = np.zeros(n_samples, dtype=np.float32)

t = 0.0
expected = []
for label, midi, kind, extra in notes:
    freq = 440.0 * 2 ** ((midi - 69) / 12.0)
    dur = 0.5
    n = int(dur * SR)
    tt = np.arange(n) / SR
    env = np.exp(-tt * 3.5)
    # 困难音色：基频较弱，2/3次谐波较强（模拟低音拨弦的琴箱共振）
    sig = np.zeros(n)
    for h in range(1, 8):
        hf = freq * h
        if hf > 12000:
            break
        if h == 1:
            amp = 1.0
        elif h == 2:
            amp = 0.18  # 2次谐波（真实音色约15-20%）
        elif h == 3:
            amp = 0.10
        else:
            amp = 0.30 / h
        sig += amp * np.sin(2 * np.pi * hf * tt)
    sig *= env * 0.4
    start = int(t * SR)
    audio[start:start+n] += sig
    expected.append((t, label, midi_to_name(midi), midi))
    t += 0.7

events = []
for i in range(len(audio) // BLOCK):
    blk = audio[i*BLOCK:(i+1)*BLOCK]
    r = det.feed(blk)
    events.extend(r["note_events"])
for _ in range(20):
    r = det.feed(np.zeros(BLOCK, dtype=np.float32))
    events.extend(r["note_events"])

print(f"{'期望键':>4} {'期望音':>6} | {'检测键':>4} {'检测音':>6} {'时长ms':>7} {'判定'}")
print("-" * 55)
correct = wrong = missing = 0
for et, elabel, ename, emidi in expected:
    best = None
    for ev in events:
        if abs(ev["t"] - et) < 0.5:
            if best is None or abs(ev["t"] - et) < abs(best["t"] - et):
                best = ev
    if best is None:
        print(f"{elabel:>4} {ename:>6} | {'--':>4} {'--':>6} {'--':>7}  缺失")
        missing += 1
    else:
        ok = best["midi"] == emidi
        mark = "OK" if ok else "错!"
        if ok: correct += 1
        else: wrong += 1
        print(f"{elabel:>4} {ename:>6} | {best['key']:>4} {best['name']:>6} {best['dur_ms']:>7.0f}  {mark}")

print(f"\n正确 {correct}  错误 {wrong}  缺失 {missing}  / 共 {len(expected)}")
