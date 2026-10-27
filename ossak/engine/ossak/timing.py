#!/usr/bin/env python3
"""음성 파일과 원고만으로 '글자 → 시각'을 맞춘다 (받아쓰기 API 없이, 무료 한도와 무관).

원리: TTS는 말하는 동안 속도가 거의 일정하다. 소리가 나는 구간(쉼 제외)에 읽기용 글자를 고르게 나누고,
실제로 쉰 자리(무음)는 그대로 시간에 끼워 넣는다. 그러면
  - 자막: 각 어절이 실제로 말해지는 시각을 안다 (쉼 앞뒤가 정확히 맞는다)
  - 호흡: 실제로 쉰 자리가 원고의 몇 번째 글자 뒤인지 안다 → 의도한 쉼과 비교
자막 글(say/sub)과 읽기용 글(tts)이 다를 때(1959년 ↔ 천구백오십구 년)는 글자 단위로 맞춰 보고, 안 맞는 부분은 사이를 고르게 나눈다.

  python3 ossak/timing.py episodes/<편>          # 쇼츠 장면별 호흡 지도
"""
import difflib, json, pathlib, re, subprocess, sys

PAUSE = re.compile(r"\[pause[^\]]*\]")
SKIP = re.compile(r"[\s,.?!…·'\"‘’“”~\-]")


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True).stdout)


def silences(wav, min_d=0.10, db=-38):
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af", f"silencedetect=n={db}dB:d={min_d}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    D = dur(wav)
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    en += [D] * (len(st) - len(en))
    return [(max(0, s), min(D, e)) for s, e in zip(st, en)], D


class Clock:
    """말한 글자 수(0~N) → 초."""

    def __init__(self, wav, n_chars):
        sil, D = silences(wav)
        self.D, self.N = D, max(1, n_chars)
        inner = [(s, e) for s, e in sil if s > 0.03 and e < D - 0.03]
        lead = next((e for s, e in sil if s <= 0.03), 0.0)
        tail = next((s for s, e in sil if e >= D - 0.03), D)
        self.segs, t = [], lead
        for s, e in inner:
            if s > t:
                self.segs.append((t, s))
            t = max(t, e)
        if tail > t:
            self.segs.append((t, tail))
        self.voiced = sum(b - a for a, b in self.segs) or D
        self.pauses = [(s, e) for s, e in inner]

    def t(self, k):
        v = min(max(k, 0), self.N) / self.N * self.voiced
        for a, b in self.segs:
            if v <= b - a:
                return a + v
            v -= b - a
        return self.segs[-1][1] if self.segs else self.D

    def k_at(self, sec):
        """초 → 그때까지 말한 글자 수."""
        acc = 0.0
        for a, b in self.segs:
            if sec <= a:
                break
            acc += min(sec, b) - a
        return acc / self.voiced * self.N


def anchored(wav, tts):
    """쉼(무음)을 원고의 어절 경계에 붙여, 그 경계에서 시각이 정확히 맞는 시계를 만든다.
    반환: (단위→초 함수, 어절 목록, 누적 가중, 쉼 표시 {어절 번호: 쉰 길이})"""
    import numpy as np
    sp, toks, cum = spoken(tts)
    clock = Clock(wav, cum[-1])
    ends = [e for _, e, _, _ in toks]
    marks, xs, ys = {}, [0.0], [clock.segs[0][0] if clock.segs else 0.0]
    # 긴 쉼(0.2초+)의 수가 의도한 쉼 자리(문장 끝·[pause])의 수와 같으면 순서대로 짝짓는다.
    # 숫자를 길게 읽는 문장처럼 말 속도가 고르지 않아도 위치 추정이 틀리지 않는다.
    longp = [(s0, e0) for s0, e0 in clock.pauses if e0 - s0 >= 0.2]
    want = [i for i, t in enumerate(toks[:-1]) if t[3] or re.search(r"[.?!,…]$", t[0])]
    paired, last = {}, -1
    # 순서를 지키며 가까운 의도한 쉼 자리에 짝짓는다 (긴 문단은 말 속도 오차가 쌓이므로 허용 폭을 넓게)
    tol = max(5.0, cum[-1] * 0.08)
    for s0, e0 in longp:
        k = clock.k_at(s0)
        cand = [j for j in want if j > last and abs(ends[j] - k) <= tol]
        if cand:
            j = min(cand, key=lambda x: abs(ends[x] - k))
            paired[s0] = j
            last = j
    for s0, e0 in clock.pauses:
        k = clock.k_at(s0)
        if s0 in paired:
            j = paired[s0]
            marks[j] = max(marks.get(j, 0), e0 - s0)
            if ends[j] > xs[-1] and s0 > ys[-1]:
                xs += [ends[j], ends[j] + 1e-6]
                ys += [s0, e0]
            continue
        j = min(range(len(ends)), key=lambda i: abs(ends[i] - k))
        near = [i for i in range(len(ends)) if abs(ends[i] - k) <= 2.0 and (toks[i][2] or toks[i][3])]
        if near:
            j = min(near, key=lambda i: abs(ends[i] - k))
        if abs(ends[j] - k) > 2.5 or j >= len(toks) - 1:
            continue
        marks[j] = max(marks.get(j, 0), e0 - s0)
        if e0 - s0 >= 0.15 and ends[j] > xs[-1] and s0 > ys[-1]:
            xs += [ends[j], ends[j] + 1e-6]
            ys += [s0, e0]
    xs.append(cum[-1]); ys.append(clock.segs[-1][1] if clock.segs else clock.D)
    # 쉼과 쉼 사이는 소리 나는 구간만 고르게 (짧은 무음은 무시)
    f = lambda u: float(np.interp(u, xs, ys))
    return f, toks, cum, marks, clock


def spoken(tts):
    """읽기용 글 → (정규화 글자열, 어절 목록[(글, 끝 위치(가중), 쉼표·문장부호, [pause] 뒤)], 글자별 누적 가중 위치)
    문장 끝 음절은 길게 읽으므로 가중을 준다(마침표·물음표 1.8, 쉼표 1.3)."""
    s, toks, cum = "", [], [0.0]
    for tok in re.split(r"(\[pause[^\]]*\]|\s+)", tts):
        if not tok or tok.isspace():
            continue
        if tok.startswith("[pause"):
            if toks:
                toks[-1][3] = True
            continue
        core = SKIP.sub("", tok)
        last = 1.5 if re.search(r"[.?!]$", tok) else 1.3 if re.search(r"[,…]$", tok) else 1.0
        for j, _ in enumerate(core):
            cum.append(cum[-1] + (last if j == len(core) - 1 else 1.0))
        s += core
        toks.append([tok, cum[-1], bool(re.search(r"[,.?!…]$", tok)), False])
    return s, toks, cum


def align(display, spoken_str):
    """자막 글자 i → 읽기용 글자 위치(실수). 숫자처럼 안 맞는 부분은 고르게 나눈다."""
    d = SKIP.sub("", display)
    sm = difflib.SequenceMatcher(None, d, spoken_str, autojunk=False)
    anchors = [(0, 0.0)]
    for a, b, n in sm.get_matching_blocks():
        for j in range(n):
            anchors.append((a + j, float(b + j)))
    anchors.append((len(d), float(len(spoken_str))))
    anchors.sort()
    xs, ys = [], []
    for x, y in anchors:
        if not xs or (x > xs[-1] and y >= ys[-1]):
            xs.append(x); ys.append(y)
    import numpy as np
    return d, lambda i: float(np.interp(i, xs, ys))


def word_times(wav, display, tts):
    """자막 어절마다 (시작, 끝) 초."""
    import numpy as np
    sp, _, cum = spoken(tts)
    f, _, cum, _, _ = anchored(wav, tts)
    _, m = align(display, sp)
    w = lambda x: float(np.interp(x, range(len(cum)), cum))      # 글자 위치 → 가중 위치
    toks = display.split()
    out, pos = [], 0
    for t in toks:
        n = len(SKIP.sub("", t))
        a, b = w(m(pos)), w(m(pos + n))
        out.append((f(a + 1e-5), f(b)))
        pos += n
    return toks, out


def breath(wav, tts, wrong_min=0.22, need_min=0.12):
    """(호흡 지도 문자열, 엉뚱한 쉼 [(어절, 초)], 빠진 쉼 수)"""
    # 위치 추정은 ±1글자 오차가 있으니, 1.3글자 안에 의도한 쉼 자리가 있으면 그쪽으로 본다 (anchored)
    _, toks, _, marks, _ = anchored(wav, tts)
    wrong = [(toks[j][0], round(d, 2)) for j, d in marks.items()
             if d >= wrong_min and not (toks[j][2] or toks[j][3])]
    missing = sum(1 for j, tk in enumerate(toks) if tk[3] and j < len(toks) - 1 and marks.get(j, 0) < need_min)
    line = ""
    for j, tk in enumerate(toks):
        line += tk[0]
        if j in marks:
            line += (" //" if marks[j] >= 0.25 else " /") + f"({marks[j]:.2f})"
        elif tk[3] and j < len(toks) - 1:
            line += " (쉼 없음!)"
        line += " "
    return line.strip(), wrong, missing


def main():
    ep = pathlib.Path(sys.argv[1])
    sc = json.loads((ep / "short.json").read_text())["scenes"]
    paras = []                      # short.py와 같은 문단 묶기 ("cont": true)
    for i, s in enumerate(sc):
        fx = s.get("sfx", [])
        fx = [fx] if isinstance(fx, str) else fx
        if i and s.get("cont") and not ({"hit", "knock"} & set(fx)):
            paras[-1].append(i)
        else:
            paras.append([i])
    bad = 0
    for pi, idx in enumerate(paras, 1):
        wav = ep / "short_audio" / f"p{pi:02d}.wav"
        tts = " ".join(sc[i].get("tts", sc[i]["say"]).strip() for i in idx)
        line, wrong, missing = breath(wav, tts, wrong_min=0.13)
        flag = "" if not wrong and not missing else f"   ← 엉뚱한 쉼 {wrong} / 빠진 쉼 {missing}"
        bad += bool(flag)
        print(f"문단{pi:02d} 실제: {line}   ({dur(wav):.1f}s){flag}")
    print(f"문제 문단 {bad}개")


if __name__ == "__main__":
    main()
