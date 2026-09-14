import wave, sys, numpy as np
wf = wave.open(sys.argv[1], "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000
W = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
step = int(W*sr)
for i in range(0, len(data)-step, step):
    seg = data[i:i+step]
    if np.sqrt(np.mean(seg**2)) < 0.01:
        continue
    win = seg * np.hanning(len(seg))
    fft = np.abs(np.fft.rfft(win, n=16384))
    freqs = np.fft.rfftfreq(len(win), 1/sr)
    fft[:5] = 0
    f0 = freqs[np.argmax(fft)]
    midi = 69 + 12*np.log2(f0/440)
    # 检查谐波
    print(f"t={i/sr:5.2f}s  f0={f0:6.1f}Hz  midi={midi:5.1f}")
