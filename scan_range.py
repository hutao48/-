# -*- coding: utf-8 -*-
"""全音域扫描测试：合成 C3~B5 每个白键音，看检测器识别成什么键。
用法: python scan_range.py [sens]
"""
import sys, numpy as np, wave
from instruments import build_lyre21, midi_to_name
from detection import NoteDetector

SR = 48000
BLOCK = 2048
sens = float(sys.argv[1]) if len(sys.argv) > 1 else 0.55

inst = build_lyre21("风物之诗琴")
det = NoteDetector(inst, sr=SR, sensitivity=sens, sim_clock=True)

# 生成全音域每个音，每个音持续 0.5s，间隔 0.2s
notes = inst.pitch_keys()  # [(label, midi, kind, extra)]
total_secs = len(notes) * 0.7
n_samples = int(total_secs * SR)
audio = np.zeros(n_samples, dtype=np.float32)

t = 0.0
expected = []
for label, midi, kind, extra in notes:
    freq = 440.0 * 2 ** ((midi - 69) / 12.0)
    # 合成拨弦音色：基频 + 衰减谐波
    dur = 0.5
    n = int(dur * SR)
    tt = np.arange(n) / SR
    # 指数衰减包络
    env = np.exp(-tt * 3.5)
    # 谐波叠加（模拟拨弦：奇次强，偶次弱）
    sig = np.zeros(n)
    for h in range(1, 8):
        hf = freq * h
        if hf > 12000:
            break
        amp = 1.0 / (h ** 1.3)
        sig += amp * np.sin(2 * np.pi * hf * tt)
    sig *= env * 0.5
    start = int(t * SR)
    audio[start:start+n] += sig
    expected.append((t, label, midi_to_name(midi), label, midi))
    t += 0.7

# 离线检测
events = []
for i in range(len(audio) // BLOCK):
    blk = audio[i*BLOCK:(i+1)*BLOCK]
    r = det.feed(blk)
    events.extend(r["note_events"])
for _ in range(20):
    r = det.feed(np.zeros(BLOCK, dtype=np.float32))
    events.extend(r["note_events"])

# 对比：每个期望音，找时间最接近的检测事件
print(f"{'期望键':>4} {'期望音':>6} | {'检测键':>4} {'检测音':>6} {'时长ms':>7} {'时间偏差':>7} {'判定'}")
print("-" * 60)
correct = 0
wrong = 0
missing = 0
for et, elabel, ename, _, emidi in expected:
    # 找时间在 et±0.5s 内的事件
    best = None
    for ev in events:
        if abs(ev["t"] - et) < 0.5:
            if best is None or abs(ev["t"] - et) < abs(best["t"] - et):
                best = ev
    if best is None:
        print(f"{elabel:>4} {ename:>6} | {'--':>4} {'--':>6} {'--':>7} {'--':>7}  缺失")
        missing += 1
    else:
        ok = best["midi"] == emidi
        mark = "OK" if ok else "错!"
        if ok:
            correct += 1
        else:
            wrong += 1
        dt = (best["t"] - et) * 1000
        print(f"{elabel:>4} {ename:>6} | {best['key']:>4} {best['name']:>6} {best['dur_ms']:>7.0f} {dt:>+6.0f}ms  {mark}")

print(f"\n正确 {correct}  错误 {wrong}  缺失 {missing}  / 共 {len(expected)}")
