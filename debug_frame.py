import wave, numpy as np
wf = wave.open("web_test6.wav", "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000
fft_size = 4096; fft_n = 16384; hop = 1024
win = np.hanning(fft_size)
# 从 4.3s 开始（起音附近），逐帧分析
for off in range(int(4.3*sr), int(5.2*sr), hop):
    frame = data[off:off+fft_size]
    if len(frame) < fft_size: break
    mag = np.abs(np.fft.rfft(frame*win, n=fft_n))
    peak = mag.max()
    t = off/sr
    # 找前几个峰
    idx = np.argsort(mag)[::-1][:6]
    peaks = []
    for i in sorted(idx, key=lambda x:-mag[x]):
        f = i*sr/fft_n
        midi = 69+12*np.log2(f/440) if f>0 else 0
        peaks.append(f"{f:.0f}Hz/m{int(round(midi))}")
    print(f"t={t:.2f} peak={peak:.0f}  " + "  ".join(peaks))
