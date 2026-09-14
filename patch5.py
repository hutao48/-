# -*- coding: utf-8 -*-
s = open("detection.py", encoding="utf-8").read()

old = '''    def _lower_fundamentals(self, peaks, mag):
        """基频降级：对每个峰 (bin, amp)，若 f/k 本身也是一个局部峰（真实存在的音），
        则 f 是它的谐波，将峰移到 f/k。只降级到真实峰，不降级到仅有能量的谐波肩。"""
        rules = [(4, 0.18), (3, 0.22), (2, 0.35)]
        out = []
        for x, amp in peaks:
            best_x, best_amp = x, amp
            for k, thr in rules:
                sub_bin = x / k
                # 检查 f/k 处是否存在另一个局部峰
                sub_is_peak = False
                for px, pamp in peaks:
                    if abs(px - sub_bin) < 3.0:
                        sub_is_peak = True
                        break
                if not sub_is_peak:
                    continue
                bi = int(round(sub_bin))
                lo, hi = max(0, bi - 2), min(len(mag), bi + 3)
                sub_amp = float(mag[lo:hi].max()) if hi > lo else 0.0
                if sub_amp > thr * amp:
                    best_x = sub_bin
                    best_amp = max(amp, sub_amp)
                    break
            out.append((best_x, best_amp))
        return out'''

new = '''    def _lower_fundamentals(self, peaks, mag):
        """基频降级：对每个峰 (bin, amp)，若 f/k 本身也是一个局部峰（真实存在的音），
        则 f 是它的谐波，将峰移到 f/k。但 f/k 对应已活跃音时不降级（两个独立音）。"""
        rules = [(4, 0.18), (3, 0.22), (2, 0.35)]
        active_midis = set(self.active.keys())
        out = []
        for x, amp in peaks:
            best_x, best_amp = x, amp
            for k, thr in rules:
                sub_bin = x / k
                # f/k 是否对应已活跃音？是则不降级（新高音是独立音）
                sub_freq = sub_bin * self.sr / self.fft_n
                sub_midi = int(round(69.0 + 12.0 * np.log2(sub_freq / 440.0)))
                if sub_midi in active_midis:
                    continue
                # 检查 f/k 处是否存在另一个局部峰
                sub_is_peak = False
                for px, pamp in peaks:
                    if abs(px - sub_bin) < 3.0:
                        sub_is_peak = True
                        break
                if not sub_is_peak:
                    continue
                bi = int(round(sub_bin))
                lo, hi = max(0, bi - 2), min(len(mag), bi + 3)
                sub_amp = float(mag[lo:hi].max()) if hi > lo else 0.0
                if sub_amp > thr * amp:
                    best_x = sub_bin
                    best_amp = max(amp, sub_amp)
                    break
            out.append((best_x, best_amp))
        return out'''

assert old in s
s = s.replace(old, new)
open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
