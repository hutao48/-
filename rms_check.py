import wave, sys, numpy as np
wf = wave.open(sys.argv[1], "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000
for i in range(len(data)//sr):
    seg = data[i*sr:(i+1)*sr]
    rms = float(np.sqrt(np.mean(seg**2)))
    bar = "#" * int(rms*300)
    print(f"{i:2d}s rms={rms:.4f} {bar}")
