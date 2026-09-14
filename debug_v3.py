# -*- coding: utf-8 -*-
import wave, numpy as np
from instruments import build_lyre21
from detection import NoteDetector

wf = wave.open("v2_lowhigh.wav","rb")
data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)/32767
sr=48000; BLOCK=2048
inst = build_lyre21("风物之诗琴")
det = NoteDetector(inst, sr=sr, sensitivity=0.55, sim_clock=True)

# monkeypatch 看 midis
orig = det._process_frame
def patched(frame, t_now):
    if 5.5 < t_now < 8.0:
        # 手动跑一遍看 midis
        keys = {}
        frame_win = frame * det._win
        mag = np.abs(np.fft.rfft(frame_win, n=det.fft_n))
        peak = float(mag.max())
        if peak > 1e-9:
            det._floor = 0.92*det._floor + 0.08*max(float(np.median(mag))*4.0, 1e-7)
        det._recent_peak = max(peak, det._recent_peak*np.exp(-det.hop/det.sr*1.2))
        gate = max(det._floor*4.0, 1.5e-4, 0.06*det._recent_peak)
        if peak < gate:
            return orig(frame, t_now)
        rel_thr = 0.16 - 0.13*det.sensitivity
        abs_thr = max(det._floor*2.0, peak*rel_thr)
        peaks = det._find_peaks(mag, abs_thr)
        if peaks:
            top_amp = peaks[0][1]
            peaks = [p for p in peaks if p[1] >= 0.15*top_amp]
        peaks = det._lower_fundamentals(peaks, mag)
        midis_all = det._peaks_to_notes(peaks, mag)
        midis_new = [m for m in midis_all if det._has_harmonic_support(m, mag)]
        valid = inst.valid_midis()
        print(f"t={t_now:.2f} peak={peak:.1f} midis_all={midis_all} midis_new={midis_new} active={list(det.active.keys())}")
    return orig(frame, t_now)
det._process_frame = patched

for i in range(len(data)//BLOCK):
    det.feed(data[i*BLOCK:(i+1)*BLOCK])
