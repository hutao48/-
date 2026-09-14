# -*- coding: utf-8 -*-
"""补丁：修复基频降级误判——不降到已活跃音"""
s = open("detection.py", encoding="utf-8").read()

old = '''    def _lower_fundamentals(self, peaks, mag):
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
        return out'''

new = '''    def _lower_fundamentals(self, peaks, mag):
        """基频降级：对每个峰 (bin, amp)，检查 f/k (k=4,3,2) 处是否有显著能量。
        若 f/k 处幅度超过阈值，说明 f 是某个更低基频的谐波，将峰移到 f/k。
        但：若 f/k 对应一个已活跃的音，说明这是两个独立音（低音还在响+新弹高音），不降级。"""
        rules = [(4, 0.18), (3, 0.22), (2, 0.35)]
        active_midis = set(self.active.keys())
        out = []
        for x, amp in peaks:
            best_x, best_amp = x, amp
            for k, thr in rules:
                sub_bin = x / k
                bi = int(round(sub_bin))
                sub_freq = bi * self.sr / self.fft_n
                sub_midi = int(round(69.0 + 12.0 * np.log2(sub_freq / 440.0)))
                # 不降到已活跃音：高音是独立音，不是低音的谐波
                if sub_midi in active_midis:
                    continue
                lo, hi = max(0, bi - 2), min(len(mag), bi + 3)
                sub_amp = float(mag[lo:hi].max()) if hi > lo else 0.0
                if sub_amp > thr * amp:
                    best_x = sub_bin
                    best_amp = max(amp, sub_amp)
                    break
            out.append((best_x, best_amp))
        return out'''

assert old in s, "old not found"
s = s.replace(old, new)
open("detection.py", "w", encoding="utf-8").write(s)
print("patched ok")
