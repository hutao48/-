s = open("ui_main.py", encoding="utf-8").read()
old = 'self.setWindowTitle("原神乐器演奏检测器 — 按键 / 和弦 / 调性 / 音长 / BPM")'
new = 'self.setWindowTitle("原神乐器演奏检测器 v2.0 — 按键 / 和弦 / 调性 / 音长 / BPM")'
assert old in s
s = s.replace(old, new)
open("ui_main.py", "w", encoding="utf-8").write(s)
print("ok")
