# -*- coding: utf-8 -*-
s = open("detection.py", encoding="utf-8").read()

old = '''        rules = [(4, 0.18), (3, 0.22), (2, 0.35)]
        active_midis = set(self.active.keys())
        out = []
        for x, amp in peaks:
            best_x, best_amp = x, amp
            for k, thr in rules:'''
new = '''        rules = [(4, 0.18), (3, 0.22), (2, 0.35)]
        active_midis = set(self.active.keys())
        out = []
        for x, amp in peaks:
            best_x, best_amp = x, amp
            # 只对 <400Hz 的峰做基频降级：高音区基频总是最强，不需要降级；
            # 否则会把高音误判为低音的高次谐波
            peak_freq = x * self.sr / self.fft_n
            if peak_freq > 400.0:
                out.append((best_x, best_amp))
                continue
            for k, thr in rules:'''
assert old in s
s = s.replace(old, new)
open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
