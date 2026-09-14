# -*- coding: utf-8 -*-
"""一次性补丁：在 detection.py 中插入基频降级逻辑"""
s = open("detection.py", encoding="utf-8").read()

# 1. 在 _peaks_to_notes 调用前插入基频降级
old = '''        peaks = self._find_peaks(mag, abs_thr)
        # 帧内主导性：弱于最强峰 12% 的候选视为杂峰（如基频的弱副峰/拍频），剔除
        if peaks:
            top_amp = peaks[0][1]
            peaks = [p for p in peaks if p[1] >= 0.15 * top_amp]
        midis_all = self._peaks_to_notes(peaks, mag)'''
new = '''        peaks = self._find_peaks(mag, abs_thr)
        # 帧内主导性：弱于最强峰 15% 的候选视为杂峰（如基频的弱副峰/拍频），剔除
        if peaks:
            top_amp = peaks[0][1]
            peaks = [p for p in peaks if p[1] >= 0.15 * top_amp]
        # 基频降级：若峰 f 的 f/k (k=2,3,4) 处有显著能量，则 f 是谐波，真正基频在更低处
        peaks = self._lower_fundamentals(peaks, mag)
        midis_all = self._peaks_to_notes(peaks, mag)'''
assert old in s, "old1 not found"
s = s.replace(old, new)

# 2. 在 _peaks_to_notes 方法前插入 _lower_fundamentals 方法
old2 = "    def _peaks_to_notes(self, peaks, mag):"
new2 = '''    def _lower_fundamentals(self, peaks, mag):
        """基频降级：对每个峰 (bin, amp)，检查 f/k (k=4,3,2) 处是否有显著能量。
        若 f/k 处幅度超过阈值，说明 f 是某个更低基频的谐波，将峰移到 f/k。
        解决：低音区基频弱、2次谐波强时，按低音键却检测到中音键的问题。"""
        rules = [(4, 0.18), (3, 0.22), (2, 0.35)]
        out = []
        for x, amp in peaks:
            best_x, best_amp = x, amp
            for k, thr in rules:
                sub_bin = x / k
                bi = int(round(sub_bin))
                lo, hi = max(0, bi - 2), min(len(mag), bi + 3)
                sub_amp = float(mag[lo:hi].max()) if hi > lo else 0.0
                if sub_amp > thr * amp:
                    best_x = sub_bin
                    best_amp = max(amp, sub_amp)
                    break
            out.append((best_x, best_amp))
        return out

    def _peaks_to_notes(self, peaks, mag):'''
assert old2 in s, "old2 not found"
s = s.replace(old2, new2)

open("detection.py", "w", encoding="utf-8").write(s)
print("patched ok")
