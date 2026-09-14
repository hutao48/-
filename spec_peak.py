import wave, sys, numpy as np
wf = wave.open(sys.argv[1], "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000
t = float(sys.argv[2])
step = int(t*sr)
seg = data[step:step+sr//2]  # 0.5s
win = seg * np.hanning(len(seg))
fft = np.abs(np.fft.rfft(win, n=16384))
freqs = np.fft.rfftfreq(len(win), 1/sr)
fft[:5] = 0
idx = np.argsort(fft)[::-1][:15]
print(f"--- t={t}s 附近前15个频率峰 ---")
for i in sorted(idx, key=lambda x: -fft[x]):
    f = freqs[i]
    midi = 69 + 12*np.log2(f/440)
    print(f"  {f:7.1f} Hz  midi={midi:5.1f}  amp={fft[i]:.2f}")
