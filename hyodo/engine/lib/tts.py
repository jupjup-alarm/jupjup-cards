"""구글 TTS(Chirp3-HD) 내레이션. 쉼은 대본 표기로 정확히 제어한다.

대본(say) 표기
  /            숨 쉼(0.18초). 이 자리에서 구절을 나눠 따로 읽고 정확한 무음을 넣는다.
  문장 끝 . ? !  문장 쉼(0.32초). '누가.'처럼 6자 이하 이름표 문장 뒤는 0.22초.
  (2026-11-04 벤치마크 분석: 터진 영상 분당 약 300음절, 우리 215 → 속도 1.15배·쉼 축소)
  {표시|읽기}   자막에는 앞, 내레이션은 뒤로 읽는다. 예: {1397|일삼구칠}, {6%|6퍼센트}
  / 가 없는 곳은 이어 말한다: 구절 안에서 TTS가 스스로 낸 0.15초 넘는 쉼은 0.12초로 줄인다.

line(text) → (wav, 길이, segs). segs = [{"text": 자막용 구절, "start": 줄 안 시작, "dur": 길이}]
"""
import array, base64, hashlib, json, re, subprocess, sys, urllib.request, pathlib, wave
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import env
KEY = env.load()["GOOGLE_TTS_KEY"]
SR = 24000
P_BREATH, P_SENT, P_LABEL = 0.18, 0.32, 0.22
RATE = 1.15
SIL_DB, MAX_IN, KEEP_IN, EDGE = -45.0, 0.15, 0.12, 0.03

DISP = re.compile(r"\{([^|{}]*)\|([^|{}]*)\}")


def spoken(t):
    return re.sub(r"\s+", " ", DISP.sub(lambda m: m.group(2), t)).strip()


def shown(t):
    return re.sub(r"\s+", " ", DISP.sub(lambda m: m.group(1), t)).strip()


def phrases(text):
    """say 한 줄 → [(구절, 뒤 쉼 초)]. 마지막 구절의 쉼은 0."""
    out = []
    sents = [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s.strip()]
    for si, s in enumerate(sents):
        parts = [p.strip() for p in s.split("/") if p.strip()]
        for pi, p in enumerate(parts):
            if pi < len(parts) - 1:
                gap = P_BREATH
            elif si < len(sents) - 1:
                gap = P_LABEL if len(shown(p).rstrip(".?!")) <= 6 else P_SENT
            else:
                gap = 0.0
            out.append((p, gap))
    return out


def synth(text, voice, out, rate=RATE):
    body = {"input": {"text": spoken(text)}, "voice": {"languageCode": "ko-KR", "name": voice},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": SR, "speakingRate": rate}}
    req = urllib.request.Request(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={KEY}",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        pathlib.Path(out).write_bytes(base64.b64decode(json.loads(r.read())["audioContent"]))


def read_pcm(path):
    with wave.open(str(path)) as w:
        a = array.array("h", w.readframes(w.getnframes()))
    return a


def write_pcm(path, a):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())


def tidy(a):
    """앞뒤 무음을 0.03초만 남기고 자르고, 구절 안의 긴 쉼(>0.15초)은 0.12초로 줄인다."""
    import math
    fr = int(SR * 0.01)
    n = len(a) // fr
    loud = []
    for i in range(n):
        seg = a[i * fr:(i + 1) * fr]
        rms = math.sqrt(sum(x * x for x in seg) / fr) or 1
        loud.append(20 * math.log10(rms / 32768) > SIL_DB)
    if not any(loud):
        return a
    first = loud.index(True); last = n - 1 - loud[::-1].index(True)
    e = int(EDGE / 0.01)
    keep, i = [], max(0, first - e)
    end = min(n - 1, last + e)
    while i <= end:
        if not loud[i]:
            j = i
            while j <= end and not loud[j]:
                j += 1
            run = j - i
            if run * 0.01 > MAX_IN and i > first and j <= last:
                k = int(KEEP_IN / 0.01); h = k // 2
                keep.append((i, i + h)); keep.append((j - (k - h), j))
            else:
                keep.append((i, j))
            i = j
        else:
            keep.append((i, i + 1)); i += 1
    out = array.array("h")
    for s, t in keep:
        out.extend(a[s * fr:t * fr])
    return out


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).strip())


def clip(text, voice, cache_dir, rate):
    h = hashlib.sha1(f"{voice}|{rate}|{spoken(text)}".encode()).hexdigest()[:12]
    raw, tid = cache_dir / f"{h}.wav", cache_dir / f"{h}_t.wav"
    if not raw.exists():
        synth(text, voice, raw, rate)
    if not tid.exists():
        write_pcm(tid, tidy(read_pcm(raw)))
    return tid


def line(text, voice, cache_dir, rate=RATE):
    cache_dir = pathlib.Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    ph = phrases(text)
    key = hashlib.sha1(f"{voice}|{rate}|{json.dumps(ph, ensure_ascii=False)}|v2".encode()).hexdigest()[:12]
    out = cache_dir / f"L{key}.wav"
    pcm, segs, t = array.array("h"), [], 0.0
    for p, gap in ph:
        a = read_pcm(clip(p, voice, cache_dir, rate))
        d = len(a) / SR
        segs.append({"text": shown(p), "start": round(t, 3), "dur": round(d, 3), "gap": gap})
        pcm.extend(a); pcm.extend(array.array("h", bytes(2 * int(SR * gap))))
        t += d + gap
    if not out.exists():
        write_pcm(out, pcm)
    return out, round(len(pcm) / SR, 3), segs


if __name__ == "__main__":
    print(phrases("누가. 10월에 신청하고, / {14곳|열네 곳}의 앱에서 만들면 됩니다. 아직 확정은 아닙니다."))
