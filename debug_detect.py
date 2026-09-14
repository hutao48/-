import wave, numpy as np
from instruments import build_lyre21
from detection import NoteDetector

wf = wave.open("web_test6.wav", "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000
BLOCK = 2048

det = NoteDetector(build_lyre21("风物之诗琴"), sr=sr, sensitivity=0.55, sim_clock=True)
events = []
n = len(data)//BLOCK
for i in range(n):
    blk = data[i*BLOCK:(i+1)*BLOCK]
    res = det.feed(blk)
    for ev in res["note_events"]:
        print(f"EVENT t={ev['t']:.2f} key={ev['key']} name={ev['name']} midi={ev.get('midi','?')} dur={ev['dur_ms']:.0f}ms")
# 收尾静音块
for _ in range(30):
    res = det.feed(np.zeros(BLOCK, dtype=np.float32))
    for ev in res["note_events"]:
        print(f"EVENT(flush) t={ev['t']:.2f} key={ev['key']} name={ev['name']} dur={ev['dur_ms']:.0f}ms")
print("active:", {m: round(a['start'],2) for m,a in det.active.items()})
