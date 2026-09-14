# -*- coding: utf-8 -*-
import wave, numpy as np
from instruments import build_lyre21
from detection import NoteDetector
wf = wave.open("v2_lowhigh.wav","rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr=48000
inst = build_lyre21("风物之诗琴")
det = NoteDetector(inst, sr=sr, sensitivity=0.55, sim_clock=True)

# 手动跑帧，打印 t=6-11s 的 midis
BLOCK=2048
for i in range(len(data)//BLOCK):
    blk = data[i*BLOCK:(i+1)*BLOCK]
    t = i * BLOCK / sr
    if 5.5 < t < 11.5:
        # 手动处理看 peaks
        frame = blk[:4096] if len(blk)>=4096 else None
        if frame is not None and len(frame)>=4096:
            r = det.feed(blk)
            events = r["note_events"]
            if events:
                for e in events:
                    print(f"t={e['t']:.2f} {e['key']}={e['name']} {e['dur_ms']:.0f}ms")
        else:
            det.feed(blk)
    else:
        det.feed(blk)
