#!/usr/bin/env python3
"""릴스 내레이션 '호흡 지도' — 실제 음성에서 어디서 쉬었는지 문장 위에 표시하고, 의도와 맞는지 잰다.

  python3 ossak/breath.py episodes/<편>

각 beat 음성(reel_audio/NN.wav)에서 0.12초 이상 조용한 구간을 찾고, Cloudflare Whisper 단어 시각으로
가장 가까운 단어 경계에 표시한다:  /  = 짧은 쉼(0.12~0.25초),  //  = 긴 쉼(0.25초 이상).
의도한 쉼 = 원고 tts(없으면 say)의 쉼표·마침표·물음표·말줄임표·[pause …] 자리.
- 엉뚱한 쉼: 의도하지 않은 자리에서 0.22초 이상 쉼 (예: '숲으로 이어진 / 발자국')
- 빠진 쉼: [pause …]를 넣었는데 0.15초 미만으로 이어 읽음
reel.py가 음성을 만들 때 이 검사를 써서, 문제가 있으면 속도를 살짝 바꿔 최대 3번 다시 만든다.
"""
import base64, json, pathlib, re, subprocess, sys, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cf import load_env  # noqa: E402

PUNCT = re.compile(r"[\s,.?!…·'\"‘’“”~\-]")


def norm(t):
    return PUNCT.sub("", re.sub(r"\[pause[^\]]*\]", "", t))


def silences(wav, min_d=0.12):
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af", f"silencedetect=n=-38dB:d={min_d}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    total = dur(wav)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return [(s, e) for s, e in zip(st, en) if s > 0.05 and e < total - 0.05]


def dur(wav):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(wav)], capture_output=True, text=True).stdout)


def words(wav):
    acc, tok = load_env()
    mp3 = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ar", "16000", "-ac", "1", "-f", "mp3", "-"],
                         capture_output=True).stdout
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/openai/whisper-large-v3-turbo",
        data=json.dumps({"audio": base64.b64encode(mp3).decode(), "language": "ko"}).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=90))["result"]
    return [w for s in r.get("segments", []) for w in s.get("words", [])]


def intended(tts):
    """의도한 쉼 자리: 정규화한 글자 수 기준 비율(0~1) 목록과, [pause] 자리(반드시 쉬어야 함) 목록."""
    total = len(norm(tts)) or 1
    soft, hard, pos = [], [], 0
    for tok in re.split(r"(\[pause[^\]]*\]|\s+)", tts):
        if not tok or tok.isspace():
            continue
        if tok.startswith("[pause"):
            hard.append(pos / total)
            soft.append(pos / total)
            continue
        pos += len(norm(tok))
        if re.search(r"[,.?!…]$", tok):
            soft.append(pos / total)
    return soft, hard


def analyze(wav, tts):
    """(호흡 지도 문자열, 엉뚱한 쉼 목록, 빠진 쉼 수)"""
    ws, sil = words(wav), silences(wav)
    total_chars = sum(len(norm(w["word"])) for w in ws) or 1
    ends, acc = [], 0
    for w in ws:
        acc += len(norm(w["word"]))
        ends.append(acc / total_chars)
    soft, hard = intended(tts)
    marks, wrong = {}, []
    for s, e in sil:
        mid = (s + e) / 2
        k = max((j for j, w in enumerate(ws) if w["end"] <= mid + 0.15), default=None)
        if k is None or k >= len(ws) - 1:
            continue
        marks[k] = max(marks.get(k, 0), e - s)
    for k, d in marks.items():
        if d >= 0.22 and not any(abs(ends[k] - f) < 0.07 for f in soft):
            wrong.append((ws[k]["word"].strip(), round(d, 2)))
    for w in ws:                       # '음,' '어' 같은 군소리
        t = norm(w["word"])
        if t in ("음", "어", "으음", "흠") and t not in norm(tts):
            wrong.append(("군소리:" + t, 0))
    missing = 0
    for f in hard:
        near = [d for k, d in marks.items() if abs(ends[k] - f) < 0.08]
        if not near or max(near) < 0.15:
            missing += 1
    line = ""
    for j, w in enumerate(ws):
        line += w["word"]
        if j in marks:
            line += (" //" if marks[j] >= 0.25 else " /") + f"({marks[j]:.2f})"
    return line.strip(), wrong, missing


def main():
    ep = pathlib.Path(sys.argv[1])
    src = ep / "story.json" if (ep / "story.json").exists() else ep / "episode.json"
    beats = json.loads(src.read_text())["reel"]["beats"]
    bad = 0
    for i, b in enumerate(beats, 1):
        wav = ep / "reel_audio" / f"{i:02d}.wav"
        tts = b.get("tts", b["say"])
        line, wrong, missing = analyze(wav, tts)
        flag = "" if not wrong and not missing else f"   ← 엉뚱한 쉼 {wrong} / 빠진 쉼 {missing}"
        bad += bool(flag)
        print(f"{i:02d} 의도: {tts}")
        print(f"   실제: {line}   ({dur(wav):.1f}s){flag}")
    print(f"문제 beat {bad}개")


if __name__ == "__main__":
    main()
