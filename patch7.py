# -*- coding: utf-8 -*-
s = open("detection.py", encoding="utf-8").read()

old = """        # 起音/落音跟踪
        attack_min = max(1.3, 2.2 - self.sensitivity)
        for m in current:
            amp = self._amp_of(m, mag)
            if m not in self.active:
                # 攻击门限：骤起才视为真实敲击；背景持续音/尾音（幅度无跳变）不启用
                if self._attack.get(m, 0.0) < attack_min:
                    continue
                self._open_note(m, t_now, amp)"""

new = """        # 起音/落音跟踪
        attack_min = max(1.3, 2.2 - self.sensitivity)
        for m in current:
            amp = self._amp_of(m, mag)
            if m not in self.active:
                # 攻击门限：骤起才视为真实敲击；背景持续音/尾音不启用。
                # 检查本音及 ±2 半音内任意音的起音强度（起音帧可能因频率偏差识别到相邻音）
                nearby_attack = max(self._attack.get(mm, 0.0)
                                    for mm in range(m - 2, m + 3))
                if nearby_attack < attack_min:
                    continue
                self._open_note(m, t_now, amp)"""

assert old in s
s = s.replace(old, new)
open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
