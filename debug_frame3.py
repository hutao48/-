import wave, numpy as np
from instruments import build_lyre21
from detection import NoteDetector

wf = wave.open("web_test7.wav", "rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr = 48000; BLOCK = 2048

det = NoteDetector(build_lyre21("风物之诗琴"), sr=sr, sensitivity=0.55, sim_clock=True)
fft_size = 4096; fft_n = 16384; win = det._win
buf = np.zeros(0, dtype=np.float32); t = 0.0
for i in range(len(data)//BLOCK):
    buf = np.concatenate([buf, data[i*BLOCK:(i+1)*BLOCK]])
    while len(buf) >= fft_size:
        frame = buf[:fft_size]; buf = buf[1024:]
        if t > 6.0 and t < 6.5:
            mag = np.abs(np.fft.rfft(frame*win, n=fft_n))
            peak = mag.max()
            rel_thr = 0.16 - 0.13*0.55
            abs_thr = max(det._floor*2, peak*rel_thr)
            peaks = det._find_peaks(mag, abs_thr)
            midis = det._peaks_to_notes(peaks, mag)
            after_harm = [m for m in midis if det._has_harmonic_support(m, mag)]
            after_dedup = det._dedup_harmonics(after_harm)
            valid = det.instrument.valid_midis()
            snapped = []
            for m in after_dedup:
                if valid[0]-1 <= m <= valid[-1]+1:
                    s = min(valid, key=lambda v: abs(v-m))
                    if s not in snapped: snapped.append(s)
            print(f"t={t:.2f} peak={peak:.0f}")
            print(f"  raw={midis[:8]}")
            print(f"  harm={after_harm}  dedup={after_dedup}  snap={snapped}")
        det._process_frame(frame, t)
        t += 1024/sr
