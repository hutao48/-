# -*- coding: utf-8 -*-
"""重写 dedup：带幅度，弱谐波去掉，强独立高音保留"""
s = open("detection.py", encoding="utf-8").read()

# 1. 修改调用处：传幅度字典
old = """        # 谐波去重：整数倍频只保留基频
        midis_new = self._dedup_harmonics(midis_new)
        midis_all = self._dedup_harmonics(midis_all)"""
new = """        # 谐波去重：整数倍频只保留基频；弱谐波(<30%基频)去掉，强独立音保留
        amp_dict = {}
        for px, pamp in peaks:
            pf = px * self.sr / self.fft_n
            if 60 <= pf <= 5000:
                pm = int(round(69 + 12*np.log2(pf/440)))
                amp_dict[pm] = max(amp_dict.get(pm, 0), pamp)
        midis_new = self._dedup_harmonics(midis_new, amp_dict)
        midis_all = self._dedup_harmonics(midis_all, amp_dict)"""
assert old in s
s = s.replace(old, new)

# 2. 重写 _dedup_harmonics
old2 = '''    def _dedup_harmonics(self, midis):
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

new2 = '''    def _dedup_harmonics(self, midis, amp_dict=None):
        """整数倍频去重：低频优先保留，高频谐波剔除。
        若高频音幅度<30%低频音幅度，视为弱谐波去掉；否则保留为独立音。"""
        if len(midis) < 2:
            return list(midis)
        amp_dict = amp_dict or {}
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
                        # 检查幅度：高频音幅度远小于低频音才是谐波
                        amp_m = amp_dict.get(m, 0)
                        amp_k = amp_dict.get(km, 0)
                        if amp_k > 0 and amp_m < 0.30 * amp_k:
                            is_harmonic = True
                        elif amp_k == 0:
                            is_harmonic = True
                        break
            if not is_harmonic:
                kept.append(m)
        return kept'''
assert old2 in s
s = s.replace(old2, new2)

open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
