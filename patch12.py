# -*- coding: utf-8 -*-
s = open("detection.py", encoding="utf-8").read()

old = """        # raw：新音候选 ∪ 仍在峰中出现的已活跃音
        raw = set(snapped_new)
        for m in self.active:
            if m in snapped_all:
                raw.add(m)"""

new = """        # raw：新音候选 ∪ 仍在峰中出现且幅度仍显著的已活跃音。
        # 活跃音幅度 <15% 帧峰值时视为已衰减为尾音/谐波，不再保持。
        raw = set(snapped_new)
        frame_top = max((float(mag[p]) for p in range(len(mag))), default=0.0)
        for m in self.active:
            if m in snapped_all:
                if self._amp_of(m, mag) >= 0.15 * frame_top:
                    raw.add(m)"""

assert old in s
s = s.replace(old, new)
open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
