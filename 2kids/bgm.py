#!/usr/bin/env python3
"""두아이 살림노트 숏츠 배경음악 — 직접 합성한 자체 제작 음원 (외부 음원·샘플 없음, 저작권 걱정 없음).

사용법:
    python3 2kids/bgm.py            # 2kids/bgm/*.mp3 전부 다시 만들기
    python3 2kids/bgm.py sunny      # 한 곡만

곡 (모두 약 64초, 끝과 처음이 자연스럽게 이어져 반복 재생 가능):
    sunny  — 우쿨렐레풍 뜯는 소리 + 마림바, 밝고 통통 튀는 (지원금·혜택 소식)
    cozy   — 부드러운 일렉 피아노 로파이, 잔잔한 (육아뉴스·공감)
    bounce — 마림바 + 글로켄, 빠르고 경쾌한 (시즌 꿀팁·체크리스트)
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent / "bgm"

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def env_adsr(n, a=0.005, d=0.1, s=0.6, r=0.1, sus_len=None):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    sus_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([np.linspace(0, 1, max(a_n, 1)), np.linspace(1, s, max(d_n, 1)),
                        np.full(sus_n, s), np.linspace(s, 0, max(r_n, 1))])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


# ---------- 악기 ----------
def pluck(f, dur, bright=0.5, rng=None):
    """카플러스-스트롱 뜯는 소리 (우쿨렐레풍)."""
    rng = rng or np.random.default_rng(0)
    n = int(dur * SR)
    N = max(2, int(SR / f))
    buf = rng.uniform(-1, 1, N)
    # 밝기: 처음 버퍼를 살짝 부드럽게
    for _ in range(int((1 - bright) * 3)):
        buf = 0.5 * (buf + np.roll(buf, 1))
    out = np.empty(n + N)
    out[:N] = buf
    i = N
    decay = 0.996
    while i < n + N:
        prev = out[i - N:i]
        blk = decay * 0.5 * (prev + np.concatenate([[prev[-1]], prev[:-1]]))
        m = min(N, n + N - i)
        out[i:i + m] = blk[:m]
        i += m
    y = out[N:N + n]
    y *= np.linspace(1, 0, n) ** 0.5
    return y * 0.8


def marimba(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 7) + 0.35 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 22) \
        + 0.12 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t * 45)
    y *= np.minimum(1, t / 0.002)
    return y * 0.7


def glock(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 3.2) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6) \
        + 0.15 * np.sin(2 * np.pi * f * 5.40 * t) * np.exp(-t * 10)
    y *= np.minimum(1, t / 0.001)
    return y * 0.35


def epiano(f, dur):
    """FM 일렉 피아노 (로즈풍)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    idx = 1.6 * np.exp(-t * 4) + 0.2
    mod = np.sin(2 * np.pi * f * t) * idx
    y = np.sin(2 * np.pi * f * t + mod) + 0.25 * np.sin(2 * np.pi * f * 2.0 * t + 0.5 * mod) * np.exp(-t * 3)
    y *= env_adsr(n, a=0.004, d=0.6, s=0.35, r=0.25) * np.exp(-t * 0.6)
    return y * 0.45


def bass(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    y *= env_adsr(n, a=0.008, d=0.15, s=0.7, r=0.06)
    return y * 0.55


def kick(dur=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    fr = 50 + 70 * np.exp(-t * 35)
    ph = 2 * np.pi * np.cumsum(fr) / SR
    return np.sin(ph) * np.exp(-t * 18) * 0.8


def shaker(dur=0.07, rng=None):
    rng = rng or np.random.default_rng(1)
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.uniform(-1, 1, n)
    x = x - np.concatenate([[0], x[:-1]])  # 고역 강조
    return x * np.exp(-t * 60) * 0.12


def snap(dur=0.12, rng=None):
    rng = rng or np.random.default_rng(2)
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.uniform(-1, 1, n)
    # 간단한 대역 필터 느낌: 두 번 평균
    x = 0.5 * (x + np.roll(x, 1))
    x = x - 0.6 * np.roll(x, 3)
    return x * np.exp(-t * 38) * 0.28


# ---------- 곡 구성 ----------
CHORDS = {  # 장조 안의 화음 (근음 반음, 구성음)
    "I": (0, [0, 4, 7]), "ii": (2, [2, 5, 9]), "iii": (4, [4, 7, 11]), "IV": (5, [5, 9, 12]),
    "V": (7, [7, 11, 14]), "vi": (9, [9, 12, 16]), "Imaj7": (0, [0, 4, 7, 11]), "IVmaj7": (5, [5, 9, 12, 16]),
    "vi7": (9, [9, 12, 16, 19]), "ii7": (2, [2, 5, 9, 12]), "V7sus": (7, [7, 12, 14, 17]),
}

TRACKS = {
    "sunny": dict(key="C", bpm=104, prog=["I", "V", "vi", "IV"], lead="pluck", arp="pluck", top="marimba", swing=0.0, seed=3),
    "cozy": dict(key="F", bpm=86, prog=["IVmaj7", "iii", "vi7", "Imaj7", "ii7", "V7sus", "Imaj7", "Imaj7"], lead="epiano",
                 arp="epiano", top="glock", swing=0.12, seed=7),
    "bounce": dict(key="G", bpm=116, prog=["I", "vi", "IV", "V"], lead="marimba", arp="marimba", top="glock", swing=0.0, seed=11),
}


def inst(name, f, dur, rng):
    if name == "pluck":
        return pluck(f, dur, bright=0.6, rng=rng)
    if name == "marimba":
        return marimba(f, dur)
    if name == "glock":
        return glock(f, dur)
    return epiano(f, dur)


def add(buf, sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[1]:
        return
    m = min(len(sig), buf.shape[1] - i)
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[0, i:i + m] += sig[:m] * gain * l * 1.414
    buf[1, i:i + m] += sig[:m] * gain * r * 1.414


def compose(name, seconds=64):
    cfg = TRACKS[name]
    rng = np.random.default_rng(cfg["seed"])
    beat = 60 / cfg["bpm"]
    bar = beat * 4
    bars = int(np.ceil(seconds / bar))
    total = bars * bar
    buf = np.zeros((2, int((total + 3) * SR)))
    root = 48 + NOTE[cfg["key"]]  # C3 근처
    prog = cfg["prog"]
    sw = cfg["swing"]

    # 2마디짜리 멜로디 모티프 (화음 구성음에서 고름), 4마디마다 살짝 변형
    motif = [(0, 2), (1, 1), (1.5, 0), (2.5, 1), (4, 2), (5, 3), (6, 1), (7, 0)]  # (8분음표 위치 ×0.5박? → 박 단위, 화음음 index)

    for b in range(bars):
        chord_root, tones = CHORDS[prog[b % len(prog)]]
        t0 = b * bar
        section = (b // 4) % 4  # 0 인트로성, 1~3 본편
        # 베이스: 1, 3박 (+ 4박 반 경과음)
        for k, pos in enumerate([0, 2, 3.5] if section else [0, 2]):
            f = hz(root - 12 + chord_root + (7 if k == 1 and cfg["bpm"] > 100 else 0))
            add(buf, bass(f, beat * (1.8 if k < 2 else 0.45)), t0 + pos * beat, 0.32)
        # 화음 아르페지오 (8분음표)
        for s in range(8):
            pos = s * 0.5 + (sw if s % 2 else 0) * 0.5
            tone = tones[[0, 1, 2, 1, len(tones) - 1, 1, 2, 1][s] % len(tones)]
            f = hz(root + 12 + tone)
            g = 0.5 if s % 2 else 0.6
            add(buf, inst(cfg["arp"], f, beat * 1.2, rng), t0 + pos * beat, g * (0.75 if section == 0 else 1), pan=-0.35)
        # 멜로디 (2마디 모티프, 섹션 1부터)
        if section >= 1:
            half = b % 2
            for pos, ti in motif:
                if (pos >= 4) != bool(half):
                    continue
                p = pos - 4 * half
                tone = tones[ti % len(tones)] + (12 if ti >= len(tones) else 0)
                if section == 3 and rng.random() < 0.3:
                    tone = tones[(ti + 1) % len(tones)]
                f = hz(root + 24 + tone)
                add(buf, inst(cfg["lead"], f, beat * 1.4, rng), t0 + (p + (sw * 0.5 if p % 1 else 0)) * beat, 1.0, pan=0.3)
        # 반짝이 (2마디마다 한 번)
        if b % 2 == 1 and section >= 1:
            f = hz(root + 36 + tones[-1] % 12)
            add(buf, inst(cfg["top"], f, beat * 2, rng), t0 + 3.5 * beat, 0.8, pan=0.6)
        # 드럼
        if section >= 1 or b % 4 == 3:
            for pos in ([0, 2.5] if cfg["bpm"] > 100 else [0, 2]):
                add(buf, kick(), t0 + pos * beat, 0.3)
            for pos in [1, 3]:
                add(buf, snap(rng=rng), t0 + pos * beat, 1.1, pan=0.1)
        for s in range(8):
            pos = s * 0.5 + (sw if s % 2 else 0) * 0.5
            add(buf, shaker(rng=rng), t0 + pos * beat, 1.6 if s % 2 else 1.0, pan=0.45)

    # 이음매: 끝 3초 꼬리를 앞에 겹쳐 반복 재생이 자연스럽게
    n = int(total * SR)
    tail = buf[:, n:]
    buf = buf[:, :n]
    buf[:, :tail.shape[1]] += tail
    # 살짝 리버브 느낌 (짧은 지연 몇 개)
    wet = np.zeros_like(buf)
    for d, g in [(0.031, 0.25), (0.053, 0.2), (0.089, 0.15), (0.137, 0.1)]:
        k = int(d * SR)
        wet[0, k:] += buf[1, :-k] * g
        wet[1, k:] += buf[0, :-k] * g
    buf = buf + wet
    # 부드러운 소프트 클리핑 + 정규화
    buf = np.tanh(buf / (np.abs(buf).max() + 1e-9) * 1.4)
    buf /= np.abs(buf).max() + 1e-9
    return buf * 0.9


def save(name):
    OUT.mkdir(exist_ok=True)
    y = compose(name)
    raw = (y.T * 32767).astype(np.int16).tobytes()
    mp3 = OUT / f"{name}.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-af", "highpass=f=70,lowpass=f=15000,loudnorm=I=-16:TP=-1.5:LRA=9",
                    "-ar", str(SR), "-b:a", "192k", str(mp3)], input=raw, check=True)
    print(mp3, round(y.shape[1] / SR, 1), "s")


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(TRACKS)):
        save(n)
