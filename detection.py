# -*- coding: utf-8 -*-
"""
实时音高/节奏/调性检测引擎（纯 NumPy，无外部 DSP 依赖）
- 复音检测：FFT 峰值拾取 + 抛物线插值 + 谐波过滤 + 多帧确认，可同时识别多个音（和弦）
- 音符跟踪：起音/落音 → 每个音的具体时长（毫秒）
- BPM：起音间隔(IOI)聚类估计，滑动窗口输出
- 调性：Krumhansl-Schmuckler 键位相关性分析（24 调）
- 和弦：音级集合 → 和弦模板匹配
"""
import time
from collections import deque
import numpy as np
from instruments import (Instrument, midi_to_name, midi_to_solfege,
                         CHORD_TEMPLATES, NOTE_NAMES)

# Krumhansl-Schmuckler 调性轮廓（大调/小调 12 音级权重）
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

CHORD_SUFFIX = {
    "maj": "", "min": "m", "dim": "dim", "aug": "aug", "sus2": "sus2", "sus4": "sus4",
    "5": "(5)", "maj7": "maj7", "7": "7", "m7": "m7", "m7b5": "m7b5",
    "dim7": "dim7", "6": "6", "m6": "m6", "add9": "add9", "madd9": "madd9",
}


class NoteDetector:
    def __init__(self, instrument: Instrument, sr: int = 48000,
                 sensitivity: float = 0.55, bpm_window: float = 12.0,
                 sim_clock: bool = False):
        self.instrument = instrument
        self.sr = sr
        self.fft_size = 4096          # 实际窗长 ≈ 85 ms
        self.fft_n = 16384            # 零填充到 16384 提升插值精度
        self.hop = 1024               # 帧移 ≈ 21 ms
        self.sensitivity = sensitivity  # 0~1
        self.bpm_window = bpm_window
        self.sim_clock = sim_clock    # True: 用音频时长推进时间（测试用）

        self._win = np.hanning(self.fft_size)
        self._buf = np.zeros(0, dtype=np.float32)
        self._sim_t = 0.0

        self.active = {}              # midi -> {"start": 秒, "last": 秒, "amp": float}
        self.active_frames = {}       # midi -> 连续缺席帧计数
        self.grace = 7                # 落音迟滞帧数（增到5~107ms，避免相邻音过渡时碎音）
        self.confirm = 4              # 连续帧确认阈值
        self._streak = {}             # midi -> 连续出现帧数
        self._miss = {}               # midi -> 连续缺席帧数
        self.onsets = []              # [(秒, 强度)] 最近起音
        self._prev_mag = None
        self._prev_rms = 0.0
        self._rms_hist = deque(maxlen=12)
        self._last_retrig = -1.0
        self._recent_peak = 0.0     # 近期最大帧峰值（指数衰减），用于相对门限
        self._attack = {}           # midi -> 攻击强度（首帧幅度/上帧同频幅度）
        self._floor = 1e-7            # 自适应噪声底
        self._bpm_smooth = None
        self._t0 = time.time()
        self.chroma_note_log = []     # [time, midi, dur_ms, amp] 用于调性

    # ------------------------------------------------------------------
    def set_instrument(self, inst: Instrument):
        self.instrument = inst

    def set_sensitivity(self, s: float):
        self.sensitivity = max(0.0, min(1.0, s))

    def reset(self):
        self.active.clear()
        self.active_frames.clear()
        self.onsets.clear()
        self.chroma_note_log.clear()
        self._streak.clear()
        self._miss.clear()
        self._prev_mag = None
        self._prev_rms = 0.0
        self._rms_hist.clear()
        self._last_retrig = -1.0
        self._bpm_smooth = None
        self._sim_t = 0.0
        self._attack.clear()

    # ------------------------------------------------------------------
    def _now(self):
        if self.sim_clock:
            return self._sim_t
        return time.time() - self._t0

    def feed(self, chunk: np.ndarray) -> dict:
        """输入一段单声道 float32 音频，返回本批检测结果"""
        chunk = np.asarray(chunk, dtype=np.float32)
        self._buf = np.concatenate([self._buf, chunk])
        out = {"keys": {}, "note_events": [], "chord": "", "tonality": "",
               "bpm": None, "t": self._now()}
        while len(self._buf) >= self.fft_size:
            frame = self._buf[:self.fft_size]
            self._buf = self._buf[self.hop:]
            if self.sim_clock:
                self._sim_t += self.hop / self.sr
            res = self._process_frame(frame, self._now())
            out["keys"].update(res["keys"])
            out["note_events"].extend(res["note_events"])
        out["chord"] = self._current_chord_text()
        out["tonality"] = self._current_tonality_text()
        out["bpm"] = self._current_bpm()
        return out

    # ------------------------------------------------------------------
    def _process_frame(self, frame: np.ndarray, t_now: float) -> dict:
        keys = {}
        events = []
        frame_win = frame * self._win
        mag = np.abs(np.fft.rfft(frame_win, n=self.fft_n))
        peak = float(mag.max())

        # 自适应噪声底
        if peak > 1e-9:
            self._floor = 0.92 * self._floor + 0.08 * max(float(np.median(mag)) * 4.0, 1e-7)

        # 近期峰值（指数衰减）→ 相对门限：播放停止后迅速压制残留/噪声
        self._recent_peak = max(peak, self._recent_peak * np.exp(-self.hop / self.sr * 1.2))
        gate = max(self._floor * 4.0, 1.5e-4, 0.06 * self._recent_peak)

        # 能量门：过静音帧直接跳过
        if peak < gate:
            self._release_all(events, t_now)
            return {"keys": {}, "note_events": events}

        # 相对阈值：灵敏度越高越灵敏
        rel_thr = 0.16 - 0.13 * self.sensitivity          # 0.03 ~ 0.16
        abs_thr = max(self._floor * 2.0, peak * rel_thr)
        peaks = self._find_peaks(mag, abs_thr)
        # 帧内主导性：弱于最强峰 15% 的候选视为杂峰（如基频的弱副峰/拍频），剔除
        if peaks:
            top_amp = peaks[0][1]
            peaks = [p for p in peaks if p[1] >= 0.12 * top_amp]
        # 基频降级：若峰 f 的 f/k (k=2,3,4) 处有显著能量，则 f 是谐波，真正基频在更低处
        peaks = self._lower_fundamentals(peaks, mag)
        midis_all = self._peaks_to_notes(peaks, mag)

        # 谐波结构校验：新音必须带谐波；已活跃的音只要在峰中出现就保持（避免谐波闪烁导致长音被切）
        midis_new = [m for m in midis_all if self._has_harmonic_support(m, mag)]

        # 攻击强度记录：对比上一帧同频幅度并取运行期最大值。
        # 真实拨弦音骤起（幅度远超上帧）；背景持续音/尾音/泄漏近似持平（≈1）。
        # 取 max 可避免"先因尾音泄漏出现、后真正敲响"的音符被陈旧小值拒绝。
        for m in midis_new:
            idx = self._bin_of(m)
            prev_amp = float(self._prev_mag[idx]) if self._prev_mag is not None else 0.0
            cur_amp = self._amp_of(m, mag)
            ratio = cur_amp / max(prev_amp, 1e-9)
            self._attack[m] = max(self._attack.get(m, 0.0), ratio)

        # 起音检测：RMS 上升 + 频谱通量（捕捉重复音/和弦重击）
        rms = float(np.sqrt(np.mean(frame ** 2)))
        flux_ratio = 0.0
        if self._prev_mag is not None:
            flux = float(np.sum(np.maximum(mag - self._prev_mag, 0.0)))
            flux_ratio = flux / (float(np.sum(mag)) + 1e-9)
        self._prev_mag = mag
        self._rms_hist.append(rms)
        recent_min = min(self._rms_hist) if len(self._rms_hist) >= 4 else 0.0
        rms_rising = rms >= 1.2 * self._prev_rms
        onset = bool(flux_ratio > 0.32 and rms >= 1.35 * max(recent_min, 1e-5))
        self._prev_rms = rms

        # 谐波去重：整数倍频只保留基频；弱谐波(<30%基频)去掉，强独立音保留
        amp_dict = {}
        for px, pamp in peaks:
            pf = px * self.sr / self.fft_n
            if 60 <= pf <= 5000:
                pm = int(round(69 + 12*np.log2(pf/440)))
                amp_dict[pm] = max(amp_dict.get(pm, 0), pamp)
        midis_new = self._dedup_harmonics(midis_new, amp_dict)
        midis_all = self._dedup_harmonics(midis_all, amp_dict)

        # 范围过滤 + 吸附到乐器可用音（含移调）
        valid = self.instrument.valid_midis()
        lo, hi = valid[0] - 1, valid[-1] + 1
        def snap(ms):
            out = []
            for m in ms:
                if lo <= m <= hi:
                    s = min(valid, key=lambda v: abs(v - m))
                    if s not in out:
                        out.append(s)
            return out
        snapped_new = snap(midis_new)
        snapped_all = snap(midis_all)
        # raw：新音候选 ∪ 仍在峰中出现且幅度仍显著的已活跃音。
        # 活跃音幅度 <15% 帧峰值时视为已衰减为尾音/谐波，不再保持。
        raw = set(snapped_new)
        frame_top = max((float(mag[p]) for p in range(len(mag))), default=0.0)
        for m in self.active:
            if m in snapped_all:
                if self._amp_of(m, mag) >= 0.15 * frame_top:
                    raw.add(m)

        # 连续帧确认：同一音需连续出现 ≥3 帧才生效（抑制过渡/瞬态杂音）
        # 缺席计数：连续缺席 2 帧才重置 streak——容忍重击瞬间基频短暂非峰，
        # 又不让已结束的音符滞留
        streak = self._streak
        miss = self._miss
        for m in list(streak.keys()):
            if m not in raw:
                miss[m] = miss.get(m, 0) + 1
                if miss[m] >= 2:
                    streak[m] = 0
                    self._attack.pop(m, None)
        for m in raw:
            miss[m] = 0
            streak[m] = streak.get(m, 0) + 1
        current = {m for m, c in streak.items() if c >= self.confirm}

        # 起音/落音跟踪
        attack_min = max(1.3, 2.2 - self.sensitivity)
        for m in current:
            amp = self._amp_of(m, mag)
            if m not in self.active:
                # 攻击门限：骤起才视为真实敲击；背景持续音/尾音不启用。
                # 检查本音及 ±2 半音内任意音的起音强度（起音帧可能因频率偏差识别到相邻音）
                nearby_attack = max(self._attack.get(mm, 0.0)
                                    for mm in range(m - 1, m + 2))
                if nearby_attack < attack_min:
                    continue
                self._open_note(m, t_now, amp)
            else:
                a = self.active[m]
                a["n"] += 1
                a["last"] = t_now
                if amp > a["maxamp"]:
                    a["maxamp"] = amp
                if amp < a["amin"]:
                    a["amin"] = amp
                a["amp"] = amp
                # 重触发已禁用：拨弦音自然衰减，幅度波动不应断开重开
        for m in list(self.active.keys()):
            if m not in current:
                self.active_frames[m] += 1
                if self.active_frames[m] >= self.grace:
                    a = self.active.pop(m)
                    self.active_frames.pop(m, None)
                    self._close_note(m, a, t_now, events)

        for m, a in self.active.items():
            label, _ = self.instrument.label_of(m)
            keys[label] = m
        return {"keys": keys, "note_events": events}

    # ------------------------------------------------------------------
    def _open_note(self, m, t_now, amp):
        self.active[m] = {"start": t_now, "last": t_now, "amp": amp,
                          "amin": amp, "maxamp": amp, "n": 0}
        self.active_frames[m] = 0
        self.onsets.append((t_now, amp))
        if len(self.onsets) > 2000:
            self.onsets = self.onsets[-1000:]
        self.chroma_note_log.append([t_now, m, 0.0, amp])

    def _close_note(self, m, a, t_now, events):
        """落音：时长过短的瞬态不产生事件、不计入起音/调性"""
        dur_ms = (t_now - a["start"]) * 1000.0
        if dur_ms < 200.0:
            for i in range(len(self.onsets) - 1, -1, -1):
                if abs(self.onsets[i][0] - a["start"]) < 0.01:
                    self.onsets.pop(i)
                    break
            for i in range(len(self.chroma_note_log) - 1, -1, -1):
                if (self.chroma_note_log[i][1] == m
                        and self.chroma_note_log[i][2] == 0.0
                        and abs(self.chroma_note_log[i][0] - a["start"]) < 0.01):
                    self.chroma_note_log.pop(i)
                    break
            return
        events.append(self._make_note_event(m, a, dur_ms))
        for entry in self.chroma_note_log:
            if entry[1] == m and entry[2] == 0.0:
                entry[2] = dur_ms
                break

    def _release_all(self, events, t_now):
        """静音帧：把所有仍在活跃的音符落音"""
        for m in list(self.active.keys()):
            self.active_frames[m] = self.active_frames.get(m, 0) + 1
            if self.active_frames[m] >= self.grace:
                a = self.active.pop(m)
                self.active_frames.pop(m, None)
                self._close_note(m, a, t_now, events)

    # ------------------------------------------------------------------
    def _find_peaks(self, mag: np.ndarray, abs_thr: float):
        """局部极大值 + 抛物线插值 → [(bin_float, amp)]"""
        out = []
        n = len(mag)
        i = 3
        while i < n - 3:
            if mag[i] > abs_thr and mag[i] >= mag[i - 1] and mag[i] >= mag[i + 1]:
                a, b, c = float(mag[i - 1]), float(mag[i]), float(mag[i + 1])
                denom = a - 2 * b + c
                d = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
                x = i + d
                amp = b - 0.25 * (a - c) * d
                out.append((x, amp))
                i += 4
            else:
                i += 1
        out.sort(key=lambda p: p[1], reverse=True)
        return out[:12]

    def _lower_fundamentals(self, peaks, mag):
        """基频降级：对每个峰 (bin, amp)，若 f/k 本身也是一个局部峰（真实存在的音），
        则 f 是它的谐波，将峰移到 f/k。但 f/k 对应已活跃音时不降级（两个独立音）。"""
        rules = [(4, 0.18), (3, 0.22), (2, 0.35)]
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
            for k, thr in rules:
                sub_bin = x / k
                # f/k 是否对应已活跃音？是则不降级（新高音是独立音）
                sub_freq = sub_bin * self.sr / self.fft_n
                sub_midi = int(round(69.0 + 12.0 * np.log2(sub_freq / 440.0)))
                if sub_midi in active_midis:
                    continue
                # 检查 f/k 处是否存在另一个局部峰
                sub_is_peak = False
                for px, pamp in peaks:
                    if abs(px - sub_bin) < 3.0:
                        sub_is_peak = True
                        break
                if not sub_is_peak:
                    continue
                bi = int(round(sub_bin))
                lo, hi = max(0, bi - 2), min(len(mag), bi + 3)
                sub_amp = float(mag[lo:hi].max()) if hi > lo else 0.0
                if sub_amp > thr * amp:
                    best_x = sub_bin
                    best_amp = max(amp, sub_amp)
                    break
            out.append((best_x, best_amp))
        return out

    def _peaks_to_notes(self, peaks, mag):
        midis = []
        for x, amp in peaks:
            freq = x * self.sr / self.fft_n
            if freq < 60.0 or freq > 5000.0:
                continue
            midi_f = 69.0 + 12.0 * np.log2(freq / 440.0)
            midis.append(int(round(midi_f)))
        return midis

    def _has_harmonic_support(self, midi, mag):
        """真实乐器音必须带谐波分量。高音(>450Hz)的2次谐波在>900Hz常被衰减，跳过校验。"""
        freq = 440.0 * 2 ** ((midi - 69) / 12.0)
        if freq > 450.0:
            return True
        base = int(freq * self.fft_n / self.sr)
        if not (0 <= base < len(mag)):
            return False
        base_amp = float(mag[max(0, base-2):min(len(mag), base+3)].max())
        if base_amp <= 0:
            return False
        for k in (2, 3, 4):
            target = base * k
            if target >= len(mag):
                break
            lo, hi = max(0, target - 3), min(len(mag), target + 4)
            if float(mag[lo:hi].max()) > 0.03 * base_amp:
                return True
        return False

    def _dedup_harmonics(self, midis, amp_dict=None):
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
                        if amp_k > 0 and amp_m < 0.50 * amp_k:
                            is_harmonic = True
                        elif amp_k == 0:
                            is_harmonic = True
                        break
            if not is_harmonic:
                kept.append(m)
        return kept

    def _bin_of(self, midi):
        freq = 440.0 * 2 ** ((midi - 69) / 12.0)
        i = int(freq * self.fft_n / self.sr)
        if 0 <= i < self.fft_n // 2:
            return i
        return 0

    def _amp_of(self, midi, mag):
        freq = 440.0 * 2 ** ((midi - 69) / 12.0)
        i = int(freq * self.fft_n / self.sr)
        if 0 <= i < len(mag):
            return float(mag[i])
        return 0.0

    # ------------------------------------------------------------------
    def _make_note_event(self, midi, active_info, dur_ms):
        label, approx = self.instrument.label_of(midi)
        name = midi_to_name(midi)
        if approx:
            target = self.instrument.pitch_keys()
            if target:
                nearest = min(target, key=lambda k: abs(k[1] - (midi - self.instrument.transpose)))
                name = f"≈{midi_to_name(nearest[1] + self.instrument.transpose)}"
        return {
            "t": active_info["start"],
            "key": label,
            "midi": midi,
            "name": name,
            "solfege": midi_to_solfege(midi),
            "dur_ms": round(dur_ms, 1),
            "approx": approx,
        }

    # ------------------------------------------------------------------
    def _current_bpm(self):
        """周期对齐法：在 0.2~1.6s 候选周期上统计起音间隔的倍频对齐数，取最密周期"""
        now = self._now()
        times = sorted(t for t, s in self.onsets if t > now - self.bpm_window)
        if len(times) < 5:
            return None
        arr = np.array(times[-24:], dtype=np.float64)  # 只用最近 24 个起音
        deltas = (arr[1:, None] - arr[None, :-1])
        deltas = deltas[deltas > 0.0]
        if len(deltas) < 6:
            return None
        best_p, best_score = None, -1
        for p in np.arange(0.20, 1.601, 0.005):
            ks = deltas / p
            ok = (ks >= 0.9) & (ks <= 4.2)
            if not ok.any():
                continue
            kk = ks[ok]
            score = int(np.sum(np.abs(kk - np.round(kk)) < 0.16))
            if score > best_score:
                best_score, best_p = score, float(p)
        if best_p is None or best_score < 3:
            return self._bpm_smooth
        new = 60.0 / best_p
        if self._bpm_smooth is None:
            self._bpm_smooth = new
        elif abs(new - self._bpm_smooth) > 30:
            self._bpm_smooth = 0.5 * self._bpm_smooth + 0.5 * new
        else:
            self._bpm_smooth = 0.75 * self._bpm_smooth + 0.25 * new
        return round(self._bpm_smooth, 1)

    # ------------------------------------------------------------------
    def _current_tonality_text(self):
        """Krumhansl-Schmuckler：最近 14s 音符（时长加权、指数衰减）→ 最可能调"""
        now = self._now()
        chroma = np.zeros(12)
        weight_sum = 0.0
        for t, midi, dur, amp in self.chroma_note_log:
            age = now - t
            if age > 14.0:
                continue
            # 时长权重封顶，避免长尾音过度主导
            w = amp * max(0.25, min(1.0, dur / 450.0)) * np.exp(-age / 7.0)
            chroma[midi % 12] += w
            weight_sum += w
        if weight_sum < 3.0:
            return "分析中…（音符不足）"
        chroma = chroma / (weight_sum + 1e-9)

        best_key, best_corr = None, -2.0
        second_corr = -2.0
        for root in range(12):
            cm = np.corrcoef(np.roll(KS_MAJOR, root), chroma)[0, 1]
            cn = np.corrcoef(np.roll(KS_MINOR, root), chroma)[0, 1]
            for name, c in (("maj", cm), ("min", cn)):
                if c > best_corr:
                    second_corr = best_corr
                    best_corr = c
                    best_key = (root, name)
                elif c > second_corr:
                    second_corr = c
        if best_key is None:
            return "未知"
        root, mode = best_key
        text = f"{NOTE_NAMES[root]} 大调" if mode == "maj" else f"{NOTE_NAMES[root]} 小调"
        conf = int(round(100 * max(0.0, (best_corr - 0.25)) / 0.65))
        conf = max(5, min(99, conf))
        return f"{text}（置信 {conf}%）"

    # ------------------------------------------------------------------
    def _current_chord_text(self):
        pcs = sorted({m % 12 for m in self.active.keys()})
        if len(pcs) < 2:
            return ""
        ck = self.instrument.match_chord_key(pcs)
        if ck:
            return f"{ck[1]}（键 {ck[0]}）"
        best = None
        for root in range(12):
            for tname, tpl in CHORD_TEMPLATES.items():
                tset = {(root + i) % 12 for i in tpl}
                if tset <= set(pcs):
                    score = len(tset) - 0.2 * (len(pcs) - len(tset))
                    if best is None or score > best[0]:
                        best = (score, root, tname, tset)
        if best is None:
            return ""
        _, root, tname, _ = best
        return f"{NOTE_NAMES[root]}{CHORD_SUFFIX[tname]}"
