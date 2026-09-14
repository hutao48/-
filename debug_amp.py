import wave, numpy as np
wf = wave.open("web_test7.wav", "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000; fft_size=4096; fft_n=16384
win = np.hanning(fft_size)
def amp_at(frame, freq):
    mag = np.abs(np.fft.rfft(frame*win, n=fft_n))
    i = int(freq*fft_n/sr)
    return float(mag[max(0,i-1):i+2].max())
for tsec in [6.1, 6.2, 6.3, 6.5, 6.8, 7.0]:
    off = int(tsec*sr)
    frame = data[off:off+fft_size]
    if len(frame)<fft_size: break
    print(f"t={tsec:.1f}s  174.6Hz(F3)={amp_at(frame,174.6):.1f}  196Hz(G3)={amp_at(frame,196):.1f}  "
          f"261.6Hz(C4)={amp_at(frame,261.6):.1f}  329.6Hz(E4)={amp_at(frame,329.6):.1f}  "
          f"523.2Hz(C5)={amp_at(frame,523.2):.1f}")
