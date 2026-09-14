# -*- coding: utf-8 -*-
"""闭环试音：录 N 秒回环 → 离线跑检测器 → 打印事件。
用法: python web_capture.py <秒数> <输出wav> [灵敏度]
"""
import sys
import time
import wave
import numpy as np
import soundcard as sc

from instruments import build_lyre21
from detection import NoteDetector

SR = 48000
BLOCK = 2048


def main():
    secs = float(sys.argv[1])
    out = sys.argv[2]
    sens = float(sys.argv[3]) if len(sys.argv) > 3 else 0.55

    mic = sc.get_microphone(id=str(sc.default_speaker().id), include_loopback=True)
    rec = mic.recorder(samplerate=SR, channels=2, blocksize=BLOCK)
    print(f"[capture] start {secs}s sens={sens}", flush=True)
    chunks = []
    t0 = time.time()
    with rec:
        while time.time() - t0 < secs:
            data = rec.record(numframes=BLOCK)
            chunks.append(np.asarray(data, dtype=np.float32).mean(axis=1))
    audio = np.concatenate(chunks)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    print(f"[capture] saved {len(audio)/SR:.2f}s -> {out}", flush=True)

    # 离线检测（sim_clock=True：按音频时长推进时间）
    inst = build_lyre21("风物之诗琴", 0)
    det = NoteDetector(inst, sr=SR, sensitivity=sens, sim_clock=True)
    all_events = []
    last = {}
    hop = BLOCK
    n_chunks = len(audio) // BLOCK
    for i in range(n_chunks):
        blk = audio[i * BLOCK:(i + 1) * BLOCK]
        last = det.feed(blk)
        all_events.extend(last.get("note_events", []))
    # 收尾：喂若干静音块，让长音关闭
    for _ in range(20):
        last = det.feed(np.zeros(BLOCK, dtype=np.float32))
        all_events.extend(last.get("note_events", []))
    print("===== 检测事件 =====")
    for ev in all_events:
        print(f"  t={ev['t']:6.2f}s  {ev['key']:>2}  {ev['name']:>4}  {ev['dur_ms']:.0f}ms")
    print(f"事件总数: {len(all_events)}  BPM: {last.get('bpm')}  调性: {last.get('tonality')}")


if __name__ == "__main__":
    main()
