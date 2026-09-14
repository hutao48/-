# -*- coding: utf-8 -*-
"""分析 v2_lowhigh.wav 各时间段的频谱峰值"""
import wave, numpy as np
wf = wave.open("v2_lowhigh.wav", "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000; fft_size=4096; fft_n=16384; win=np.hanning(fft_size)

def top_peaks(tsec, n=8):
    off = int(tsec*sr)
    frame = data[off:off+fft_size]
    if len(frame) < fft_size: return []
    mag = np.abs(np.fft.rfft(frame*win, n=fft_n))
    # 找局部极大
    peaks = []
    for i in range(3, len(mag)-3):
        if mag[i] > 5 and mag[i] >= mag[i-1] and mag[i] >= mag[i+1]:
            peaks.append((i*sr/fft_n, float(mag[i])))
    peaks.sort(key=lambda p: p[1], reverse=True)
    return peaks[:n]

# Q=C5 应该在 t≈9-10s (Z 持续到10.5s后)
# 扫描每个时间段
for t in [3, 5, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17]:
    pk = top_peaks(t)
    if not pk:
        print(f"t={t}: (静音)")
        continue
    top = pk[0][1]
    parts = []
    for f, a in pk:
        midi = 69 + 12*np.log2(f/440)
        parts.append(f"{f:.0f}Hz(m{int(round(midi))},{a/top*100:.0f}%)")
    print(f"t={t}: " + "  ".join(parts))
