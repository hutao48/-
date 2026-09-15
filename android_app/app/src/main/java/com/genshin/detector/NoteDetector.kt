package com.genshin.detector

import kotlin.math.*

/**
 * 音高检测器 - 21键风物之诗琴
 * Q-U=C5-B5, A-J=C4-B4, Z-M=C3-B3
 */
class NoteDetector(private val sensitivity: Float = 0.7f, srVal: Int = 44100) {
    private val sr = srVal
    private val fftSize = 4096
    private val fftN = 16384

    private val keyMidi = mapOf(
        "Q" to 72, "W" to 74, "E" to 76, "R" to 77, "T" to 79, "Y" to 81, "U" to 83,
        "A" to 60, "S" to 62, "D" to 64, "F" to 65, "G" to 67, "H" to 69, "J" to 71,
        "Z" to 48, "X" to 50, "C" to 52, "V" to 53, "B" to 55, "N" to 57, "M" to 59
    )
    private val midiKey = keyMidi.entries.associate { (k, v) -> v to k }

    private class ActiveNote(var start: Double, var last: Double, var amp: Float, var maxAmp: Float)

    private val active = mutableMapOf<Int, ActiveNote>()
    private val streak = mutableMapOf<Int, Int>()
    private val miss = mutableMapOf<Int, Int>()
    private val attack = mutableMapOf<Int, Float>()
    private var prevMag: FloatArray? = null
    private var floor = 1e-7f
    private var recentPeak = 0f
    private var prevRms = 0f
    private var grace = 7
    private val confirm = 4
    private val onsets = mutableListOf<Pair<Double, Float>>()
    private var bpmSmooth: Float? = null
    private var noiseSpec: FloatArray? = null

    var bpm: Float? = null
        private set
    var tonality: String = "分析中…"
        private set
    var chord: String? = null
        private set
    val activeLabels: Set<String> get() = active.keys.mapNotNull { midiKey[it] }.toSet()

    // FFT buffers (full size, power of 2)
    private val re = DoubleArray(fftN)
    private val im = DoubleArray(fftN)
    private val mag = FloatArray(fftN / 2 + 1)
    private val win = FloatArray(fftSize)

    init {
        for (i in 0 until fftSize) win[i] = (0.5 * (1 - cos(2 * PI * i / (fftSize - 1)))).toFloat()
    }

    fun feed(frame: FloatArray, tNow: Double) {
        // Fill FFT buffer
        for (i in 0 until fftN) {
            re[i] = if (i < fftSize) (frame[i] * win[i]).toDouble() else 0.0
            im[i] = 0.0
        }
        fft(re, im)
        for (i in 0..fftN / 2) {
            mag[i] = sqrt(re[i] * re[i] + im[i] * im[i]).toFloat()
        }
        val peak = mag.maxOrNull() ?: 0f

        // Noise tracking
        if (noiseSpec == null) noiseSpec = mag.copyOf()
        noiseSpec?.let { ns ->
            for (i in ns.indices) ns[i] = (0.997 * ns[i] + 0.003 * mag[i]).toFloat()
        }
        val noise = noiseSpec!!
        val magClean = FloatArray(mag.size) { i ->
            maxOf(mag[i] - 1.0f * noise[i], 0.1f * mag[i])
        }

        // Adaptive floor
        if (peak > 1e-9) {
            val sorted = mag.copyOf().sorted()
            val med = sorted[sorted.size / 2]
            floor = (0.92f * floor + 0.08f * maxOf(med * 4f, 1e-7f))
        }
        recentPeak = maxOf(peak, (recentPeak * exp(-1024.0 / sr * 1.2)).toFloat())
        val gate = maxOf(floor * 4f, 1.5e-4f, 0.06f * recentPeak)

        if (peak < gate) {
            active.clear()
            prevMag = mag
            return
        }

        val relThr = 0.16f - 0.13f * sensitivity
        val absThr = maxOf(floor * 2f, peak * relThr)

        val peaks = findPeaks(magClean, absThr)
        if (peaks.isNotEmpty()) {
            val topAmp = peaks[0].second
            peaks.retainAll { it.second >= 0.12f * topAmp }
        }

        val midis = peaks.map { (bin, _) ->
            val freq = bin * sr / fftN
            (69 + 12 * log2(freq / 440.0)).roundToInt()
        }.filter { it in 47..84 }

        val midisNew = midis.filter { hasHarmonicSupport(it, magClean) }

        val prev = prevMag
        for (m in midisNew) {
            val amp = ampOf(m, magClean)
            val prevAmp = prev?.let { it[binOf(m)] } ?: 0f
            val ratio = amp / maxOf(prevAmp, 1e-9f)
            attack[m] = maxOf(attack.getOrDefault(m, 0f), ratio)
        }

        val rms = sqrt(frame.map { it * it }.average()).toFloat()
        prevRms = rms

        for (m in streak.keys.toList()) {
            if (m !in midis) {
                miss[m] = (miss[m] ?: 0) + 1
                if ((miss[m] ?: 0) >= 2) { streak[m] = 0; attack.remove(m) }
            }
        }
        for (m in midis) { miss[m] = 0; streak[m] = (streak[m] ?: 0) + 1 }
        val current = streak.filter { it.value >= confirm }.keys.toSet()

        val attackMin = maxOf(1.3f, 2.2f - sensitivity)
        for (m in current) {
            if (m !in active) {
                val near = (m - 1..m + 1).maxOfOrNull { attack.getOrDefault(it, 0f) } ?: 0f
                if (near >= attackMin) {
                    val amp = ampOf(m, magClean)
                    active[m] = ActiveNote(tNow, tNow, amp, amp)
                    onsets.add(tNow to amp)
                }
            } else {
                val a = active[m]!!
                a.last = tNow
                a.amp = ampOf(m, magClean)
                if (a.amp > a.maxAmp) a.maxAmp = a.amp
            }
        }
        for (m in active.keys.toList()) {
            if (m !in current) {
                miss[m] = (miss[m] ?: 0) + 1
                if ((miss[m] ?: 0) >= grace) active.remove(m)
            }
        }

        prevMag = mag
        updateBpm(tNow)
    }

    private fun findPeaks(mag: FloatArray, thr: Float): MutableList<Pair<Float, Float>> {
        val out = mutableListOf<Pair<Float, Float>>()
        for (i in 3 until mag.size - 3) {
            if (mag[i] > thr && mag[i] >= mag[i-1] && mag[i] >= mag[i+1]) {
                out.add(i.toFloat() to mag[i])
            }
        }
        out.sortByDescending { it.second }
        return out
    }

    private fun hasHarmonicSupport(midi: Int, mag: FloatArray): Boolean {
        val freq = 440.0 * 2.0.pow((midi - 69) / 12.0)
        if (freq > 450) return true
        val base = (freq * fftN / sr).toInt()
        if (base !in mag.indices) return false
        var baseAmp = 0f
        for (i in maxOf(0,base-2)..minOf(mag.size-1,base+3)) {
            if (mag[i] > baseAmp) baseAmp = mag[i]
        }
        baseAmp = maxOf(baseAmp, 1e-9f)
        for (k in 2..4) {
            val t = base * k
            if (t >= mag.size) break
            var maxV = 0f
            for (i in maxOf(0,t-3)..minOf(mag.size-1,t+4)) {
                if (mag[i] > maxV) maxV = mag[i]
            }
            if (maxV > 0.03f * baseAmp) return true
        }
        return false
    }

    private fun binOf(midi: Int): Int {
        val f = 440.0 * 2.0.pow((midi - 69) / 12.0)
        val i = (f * fftN / sr).toInt()
        return if (i in 0 until fftN / 2) i else 0
    }

    private fun ampOf(midi: Int, mag: FloatArray): Float {
        val i = binOf(midi)
        return if (i in mag.indices) mag[i] else 0f
    }

    private fun updateBpm(now: Double) {
        val recent = onsets.filter { it.first > now - 12 }.map { it.first }
        if (recent.size < 5) { bpm = null; return }
        val arr = recent.takeLast(24)
        var bestP = 0.25; var bestScore = 0
        var p = 0.20
        while (p <= 1.60) {
            var score = 0
            for (i in arr.indices) for (j in i+1 until arr.size) {
                val d = arr[j] - arr[i]
                val k = d / p
                if (k in 0.9..4.2 && abs(k - round(k)) < 0.16) score++
            }
            if (score > bestScore) { bestScore = score; bestP = p }
            p += 0.005
        }
        if (bestScore < 3) return
        val newBpm = (60.0 / bestP).toFloat()
        bpm = bpmSmooth?.let { old ->
            if (abs(newBpm - old) > 30) (0.5f * old + 0.5f * newBpm) else (0.75f * old + 0.25f * newBpm)
        } ?: newBpm
        bpmSmooth = bpm
    }

    private fun fft(re: DoubleArray, im: DoubleArray) {
        val n = re.size
        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) { j = j xor bit; bit = bit shr 1 }
            j = j xor bit
            if (i < j) {
                var tr = re[i]; re[i] = re[j]; re[j] = tr
                var ti = im[i]; im[i] = im[j]; im[j] = ti
            }
        }
        var len = 2
        while (len <= n) {
            val ang = -2.0 * PI / len
            val wr = cos(ang); val wi = sin(ang)
            for (i in 0 until n step len) {
                var cr = 1.0; var ci = 0.0
                for (k in 0 until len / 2) {
                    val ur = re[i+k]; val ui = im[i+k]
                    val vr = re[i+k+len/2] * cr - im[i+k+len/2] * ci
                    val vi = re[i+k+len/2] * ci + im[i+k+len/2] * cr
                    re[i+k] = ur + vr; im[i+k] = ui + vi
                    re[i+k+len/2] = ur - vr; im[i+k+len/2] = ui - vi
                    val ncr = cr * wr - ci * wi
                    ci = cr * wi + ci * wr; cr = ncr
                }
            }
            len *= 2
        }
    }
}
