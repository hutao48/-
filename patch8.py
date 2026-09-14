# -*- coding: utf-8 -*-
s = open("detection.py", encoding="utf-8").read()

old = '''    def _dedup_harmonics(self, midis):
        """整数倍频去重：低频优先保留，高频谐波剔除"""
        if len(midis) < 2:
            return list(midis)
        kept = []
        for m in sorted(set(midis)):
            freq = 440.0 * 2 ** ((m - 69) / 12.0)
            is_harmonic = False
            for km in kept:
                kfreq = 440.0 * 2 ** ((km - 69) / 12.0)
                ratio = freq / kfreq
                if 1.7 <= ratio <= 8.5:
                    r = round(ratio)
                    if abs(ratio - r) < 0.08:
                        is_harmonic = True
                        break
            if not is_harmonic:
                kept.append(m)
        return kept'''

new = '''    def _dedup_harmonics(self, midis):
        """整数倍频去重：低频优先保留，高频谐波剔除。
        >400Hz (midi>=68) 的音不参与去重，它们是独立高音不是低音的谐波。"""
        if len(midis) < 2:
            return list(midis)
        kept = []
        for m in sorted(set(midis)):
            freq = 440.0 * 2 ** ((m - 69) / 12.0)
            if freq < 400.0:
                is_harmonic = False
                for km in kept:
                    kfreq = 440.0 * 2 ** ((km - 69) / 12.0)
                    ratio = freq / kfreq
                    if 1.7 <= ratio <= 8.5:
                        r = round(ratio)
                        if abs(ratio - r) < 0.08:
                            is_harmonic = True
                            break
                if is_harmonic:
                    continue
            kept.append(m)
        return kept'''

assert old in s, "old not found"
s = s.replace(old, new)
open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
