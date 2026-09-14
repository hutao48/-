import wave, numpy as np, sys
from instruments import build_lyre21
from detection import NoteDetector
fn = sys.argv[1] if len(sys.argv)>1 else "web_test7.wav"
wf = wave.open(fn,'rb')
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sens = float(sys.argv[2]) if len(sys.argv)>2 else 0.55
det = NoteDetector(build_lyre21('风物之诗琴'), sr=48000, sensitivity=sens, sim_clock=True)
evs=[]
for i in range(len(data)//2048):
    r = det.feed(data[i*2048:(i+1)*2048])
    evs.extend(r['note_events'])
for _ in range(30):
    r = det.feed(np.zeros(2048,dtype=np.float32))
    evs.extend(r['note_events'])
for e in evs:
    print(f"t={e['t']:.2f} key={e['key']} name={e['name']} dur={e['dur_ms']:.0f}ms")
print(f"total {len(evs)}  bpm={r.get('bpm')}  tonality={r.get('tonality')}")
