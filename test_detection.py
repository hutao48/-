# -*- coding: utf-8 -*-
"""用合成音频验证检测引擎：音符、音长、BPM、调性、和弦"""
import time
import numpy as np
from instruments import build_lyre21, build_horn, build_youko, midi_to_name
from detection import NoteDetector

SR = 48000


def synth_note(midi, dur_s, sr=SR, amp=0.5, decay=4.0):
    """模拟拨弦音：基频 + 前几个谐波 + 指数衰减"""
    f0 = 440.0 * 2 ** ((midi - 69) / 12.0)
    t = np.arange(int(dur_s * sr)) / sr
    env = np.exp(-decay * t)
    sig = np.zeros_like(t)
    for k, a in [(1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1)]:
        sig += a * np.sin(2 * np.pi * f0 * k * t)
    return (amp * sig * env).astype(np.float32)


def play_sequence(events, sr=SR):
    """events: [(midi_or_list, dur_s)] → 连续音频（每音间隔 gap）"""
    gap = 0.02
    chunks = []
    for notes, dur in events:
        if isinstance(notes, int):
            notes = [notes]
        n = max(len(synth_note(m, dur)) for m in notes)
        mix = np.zeros(n, dtype=np.float32)
        for m in notes:
            s = synth_note(m, dur)
            mix[:len(s)] += s
        g = np.zeros(int(gap * sr), dtype=np.float32)
        chunks += [mix, g]
    return np.concatenate(chunks)


def run_test(name, inst, events, expect=None):
    det = NoteDetector(inst, sr=SR, sensitivity=0.6, sim_clock=True)
    audio = play_sequence(events)
    notes_detected = []
    bpm_vals = []
    # 分块喂入
    block = 2048
    for i in range(0, len(audio) - block, block):
        res = det.feed(audio[i:i + block])
        for ev in res["note_events"]:
            notes_detected.append(ev)
        if res["bpm"]:
            bpm_vals.append(res["bpm"])
    # 收尾（喂足够静音让所有音符落音）
    res = det.feed(np.zeros(int(1.0 * SR), dtype=np.float32))
    for ev in res["note_events"]:
        notes_detected.append(ev)

    print(f"\n===== {name} =====")
    seq = " ".join(f"{ev['key']}({ev['name']},{ev['dur_ms']:.0f}ms)" for ev in notes_detected)
    print("检测到的音符序列:", seq[:400])
    if bpm_vals:
        print(f"BPM 估计: {bpm_vals[-1]:.1f} (期望 {expect.get('bpm') if expect else '?'})")
    else:
        print("BPM 估计: 无")
    print("调性:", det._current_tonality_text())
    return notes_detected, bpm_vals


if __name__ == "__main__":
    # ---- 风物之诗琴：C大调 小星星 120BPM（四分音符 0.5s）
    lyre = build_lyre21("风物之诗琴")
    # C4 D4 E4 C4 | C4 D4 E4 C4 | E4 F4 G4 _ | ...
    ev = []
    for midi in [60, 62, 64, 60, 60, 62, 64, 60, 64, 65, 67]:
        ev.append((midi, 0.45))
    run_test("风物之诗琴 小星星(120BPM)", lyre, ev, {"bpm": 120})

    # ---- 和弦测试：悠可琴 C 和弦键
    youko = build_youko()
    ev = [([60, 64, 67], 0.6), ([57, 60, 64], 0.6), ([62, 65, 69], 0.6)]
    run_test("悠可琴 三和弦(C, Am, Dm)", youko, ev)

    # ---- 调性测试：A 小调旋律（A G F E D E G）
    ev = [(69, 0.4), (67, 0.4), (65, 0.4), (64, 0.4), (62, 0.4), (64, 0.4), (67, 0.8)]
    run_test("A小调音阶片段", lyre, ev)

    # ---- 晚风圆号测试
    horn = build_horn()
    ev = [(72, 0.3), (74, 0.3), (76, 0.3), (77, 0.3), (79, 0.3), (77, 0.3), (76, 0.3), (74, 0.3)]
    run_test("晚风圆号 上行+下行(约160BPM)", horn, ev, {"bpm": 160})

    # ---- BPM 精确测试：120BPM 八分音符
    ev = [(60, 0.18)] * 24  # 八分音符 0.25s → 240BPM；用 0.18s 音长+间隔≈0.25s
    # 实际我们每音间隔 0.02s，音长 0.18s → 起音间隔 0.2s → 300BPM（超范围）→ 换 0.42s 音长
    ev = [(60, 0.42)] * 12  # 起音间隔 0.44s ≈ 136BPM
    run_test("BPM=136 长音测试", lyre, ev, {"bpm": 136})
