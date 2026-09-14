import wave, numpy as np
from instruments import build_lyre21
from detection import NoteDetector

wf = wave.open("web_test7.wav", "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000
BLOCK = 2048

det = NoteDetector(build_lyre21("风物之诗琴"), sr=sr, sensitivity=0.55, sim_clock=True)

# 直接调用内部方法看每帧
fft_size = 4096; fft_n = 16384; win = det._win
buf = np.zeros(0, dtype=np.float32)
t = 0.0
for i in range(len(data)//BLOCK):
    blk = data[i*BLOCK:(i+1)*BLOCK]
    buf = np.concatenate([buf, blk])
    while len(buf) >= fft_size:
        frame = buf[:fft_size]; buf = buf[1024:]
        mag = np.abs(np.fft.rfft(frame*win, n=fft_n))
        peak = mag.max()
        if peak > 0.01 and t > 5.5:  # 只看起音附近
            rel_thr = 0.16 - 0.13*0.55
            abs_thr = max(det._floor*2, peak*rel_thr)
            peaks = det._find_peaks(mag, abs_thr)
            midis = det._peaks_to_notes(peaks, mag)
            print(f"t={t:.2f} peak={peak:.1f} thr={abs_thr:.2f} raw_midis={midis[:8]}")
        # 调原方法更新状态
        det._process_frame(frame, t)
        t += 1024/sr
