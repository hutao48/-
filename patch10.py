# -*- coding: utf-8 -*-
s = open("detection.py", encoding="utf-8").read()

# 1. grace 4->10, confirm 3->4
s = s.replace("self.grace = 4", "self.grace = 10")
s = s.replace("self.confirm = 3", "self.confirm = 4")
# 2. 最短音长 150->250ms
s = s.replace("if dur_ms < 150.0:", "if dur_ms < 250.0:")
# 3. nearby_attack ±2 -> ±1
s = s.replace("range(m - 2, m + 3)", "range(m - 1, m + 2)")
# 4. 关闭自动重触发
old_rt = (
    '                # 重触发：同一音被再次敲击（自身幅度从低谷显著回升）\n'
    '                if (a["n"] >= 6 and (t_now - a["start"]) >= 0.12\n'
    '                        and amp >= 2.0 * a["amin"]\n'
    '                        and amp >= 0.45 * a["maxamp"]):\n'
    '                    self._close_note(m, a, t_now, events)\n'
    '                    self._open_note(m, t_now, amp)'
)
new_rt = '                # 重触发已禁用：拨弦音自然衰减，幅度波动不应断开重开'
assert old_rt in s, "retrigger block not found"
s = s.replace(old_rt, new_rt)
# 5. 15% -> 12%
s = s.replace("p[1] >= 0.15 * top_amp", "p[1] >= 0.12 * top_amp")

open("detection.py", "w", encoding="utf-8").write(s)
print("ok")
