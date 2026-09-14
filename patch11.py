# -*- coding: utf-8 -*-
s = open("detection.py", encoding="utf-8").read()

old = '''    def _has_harmonic_support(self, midi, mag):
        """真实乐器音必须带有谐波分量（2/3/4 倍频 ≥12% 基频），用于剔除噪声毛刺"""
        freq = 440.0 * 2 ** ((midi - 69) / 12.0)
        base = int(freq * self.fft_n / self.sr)'''

new = '''    def _has_harmonic_support(self, midi, mag):
        """真实乐器音必须带谐波分量。高音(>450Hz)的2次谐波在>900Hz常被衰减，跳过校验。"""
        freq = 440.0 * 2 ** ((midi - 69) / 12.0)
        if freq > 450.0:
            return True
        base = int(freq * self.fft_n / self.sr)'''

assert old in s, "not found"
s = s.replace(old, new)
open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
