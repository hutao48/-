# -*- coding: utf-8 -*-
"""解析谱子为弹奏序列，输出 JSON 供 cu 执行"""
import json, re

# 原始谱子（每行一小节）
lines = """(CMD) /     /     /J J /J  /H J /(CNHQ) /J  /
(XNH) /    /    /    /     /     /
(CMD) /     /     /J J /J  /H J /(CNHQ) /J  /
(XNH)  /     /W  /     /     /     /
(CBA) /E E /E  /W Q /(XMW) /G  /
(XN) /Q Q /Q  /J Q /(ZBJ) /G  /
(ZVN) /H H /H  /G H /(XBMJ) /G  /
(CNSH) /     /     /     /(CNSH) /     /
(NAD) /     /     /E E /E  /W E /(NSHR)  /E  /
(BSGW) /     /G  /G H /J  /W  /
(NDH)  /     /     /E E /E  /W E /(NSHR) /E  /
(BSGW) /     /T  /J Q /W  /E   /
(VAD) /(QY) (QY) /(QY) /(JT) R /(CBSQT) /Q  /
(XNF) /(HR) (HR) /(HR) /(QE) R /(ZBQE) /Q  /
(XVN) /W W /W  /Q W /(CBME) /Q  /
(CNSW) /     /     /     /W  /     /
(CBM) /(DJ) (DJ) /(DJ)  /(DH) (DG) /(XNSH) /S  /
(CNAD) /(DQ) (DQ) /(DQ) /(DJ) (DQ) /(ZBDJ) /(DG) /
(ZVN) /(ZVNFH) (FH) /(ZVNFH) /(ZVNF) G /
(ZVNH) /(ZVNFH) (FH) /(ZVNFH) /(ZVNR) T /
(ZVNY) /(ZVN) /(ZVNY) /(ZVN) /(ZVNY) /(ZVNY) /
(CMEU) /(CM) (DJ)(DJ)/(CMDJ) /(CM) (DJ)(DJ)/
(CMU) /(CM) /(CMDU) (DJ) /(CMDJ) (DJ) /
     /     /CDCDCDCD /CDCDCDCD /""".strip().split("\n")

beats = []  # list of list-of-keys (each sublist = simultaneous press)
for line in lines:
    parts = line.split("/")
    for p in parts:
        p = p.strip()
        if not p:
            beats.append([])  # rest
            continue
        # 解析：可能是 (chord) 或 "A B" 或 "A"
        # 先提取所有括号组
        tokens = []
        # 找括号内容
        for m in re.finditer(r'\(([^)]+)\)', p):
            tokens.append(("chord", m.group(1)))
            p = p.replace(m.group(0), " ")
        # 剩余按空格分
        remaining = p.strip()
        if remaining:
            for ch in remaining.split():
                tokens.append(("note", ch))
        if not tokens:
            beats.append([])
        else:
            for ttype, tval in tokens:
                if ttype == "chord":
                    beats.append(list(tval))
                else:
                    beats.append([tval])

# 输出为 cu 可执行的序列
# 每个 beat: (keys, hold_sec)
seq = []
for b in beats:
    if not b:
        seq.append({"keys": [], "hold": 0.15})  # rest
    else:
        # 和弦或单音
        if len(b) > 1 and all(len(k)==1 for k in b):
            # 和弦
            seq.append({"keys": list(b), "hold": 0.35})
        else:
            # 单音
            seq.append({"keys": [b[0]], "hold": 0.3})

print(f"total beats: {len(seq)}")
total_dur = sum(s["hold"] for s in seq)
print(f"total duration: {total_dur:.1f}s")
# 保存
with open("score_seq.json", "w") as f:
    json.dump(seq, f)
# 打印前20个
for i, s in enumerate(seq[:20]):
    print(f"  {i}: {s['keys']} {s['hold']}s")
