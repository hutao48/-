import wave, numpy as np
from instruments import build_lyre21
from detection import NoteDetector

wf = wave.open("web_test6.wav", "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000
BLOCK = 2048

det = NoteDetector(build_lyre21("风物之诗琴"), sr=sr, sensitivity=0.55, sim_clock=True)
# 包一层打印
orig = det._process_frame
def wrapped(frame, t):
    res = orig(frame, t)
    if res.get("note_events") or det.active:
        keys = res.get("keys", {})
        evs = res.get("note_events", [])
        if evs:
            for e in evs:
                print(f"  {t:.2f}s EVENT {e['key']} {e['name']} {e['dur_ms']:.0f}ms")
    return res
det._process_frame = wrapped

n = len(data)//BLOCK
for i in range(n):
    det.feed(data[i*BLOCK:(i+1)*BLOCK])
for _ in range(30):
    det.feed(np.zeros(BLOCK, dtype=np.float32))
print("done")
