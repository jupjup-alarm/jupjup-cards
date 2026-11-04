#!/usr/bin/env python3
"""오싹알람 쇼츠 엔진 — 세로 전체화면 그림 + 내레이션 + 단어 자막으로 1080×1920 영상을 만든다.
같은 파일을 유튜브 쇼츠와 인스타 릴스에 올린다.

  python3 ossak/short.py episodes/<편> --images          # 빠진 세로 그림만 그린다 (기본 864×1536 약 156뉴런, SHORT_IMG=576x1024로 줄일 수 있음)
  python3 ossak/short.py episodes/<편> --images --only v03 --force
  python3 ossak/short.py episodes/<편> --date 2026-10-28  # 영상 + 발행 행(short_rows.json)
  python3 ossak/short.py episodes/<편> --date 2026-10-28 --rows-only

원고: episodes/<편>/short.json
{
  "id": "W-0001", "no": 1, "series": "세계기담", "format": "story" | "loop", "mood": "mystery" | "horror" | "wonder",  # wonder = 신기형(2026-11-03), 화면·소리는 mystery와 같음
  "title": "디아틀로프 고개",                      # 사건 이름(시트용)
  "hook": ["한겨울, 신발 두고", "텐트를 떠난 9명"],  # 화면 위 고정 제목 2줄 (줄당 10자 안팎)
  "accent_word": "9명",
  "images": [{"id": "v01", "prompt": "영문 장면 묘사", "with_character": false, "nop": true,
              "bright": true,      # 밝고 선명하게 (첫 화면·현상 장면 — 구성 규칙 1)
              "ref": "v02"}],      # 같은 인물 이어 그리기 (먼저 그린 그림을 참고로)
  "scenes": [
    {"say": "자막·내레이션 문장", "tts": "읽기용 표기(선택)", "sub": "자막이 달라야 할 때(선택)",
     "img": "v01", "move": "in|out|up|down|left|right", "zoom": 1.0, "focus": [0.5, 0.5],
     "sfx": "hit",            # 반전 직전: 0.45초 숨(소리는 줄이기만) + 낮은 효과음 (한 편에 한 번). 공포형은 그 앞에 긴장음이 차오른다
                              # "knock": 노크 세 번 / "heartbeat": 낮은 심장 소리 / "thud": 떨어져 박히는 '퍽' / "pop" / "paper"
                              # 여러 개면 ["thud", "hit"]. 그림 전환 '휙'·큰 글자 '톡'·증거 '종이'는 자동
     "hold": 0.0,             # 말이 끝난 뒤 그림을 더 보여줄 초
     "emph": ["9명"],         # 자막에서 말머리 색으로 칠할 단어
     # ── 편집 (2026-11-04 터진 영상 분석 반영 — 화면이 1.5초 넘게 멈추지 않는다) ──
     "shots": [{"img": "v02", "zoom": 1.4, "focus": [0.4, 0.6], "move": "in", "w": 1}],   # 장면 안에서 다른 그림으로 넘어갈 때만.
                              # 같은 그림 구도만 끊는 컷은 쓰지 않는다(2026-11-04 사용자: 정신없다). 한 장면 = 한 그림 + 천천히 움직임
     "big": "개구리 알?",      # 화면 가운데 큰 핵심어 (톡 소리와 함께 튀어나옴). {"text": "...", "at": 0.3}도 됨
     "proof": {"img": "proof/x.jpg", "hl": [x0, y0, x1, y1], "credit": "White Pine News 1876.3.18 · 미국 의회도서관"}
                              # 실물 증거(원본 신문·사진·문서). 전체 → hl 부분 확대 두 컷, hl은 그림 비율(0~1)로 형광펜
  ],
  "src_line": "1876 · 미국 켄터키",   # 화면 아래쪽 작은 고정 글자 — 연도·지명·출처는 말 대신 여기 (구성 규칙 2)
  "faces": true,                       # 가상 인물 얼굴·표정 허용 (2026-11-04 사용자 결정, 기본 true). 실존 인물 닮은 얼굴 금지

  "youtube": {"title": "제목 15~25자", "summary": "설명란 두세 줄(답 없이)", "pinned": "고정 댓글 질문"},
  "instagram": {"caption": "첫 줄 훅 … (선택, 없으면 자동)"},
  "sources": "출처: …", "tags": "#세계기담 #디아틀로프", "risk": "저",
  "hook_type": "권위×초자연(임금이 귀신 안부)",   # 훅 유형 — 주간 분석이 유형별 성과를 비교한다
  "adapted": true                                   # 각색했으면 설명란 문구가 바뀐다
}

화면: 위 300px·아래 420px·오른쪽 140px에는 글자를 두지 않는다. 제목은 위(y≈310~), 자막은 가운데 아래(y≈1130),
부기 로고는 오른쪽 위. 첫 프레임부터 제목·그림·첫 자막이 보인다(로고 인트로·페이드인 없음).
소리: 내레이션(구글 Umbriel) + 끊기지 않는 바닥 소리(바람 + 낮은 화음, 공포형은 낮은 울림) + 그림이 바뀔 때 '휙', 큰 글자 '톡',
증거 '종이', sfx 장면 효과음. 문장 사이·반전 직전에도 소리를 비우지 않는다(줄일 뿐). 끝은 마지막 말 0.35초 뒤 바로 끝.
"""
import argparse, base64, datetime, json, math, os, pathlib, re, subprocess, sys, time, urllib.error, urllib.request, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from compose import font, C  # noqa: E402
from cf import load_env, multipart, MODELS  # noqa: E402
from render import STYLE  # noqa: E402
from reel import speak, dur  # noqa: E402
from timing import word_times as tts_word_times, anchored, breath, SKIP  # noqa: E402


def breathe(t):
    """읽기용 글의 쉼표·말줄임표 → [pause short] (이미 있으면 그대로)."""
    t = re.sub(r"\s*…\s*", " [pause short] ", t.strip())
    t = re.sub(r",\s*(?!\[pause)", " [pause short] ", t)
    t = re.sub(r",\s*(\[pause)", r" \1", t)
    t = re.sub(r"(\[pause short\]\s*){2,}", "[pause short] ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def norm(t):
    return SKIP.sub("", re.sub(r"\[pause[^\]]*\]", "", t))

ENGINE = pathlib.Path(__file__).resolve().parent.parent
REPO_OSSAK = ENGINE.parent
BASE = "https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/ossak/"
W, H, FPS, SR = 1080, 1920, 30, 48000
SAFE_R = 140                        # 오른쪽 버튼 자리
TITLE_Y, SUB_Y, SUB_MAXW = 318, 1130, 840
LEAD, GAP, HIT_GAP, PGAP = 0.05, 0.22, 0.45, 0.38
END_TAIL = 0.35                     # 마지막 말 뒤 꼬리 (터진 영상은 0.4초 안에 끝남 — 2026-11-04)
SHOT_MAX = 1.7                      # 자동 컷 간격 상한(초)
SRC_Y = 1468
SERIES = {"세계기담": ("#F2B544", "amber"), "새벽괴담": ("#3FB8A8", "teal"), "미제파일": ("#E8693A", "orange"),
          "그날의 기록": ("#E8693A", "orange"), "그 후": ("#9AA3B8", "silver")}
CHARACTER = ("Boogi, a small round owl archivist mascot: dark slate-navy feathers, two pointed ear tufts, large glowing "
             "amber eyes behind thin round silver glasses, a small amber diamond-shaped beak, a lighter navy chevron-patterned "
             "belly, short wings, carrying a small cream notebook and a little amber lantern. Cute, simple, flat webtoon character design.")
FACES = ("Human characters are fictional ordinary people with clearly visible, expressive faces and readable emotions "
         "(surprise, disgust, fear), drawn in webtoon style, not resembling any real or famous person. ")
BRIGHT = (" Bright clear daylight and vivid natural colors for this scene, high contrast, the strange subject large, sharp and "
          "unmistakable in the middle of the frame.")
NOP = " Absolutely no human figures, silhouettes or shadows of people anywhere in the image."
HORROR = " Deep shadows, a single cold light source, unsettling empty space, nothing explicit."
VERT = (" Tall vertical 9:16 composition filling the whole frame edge to edge (no black bars, no borders): "
        "the key subject sits in the middle of the frame, and the upper part of the picture shows open sky, ceiling or wall "
        "continuing the scene, with no important detail at the very top.")


# ───────── 세로 그림 ─────────
def gen_image(spec, im, out):
    acc, tok = load_env()
    prompt = im["prompt"] + VERT
    if im.get("nop"):
        prompt += NOP
    if spec.get("mood") == "horror":
        prompt += HORROR
    refs = {}
    if im.get("with_character"):
        prompt += " The owl must look exactly like the owl character in the reference image: " + CHARACTER
        refs = {"input_image_0": ("boogi.png", (ENGINE / "refs" / "boogi_sheet.png").read_bytes(), "image/png")}
    if im.get("ref"):                                   # 같은 인물·장소를 이어 그릴 때: 먼저 그린 그림을 참고로
        rp = out.parent / f"{im['ref']}.jpg"
        if rp.exists():
            refs = {"input_image_0": ("ref.jpg", rp.read_bytes(), "image/jpeg")}
            prompt += " Keep the same character (same face, beard, hat and clothes) as in the reference image."
    if im.get("bright"):
        prompt += BRIGHT
    style = STYLE.format(accent=SERIES.get(spec["series"], ("", "amber"))[1])
    if spec.get("faces", True) and not im.get("nop"):     # 2026-11-04 사용자 결정: 가상 인물 얼굴 허용
        style = style.replace("Any human figures are faceless silhouettes with no facial features. ", FACES)
    prompt += " " + style
    iw, ih = (int(x) for x in os.environ.get("SHORT_IMG", "864x1536").split("x"))   # 장당 약 156뉴런 (512² 칸 6개 × 26.05)
    body, ctype = multipart({"prompt": prompt, "width": iw, "height": ih, **({"seed": im["seed"]} if im.get("seed") else {})}, refs)
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{MODELS['klein']}"
    for tries in range(4):
        try:
            t = time.time()
            req = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Authorization": f"Bearer {tok}", "Content-Type": ctype})
            data = json.loads(urllib.request.urlopen(req, timeout=170).read())
            out.write_bytes(base64.b64decode(data["result"]["image"]))
            print(im["id"], f"{time.time() - t:.0f}s")
            return True
        except urllib.error.HTTPError as e:
            print(im["id"], "HTTP", e.code, e.read()[:200])
            if e.code in (429, 500, 502, 503) and tries < 3:
                time.sleep(10 * (tries + 1))
                continue
            return False
    return False


def images(ep, spec, only=None, force=False):
    d = ep / "vpanels"
    d.mkdir(exist_ok=True)
    for im in spec["images"]:
        if only and im["id"] not in only:
            continue
        out = d / f"{im['id']}.jpg"
        if out.exists() and not force:
            continue
        gen_image(spec, im, out)
    sheet(ep, spec)


def sheet(ep, spec):
    """세로 그림 축소 시트 (검수용)."""
    ims = [ep / "vpanels" / f"{im['id']}.jpg" for im in spec["images"]]
    ims = [p for p in ims if p.exists()]
    if not ims:
        return
    tw, th, cols = 216, 384, 6
    rows = (len(ims) + cols - 1) // cols
    s = Image.new("RGB", (tw * cols, (th + 30) * rows), C["bg"])
    d = ImageDraw.Draw(s)
    for i, p in enumerate(ims):
        x, y = (i % cols) * tw, (i // cols) * (th + 30)
        s.paste(Image.open(p).convert("RGB").resize((tw, th)), (x, y + 30))
        d.text((x + 6, y + 4), p.stem, font=font("sans", 20, 700), fill=C["ink"])
    s.save(ep / "vpanels_sheet.jpg", quality=80)


# ───────── 소리 ─────────
def read_wav(p):
    with wave.open(str(p), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def brown(n, rng):
    x = np.cumsum(rng.standard_normal(n).astype(np.float32))
    k = int(SR * 0.5)                       # 느린 흐름 제거(고역 통과)
    ma = np.convolve(x, np.ones(k, dtype=np.float32) / k, mode="same")
    x = x - ma
    k2 = 40                                 # 저역 통과
    x = np.convolve(x, np.ones(k2, dtype=np.float32) / k2, mode="same")
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-9)


def hit_sound():
    t = np.arange(int(SR * 2.2)) / SR
    f = 38 + 34 * np.exp(-t * 3)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    rng = np.random.default_rng(7)
    n = rng.standard_normal(len(t)).astype(np.float32)
    n = np.convolve(n, np.ones(60) / 60, mode="same") * np.exp(-t * 9) * 3
    return (0.55 * boom + 0.25 * n).astype(np.float32)


def knock_sound():
    """나무 문을 두드리는 둔탁한 소리 세 번."""
    one_t = np.arange(int(SR * 0.25)) / SR
    rng = np.random.default_rng(3)
    click = np.convolve(rng.standard_normal(len(one_t)), np.ones(25) / 25, mode="same") * np.exp(-one_t * 60) * 2.2
    body = np.sin(2 * np.pi * 115 * one_t) * np.exp(-one_t * 28)
    one = (0.5 * body + 0.5 * click).astype(np.float32)
    out = np.zeros(int(SR * 1.3), np.float32)
    for k, a in enumerate((0.0, 0.42, 0.84)):
        i = int(a * SR)
        out[i:i + len(one)] += one * (1.0 if k < 2 else 0.85)
    return out * 0.6


def heartbeat(dur_s):
    """낮은 심장 소리 (두-근), 0.95초 간격."""
    t1 = np.arange(int(SR * 0.16)) / SR
    th = (np.sin(2 * np.pi * 48 * t1) * np.exp(-t1 * 26)).astype(np.float32)
    out = np.zeros(int(SR * dur_s) + 1, np.float32)
    t = 0.0
    while t < dur_s - 0.3:
        for off, g in ((0, 1.0), (0.24, 0.7)):
            i = int((t + off) * SR)
            seg = th[:max(0, len(out) - i)] * g
            out[i:i + len(seg)] += seg
        t += 0.95
    return out * 0.45


def riser(dur_s=2.6):
    """효과음 직전 서서히 차오르는 긴장음."""
    t = np.arange(int(SR * dur_s)) / SR
    rng = np.random.default_rng(5)
    nz = np.convolve(rng.standard_normal(len(t)), np.ones(90) / 90, mode="same")
    f = 55 + 30 * (t / dur_s) ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = (t / dur_s) ** 2.2
    return ((0.6 * nz * 6 + 0.4 * tone) * env * 0.12).astype(np.float32)


def pad(n, rng):
    """낮게 깔리는 화음 — 문장 사이에도 소리가 비지 않게 (2026-11-04: 터진 영상 12편 모두 무음 0회)."""
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    for f, g, lfo in ((110.0, 1.0, 0.07), (164.81, 0.7, 0.05), (220.0, 0.45, 0.09), (261.63, 0.35, 0.06)):
        ph = rng.uniform(0, 2 * np.pi)
        out += (g * np.sin(2 * np.pi * f * t + ph) * (0.65 + 0.35 * np.sin(2 * np.pi * lfo * t + ph))).astype(np.float32)
    k = 24
    out = np.convolve(out, np.ones(k, dtype=np.float32) / k, mode="same")
    return out / (np.max(np.abs(out)) + 1e-9)


def whoosh():
    """컷이 바뀔 때 작은 '휙'."""
    n = int(SR * 0.3)
    t = np.arange(n) / SR
    rng = np.random.default_rng(21)
    x = rng.standard_normal(n).astype(np.float32)
    x = x - np.convolve(x, np.ones(30) / 30, mode="same")           # 고역만
    x = np.convolve(x, np.ones(6) / 6, mode="same")
    env = np.sin(np.pi * np.clip(t / 0.3, 0, 1)) ** 2
    return (x * env * 0.05).astype(np.float32)


def pop():
    """큰 글자가 튀어나올 때 '톡'."""
    t = np.arange(int(SR * 0.09)) / SR
    f = 820 - 2600 * t
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45) * 0.16).astype(np.float32)


def thud():
    """무언가 떨어져 박히는 '퍽'."""
    t = np.arange(int(SR * 0.45)) / SR
    f = 70 + 60 * np.exp(-t * 18)
    rng = np.random.default_rng(17)
    nz = np.convolve(rng.standard_normal(len(t)), np.ones(12) / 12, mode="same") * np.exp(-t * 40)
    return ((np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.5 + nz * 0.35) * 0.7).astype(np.float32)


def paper():
    """증거 화면이 나올 때 종이 넘기는 소리."""
    n = int(SR * 0.35)
    t = np.arange(n) / SR
    rng = np.random.default_rng(29)
    x = rng.standard_normal(n).astype(np.float32)
    x = x - np.convolve(x, np.ones(12) / 12, mode="same")
    crack = (rng.random(n) < 0.004) * rng.standard_normal(n) * 3
    env = np.clip(t / 0.05, 0, 1) * np.exp(-t * 7)
    return ((x + crack) * env * 0.07).astype(np.float32)


FX = {"whoosh": whoosh, "pop": pop, "thud": thud, "paper": paper}


def mix(total, placements, hits, silences, horror, knocks=(), beats=(), events=()):
    n = int(total * SR) + 1
    out = np.zeros(n, np.float32)
    for start, wav in placements:
        a = int(start * SR)
        out[a:a + len(wav)] += wav[:max(0, n - a)]
    rng = np.random.default_rng(11)
    # 바닥 소리: 터진 영상 바닥 -20~-37dB, 우리는 -40~-44dB였다 (2026-11-04 분석) → 바람 + 화음으로 채운다
    amb = brown(n, rng) * (0.03 if horror else 0.022)
    if horror:
        t = np.arange(n) / SR
        amb += (0.016 * np.sin(2 * np.pi * 55 * t) + 0.010 * np.sin(2 * np.pi * 82.4 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t))
    else:
        amb += pad(n, rng) * 0.03
    env = np.ones(n, np.float32)
    fade = int(SR * 0.3)
    env[-fade:] *= np.linspace(1, 0.5, fade)
    for s, e in silences:                    # 반전 직전: 소리를 비우지 않고 줄이기만 한다
        a, b = int(s * SR), int(e * SR)
        r = int(0.1 * SR)
        env[a:a + r] *= np.linspace(1, 0.45, r)[:len(env[a:a + r])]
        env[a + r:b] *= 0.45
    out += amb * env
    def put(sig, t0):
        a = int(t0 * SR)
        if a < 0:
            sig, a = sig[-a:], 0
        seg = sig[:max(0, n - a)]
        out[a:a + len(seg)] += seg
    for t0 in knocks:
        put(knock_sound(), t0)
    for b0, b1 in beats:
        put(heartbeat(b1 - b0), b0)
    if horror:
        for s0, _ in silences:                # 정적 직전까지 차오르는 긴장음
            r = riser()
            put(r, s0 - len(r) / SR)
    hs = hit_sound()
    for t0 in hits:
        put(hs, t0)
    cache = {}
    for t0, name in events:
        if name not in cache:
            cache[name] = FX[name]()
        put(cache[name], t0)
    peak = np.max(np.abs(out)) or 1
    if peak > 0.97:
        out *= 0.97 / peak
    return out


def write_wav(p, x):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


# ───────── 자막 시각 ─────────
def chunks(toks, times, max_words=4, max_chars=11):
    """2~4어절 덩어리. 쉼표·마침표 뒤에서 끊는다."""
    res, cur = [], []
    for i, t in enumerate(toks):
        cur.append(i)
        chars = sum(len(norm(toks[j])) for j in cur)
        nxt = len(norm(toks[i + 1])) if i + 1 < len(toks) else 0
        if re.search(r"[,.?!…]$", t) or len(cur) >= max_words or chars + nxt > max_chars:
            res.append(cur); cur = []
    if cur:
        if res and len(cur) == 1 and len(norm(toks[cur[0]])) <= 2:
            res[-1] += cur
        else:
            res.append(cur)
    return [(" ".join(toks[j] for j in c), times[c[0]][0]) for c in res]


def clean(s):
    s = re.sub(r"[,.](?=\s|$)", "", s)
    return s.replace("…", "…").strip()


# ───────── 그림 그리기 ─────────
def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def vignette():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = (x - W / 2) / (W / 2), (y - H / 2) / (H / 2)
    r = np.sqrt(dx ** 2 * 0.9 + dy ** 2 * 0.55)
    a = np.clip((r - 0.55) / 0.7, 0, 1) ** 1.6 * 150
    top = np.clip(1 - y / 820, 0, 1) ** 1.4 * 170          # 제목 읽히게 위쪽 어둡게
    sub = np.exp(-((y - SUB_Y - 40) / 230) ** 2) * 70       # 자막 주변
    m = np.clip(np.maximum(a, top) + sub, 0, 215).astype(np.uint8)
    return Image.fromarray(m, "L")


def logo():
    sh = Image.open(ENGINE / "refs" / "boogi_sheet.png").convert("RGB")
    head = sh.crop((404, 318, 616, 530)).resize((64, 64), Image.LANCZOS)
    m = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 63, 63), fill=255)
    f = font("serif", 30)
    tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength("오싹알람", font=f))
    lg = Image.new("RGBA", (64 + 14 + tw + 22, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(lg)
    d.rounded_rectangle((20, 6, lg.width - 1, 58), radius=26, fill=(8, 11, 22, 170))
    lg.paste(head, (0, 0), m)
    d.ellipse((0, 0, 63, 63), outline=(242, 181, 68, 230), width=2)
    d.text((64 + 12, 32), "오싹알람", font=f, fill=(237, 230, 214, 235), anchor="lm")
    return lg


def title_layer(hook, accent_word, accent):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    size = 80
    f = font("serif", size)
    while max(d.textlength(l, font=f) for l in hook) > W - 120 and size > 56:
        size -= 4
        f = font("serif", size)
    y = TITLE_Y
    for line in hook[:2]:
        segs = re.split(f"({re.escape(accent_word)})", line) if accent_word else [line]
        lw = d.textlength(line, font=f)
        x = (W - lw) / 2
        for seg in segs:
            if not seg:
                continue
            col = accent if accent_word and seg == accent_word else (240, 234, 220)
            d.text((x, y), seg, font=f, fill=col, stroke_width=6, stroke_fill=(5, 7, 14))
            x += d.textlength(seg, font=f)
        y += int(size * 1.28)
    return lay


def sub_image(text, emph, accent):
    f = font("sans", 74, 800)
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    toks = text.split()
    lines, cur = [], []
    for t in toks:
        if cur and d.textlength(" ".join(cur + [t]), font=f) > SUB_MAXW:
            lines.append(cur); cur = []
        cur.append(t)
    lines.append(cur)
    lh = 98
    img = Image.new("RGBA", (SUB_MAXW + 60, lh * len(lines) + 30), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    for li, ln in enumerate(lines):
        full = " ".join(ln)
        x = (img.width - d.textlength(full, font=f)) / 2
        y = 15 + li * lh
        for k, t in enumerate(ln):
            word = t + (" " if k < len(ln) - 1 else "")
            hot = any(e and e in t for e in emph)
            dd.text((x, y), t, font=f, fill=accent if hot else (250, 247, 240), stroke_width=7, stroke_fill=(0, 0, 0))
            x += d.textlength(word, font=f)
    return img


def big_image(text, accent):
    """화면 가운데 큰 핵심어 (편집 규칙 5 — 핵심어 하나만)."""
    lines = str(text).split("\n")
    size = 132
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f = font("sans", size, 800)
    while max(d.textlength(l, font=f) for l in lines) > W - SAFE_R - 140 and size > 72:
        size -= 6
        f = font("sans", size, 800)
    lh = int(size * 1.2)
    img = Image.new("RGBA", (W - SAFE_R, lh * len(lines) + 40), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        x = (img.width - d.textlength(l, font=f)) / 2
        dd.text((x, 20 + i * lh), l, font=f, fill=accent, stroke_width=10, stroke_fill=(0, 0, 0))
    return img


def src_layer(text):
    """아래쪽 작은 고정 글자 (연도·지명·출처 — 말로 읽지 않는다, 구성 규칙 2)."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not text:
        return lay
    d = ImageDraw.Draw(lay)
    f = font("sans", 30, 600)
    tw = d.textlength(text, font=f)
    cx = (W - SAFE_R) / 2 + 20
    d.rounded_rectangle((cx - tw / 2 - 18, SRC_Y - 24, cx + tw / 2 + 18, SRC_Y + 24), radius=22, fill=(6, 8, 16, 150))
    d.text((cx, SRC_Y), text, font=f, fill=(232, 226, 212, 235), anchor="mm")
    return lay


PROOF_W, PROOF_H, PROOF_CY = 900, 720, 830


def proof_frame(P, shot, p, accent, bgc):
    """실물 증거(원본 신문·사진·문서) 화면: 흐린 배경 위 카드, 전체 → hl 확대, 형광펜 (편집 규칙 4)."""
    key = id(P)
    if key not in bgc:
        r = max(W / P.width, H / P.height)
        bg = P.resize((int(P.width * r) + 2, int(P.height * r) + 2), Image.BILINEAR).crop((0, 0, W, H))
        bg = bg.filter(ImageFilter.GaussianBlur(28))
        bgc[key] = Image.blend(bg, Image.new("RGB", (W, H), (4, 6, 12)), 0.62).convert("RGBA")
    fr = bgc[key].copy()
    hl = shot.get("hl")
    box = (0, 0, P.width, P.height)
    if hl and (shot.get("_zoom") or shot.get("_glide")):
        x0, y0, x1, y1 = hl[0] * P.width, hl[1] * P.height, hl[2] * P.width, hl[3] * P.height
        bw, bh = (x1 - x0) * 1.35, (y1 - y0) * 1.8
        ar = P.width / P.height
        if bw / bh < ar:
            bw = bh * ar
        else:
            bh = bw / ar
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        bw, bh = min(bw, P.width), min(bh, P.height)
        cx = min(max(cx, bw / 2), P.width - bw / 2)
        cy = min(max(cy, bh / 2), P.height - bh / 2)
        box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
        if shot.get("_glide"):                         # 전체(처음 25%) → 형광펜 부분으로 부드럽게 다가감
            e = min(1, max(0, (p - 0.25) / 0.5))
            e = e * e * (3 - 2 * e)
            box = tuple(a + (b - a) * e for a, b in zip((0, 0, P.width, P.height), box))
    z = 1 + 0.04 * p                                   # 천천히 다가감
    bx0, by0, bx1, by1 = box
    cw, ch = (bx1 - bx0) / z, (by1 - by0) / z
    mx, my = (bx0 + bx1) / 2, (by0 + by1) / 2
    box = (mx - cw / 2, my - ch / 2, mx + cw / 2, my + ch / 2)
    r = min(PROOF_W / cw, PROOF_H / ch)
    dw, dh = int(cw * r), int(ch * r)
    card = P.resize((dw, dh), Image.LANCZOS, box=box).convert("RGBA")
    if hl:                                             # 형광펜: 장면 20%부터 왼쪽→오른쪽으로 칠해짐
        m = (min(1, max(0, (p - 0.55) / 0.3)) if shot.get("_glide")
             else min(1, max(0, (p - 0.2) / 0.35)) if shot.get("_zoom") or not shot.get("_split") else 0)
        if m > 0:
            hx0 = (hl[0] * P.width - box[0]) * r
            hy0 = (hl[1] * P.height - box[1]) * r
            hx1 = (hl[2] * P.width - box[0]) * r
            hy1 = (hl[3] * P.height - box[1]) * r
            ov = Image.new("RGBA", card.size, (0, 0, 0, 0))
            ImageDraw.Draw(ov).rectangle((hx0, hy0, hx0 + (hx1 - hx0) * m, hy1), fill=accent + (78,))
            card = Image.alpha_composite(card, ov)
    cx = int((W - SAFE_R) / 2 + 20)
    x, y = cx - dw // 2, PROOF_CY - dh // 2
    sh = Image.new("RGBA", (dw + 40, dh + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle((20, 26, dw + 20, dh + 26), fill=(0, 0, 0, 150))
    fr.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)), (x - 20, y - 20))
    ImageDraw.Draw(fr).rectangle((x - 6, y - 6, x + dw + 5, y + dh + 5), fill=(240, 234, 220, 255))
    fr.alpha_composite(card, (x, y))
    if shot.get("credit"):
        d = ImageDraw.Draw(fr)
        f = font("sans", 28, 600)
        d.text((cx, y + dh + 34), shot["credit"], font=f, fill=(225, 220, 205, 230), anchor="mm",
               stroke_width=3, stroke_fill=(0, 0, 0))
    return fr


def plan_shots(sc, s, e):
    """장면(s~e초)을 컷으로 나눈다. 반환: [(시작, 끝, 컷 dict)] (편집 규칙 1 — 1.5초 넘게 멈추지 않기)."""
    d = e - s
    if sc.get("shots"):
        shots = [dict(sh) for sh in sc["shots"]]
    elif sc.get("proof"):
        pf = sc["proof"]
        base = {"proof": pf["img"], "hl": pf.get("hl"), "credit": pf.get("credit", ""), "_split": bool(pf.get("hl"))}
        shots = [dict(base, _glide=bool(pf.get("hl")))]
    else:
        n = max(1, math.ceil(d / SHOT_MAX)) if sc.get("split") else 1   # 2026-11-04 사용자: 같은 그림 구도만 끊는 자동 컷은 정신없다 → 기본 끔
        z0 = sc.get("zoom", 1.0)
        f0 = sc.get("focus", [0.5, 0.5])
        pts = sc.get("points") or [f0, [f0[0] + 0.08, f0[1] - 0.05], [f0[0] - 0.08, f0[1] + 0.05], [f0[0] + 0.04, f0[1] + 0.07]]
        zs = (1.0, 1.38, 1.18, 1.5)
        mvs = [sc["move"], "in", "out", "left"]
        shots = [{"img": sc["img"], "zoom": z0 * zs[k % 4], "focus": [min(.9, max(.1, pts[k % len(pts)][0])), min(.9, max(.1, pts[k % len(pts)][1]))],
                  "move": mvs[k % 4]} for k in range(n)]
    ws = [sh.get("w", 1) for sh in shots]
    out, t0 = [], s
    for sh, w in zip(shots, ws):
        t1 = t0 + d * w / sum(ws)
        if not sh.get("proof"):
            sh.setdefault("img", sc["img"])
            sh.setdefault("zoom", sc.get("zoom", 1.0))
            sh.setdefault("focus", sc.get("focus", [0.5, 0.5]))
            sh.setdefault("move", sc["move"])
        out.append((t0, t1, sh))
        t0 = t1
    return out


def view(src, sc, p, punch=0.0):
    """장면 진행 p(0~1)에 따른 잘라낼 상자 (src 좌표)."""
    sw, sh = src.size
    z0 = sc.get("zoom", 1.0)
    fx, fy = sc.get("focus", [0.5, 0.5])
    mv = sc["move"]
    e = p * p * (3 - 2 * p) * 0.35 + p * 0.65          # 살짝 부드러운 시작
    z = z0 * (1 + 0.10 * e) if mv == "in" else z0 * (1.10 - 0.10 * e) if mv == "out" else z0 * 1.07
    cw, ch = sw / z, sh / z
    cx, cy = fx * sw, fy * sh
    span = 0.07
    if mv == "up":
        cy += (0.5 - e) * span * 2 * sh
    elif mv == "down":
        cy -= (0.5 - e) * span * 2 * sh
    elif mv == "left":
        cx += (0.5 - e) * span * 2 * sw
    elif mv == "right":
        cx -= (0.5 - e) * span * 2 * sw
    if punch:                                          # 컷 첫 몇 프레임: 살짝 크게 들어왔다 자리 잡음
        cw, ch = cw / (1 + punch), ch / (1 + punch)
    cx = min(max(cx, cw / 2), sw - cw / 2)
    cy = min(max(cy, ch / 2), sh - ch / 2)
    return (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)


# ───────── 본체 ─────────
def build(ep, spec, a):
    series = spec["series"]
    accent_hex = SERIES.get(series, ("#F2B544",))[0]
    accent = hexrgb(accent_hex)
    horror = spec.get("mood") == "horror"
    loop = spec.get("format") == "loop"
    if "TTS_RATE" not in os.environ:   # 공포 0.95, 그 밖 1.0 (원고 tts_rate로 바꿀 수 있음)
        os.environ["TTS_RATE"] = str(spec.get("tts_rate") or ("0.95" if horror else "1.0"))
    scenes = spec["scenes"]
    moves = ["in", "up", "out", "down", "in", "left", "out", "right"]
    for i, sc in enumerate(scenes):
        sc.setdefault("move", moves[i % len(moves)])

    # 1) 음성 — 이야기 한 토막(문단)을 한 번에 읽힌다. "cont": true인 장면은 앞 장면과 같은 문단.
    #    문장마다 따로 만들면 억양이 매번 처음부터 시작돼 '안내 방송을 이어 붙인' 소리가 난다 (2026-10-27 피드백).
    paras = []
    for i, sc in enumerate(scenes):
        fx = sc.get("sfx", [])
        fx = [fx] if isinstance(fx, str) else list(fx)
        sc["_fx"] = fx
        if i and sc.get("cont") and not ({"hit", "knock"} & set(fx)):
            paras[-1].append(i)
        else:
            paras.append([i])
    ad = ep / "short_audio"
    ad.mkdir(exist_ok=True)
    ptts, pwav, pdur, pbound = [], [], [], []
    for pi, idx in enumerate(paras, 1):
        # 구글 목소리는 쉼표를 자주 무시하고 이어 읽는다 → 쉼표·말줄임표와 장면 경계를 [pause short]로 바꾼다
        parts = [breathe(scenes[i].get("tts", scenes[i]["say"])) for i in idx]
        text = " ".join(p if p.endswith("]") or k == len(parts) - 1 else p + " [pause short]" for k, p in enumerate(parts))
        wav = ad / f"p{pi:02d}.wav"
        speak(text, wav, a.voice, max_pause=0.32, wrong_min=0.13)
        f, _, cum, _, _ = anchored(wav, text)
        # 문단 안 장면 경계 시각: 앞 장면들의 읽기 글자 수 → 시각 (쉼이 있으면 쉼이 끝난 때)
        bounds_t, nchar = [0.0], 0
        for prt in parts[:-1]:
            nchar += len(norm(prt))
            u = cum[min(nchar, len(cum) - 1)]
            bounds_t.append(f(u + 1e-5))
        ptts.append(text); pwav.append(wav); pdur.append(dur(wav)); pbound.append(bounds_t)

    # 호흡 검수 (반드시 통과 — 사용자 요구 2026-10-27 "내레이션 규칙은 꼭 지켜지도록")
    #  - 쉼표·문장 끝·장면 경계에서 쉬지 않음(빠진 쉼) / 의도하지 않은 곳에서 0.2초 넘게 쉼 → 실패
    if len(scenes) > 8 and not any(sc.get("cont") for sc in scenes):
        print("경고: 문단(cont)이 하나도 없어요 — 문장마다 끊겨 들립니다. 이야기 토막으로 묶으세요.")
    fails = []
    for pi, (text, wav) in enumerate(zip(ptts, pwav), 1):
        line, wrong, missing = breath(wav, text, wrong_min=0.2)
        if wrong or missing:
            fails.append(f"문단{pi:02d}: 엉뚱한 쉼 {wrong} / 빠진 쉼 {missing}\n    {line}")
    if fails:
        print("호흡 검수 실패 — tts를 고쳐 다시 만드세요 (어순 바꾸기, 쉼표 위치 옮기기, 붙여 쓰기):")
        print("\n".join(fails))
        if not a.force_breath:
            raise SystemExit(3)

    # 2) 시간표
    t = LEAD
    starts, nar, hits, sil, knocks, beats, pstart = [0.0] * len(scenes), [], [], [], [], [], []
    for pi, idx in enumerate(paras):
        first = scenes[idx[0]]
        fx = first["_fx"]
        if "knock" in fx:                     # 노크 세 번을 먼저 듣고 말이 시작된다
            knocks.append(t + 0.05)
            t += 1.35
        if "hit" in fx and pi > 0:
            sil.append((t - PGAP + 0.05, t - PGAP + HIT_GAP))
            t += HIT_GAP - PGAP
            hits.append(t)
        n0 = t + (0.18 if "hit" in fx else 0)
        pstart.append(n0)
        for k, i in enumerate(idx):
            starts[i] = t if k == 0 else n0 + pbound[pi][k] - 0.05
        end = n0 + pdur[pi]
        for k, i in enumerate(idx):
            if "heartbeat" in scenes[i]["_fx"]:
                b_end = (n0 + pbound[pi][k + 1]) if k + 1 < len(idx) else end
                beats.append((starts[i], b_end + 0.4))
        t = end + scenes[idx[-1]].get("hold", 0)
        t += END_TAIL if pi == len(paras) - 1 else PGAP
    for sc in scenes:
        sc["sfx"] = "hit" if "hit" in sc["_fx"] else ""
    total = t
    if total > 89:
        raise SystemExit(f"{total:.1f}초 — 90초를 넘어요. 문장을 줄이세요")
    if not loop and total > 70.5:
        raise SystemExit(f"{total:.1f}초 — 서사형은 70초를 넘기지 않는다 (2026-11-02 사용자 결정). 곁가지 문장을 빼고 다시")
    if not loop and total < 48:
        print(f"주의: {total:.1f}초 — 서사형 목표 50~70초")
    # 컷: 그림이 바뀔 때만 (같은 그림 구도 컷은 2026-11-04 사용자 판단으로 끔 — split:true일 때만)
    ends = starts[1:] + [total]
    shots = []                                  # (시작, 끝, 컷, 장면 번호)
    for i, (s0, e0) in enumerate(zip(starts, ends)):
        shots += [(a0, a1, sh, i) for a0, a1, sh in plan_shots(scenes[i], s0, e0)]
    long_sh = [(k + 1, round(a1 - a0, 1)) for k, (a0, a1, sh, i) in enumerate(shots) if a1 - a0 > 4.5]
    if long_sh:
        print("그림 길이 경고(한 그림 4.5초 초과 — 다음 그림을 일찍 넣거나 문장을 나누세요): " + ", ".join(f"컷{k} {d}초" for k, d in long_sh))
    imgs_used = len({sh.get("img") or sh.get("proof") for _, _, sh, _ in shots})
    print(f"그림 전환 {len(shots)}번 · 평균 {total / len(shots):.2f}초 · 서로 다른 그림 {imgs_used}장")
    (ep / "short_scene_times.json").write_text(json.dumps(
        [round(e - s, 2) for s, e in zip(starts, ends)]))
    events = []
    def src_of(sh):
        return sh.get("proof") or sh.get("img")
    for k, (a0, a1, sh, i) in enumerate(shots):
        sh["_new"] = k == 0 or src_of(sh) != src_of(shots[k - 1][2])
        if k and a0 > 0.2 and sh["_new"]:        # 그림이 바뀔 때만 (같은 그림 구도 바뀜엔 소리 없음)
            events.append((a0 - 0.08, "paper" if sh.get("proof") else "whoosh"))
    for i, sc in enumerate(scenes):
        for name in sc["_fx"]:
            if name in FX:
                events.append((starts[i] + (0.02 if i == 0 else 0.0), name))
        if sc.get("big"):
            bg = sc["big"] if isinstance(sc["big"], dict) else {"text": sc["big"]}
            sc["_big"] = (bg["text"], starts[i] + (ends[i] - starts[i]) * bg.get("at", 0.15))
            events.append((sc["_big"][1], "pop"))

    work = ep / "short_work"
    work.mkdir(exist_ok=True)
    audio = mix(total, [(pstart[pi], read_wav(pwav[pi])) for pi in range(len(paras))], hits, sil, horror,
                knocks, beats, events)
    write_wav(work / "mix.wav", audio)

    # 3) 자막 시간표 — 문단 음성에서 어절 시각을 구하고, 장면 경계를 넘지 않게 덩어리를 나눈다
    caps = []          # (시작, 끝, 글, emph)
    for pi, idx in enumerate(paras):
        disp = [scenes[i].get("sub", scenes[i]["say"]) for i in idx]
        toks, tms = tts_word_times(pwav[pi], " ".join(disp), ptts[pi])
        pos = 0
        for i, dtext in zip(idx, disp):
            n = len(dtext.split())
            st, sm = toks[pos:pos + n], tms[pos:pos + n]
            pos += n
            sc = scenes[i]
            for ct, c0 in chunks(st, sm):
                caps.append([max(0.0, pstart[pi] + c0 - 0.06), None, clean(ct),
                             sc.get("emph", []) + ([spec["accent_word"]] if spec.get("accent_word") else [])])
        for j in range(len(caps) - 1):
            if caps[j][1] is None:
                caps[j][1] = caps[j + 1][0]
        caps[-1][1] = pstart[pi] + pdur[pi] + 0.15
    caps[0][0] = 0.0                     # 첫 프레임부터 첫 자막

    # 4) 프레임
    out_dir = REPO_OSSAK / ep.name
    out_dir.mkdir(parents=True, exist_ok=True)
    video = out_dir / f"{ep.name}.mp4"          # 파일 이름으로 편 구분 (2026-10-28 사용자 요청)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", str(work / "mix.wav"), "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "21", "-maxrate", "3500k", "-bufsize", "7M", "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
                            "-movflags", "+faststart", "-shortest", str(video)], stdin=subprocess.PIPE)
    vig = vignette()
    black = Image.new("RGB", (W, H), (2, 3, 8))
    tl = title_layer(spec["hook"], spec.get("accent_word"), accent)
    lg = logo()
    srcs, proofs, bgc = {}, {}, {}
    for _, _, sh, _ in shots:
        if sh.get("proof"):
            if sh["proof"] not in proofs:
                pp = ep / sh["proof"]
                if not pp.exists():
                    raise SystemExit(f"증거 이미지 없음: {pp}")
                proofs[sh["proof"]] = Image.open(pp).convert("RGB")
            continue
        if sh["img"] not in srcs:
            p = ep / "vpanels" / f"{sh['img']}.jpg"
            if not p.exists():
                raise SystemExit(f"세로 그림 없음: {p.name} — --images 먼저")
            im = Image.open(p).convert("RGB")
            small = im.width < 800
            im = im.resize((1350, 2400), Image.LANCZOS)
            if small:                       # 576×1024에서 키운 그림은 윤곽을 살짝 살린다
                im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=2))
            if horror:                      # 색을 빼고 차갑게, 더 어둡게
                gray = im.convert("L").convert("RGB")
                im = Image.blend(im, gray, 0.35)
                im = Image.blend(im, Image.new("RGB", im.size, (6, 14, 24)), 0.18)
            srcs[sh["img"]] = im
    grains = []
    if horror:                                # 필름 입자 (6장 돌려 씀)
        rng = np.random.default_rng(9)
        for _ in range(6):
            g = rng.integers(0, 255, (H // 3, W // 3), dtype=np.uint8)
            gi = Image.fromarray(g, "L").resize((W, H), Image.BILINEAR)
            a = Image.new("L", (W, H), 10)
            grains.append(Image.merge("RGBA", (gi, gi, gi, a)))
        flick = np.random.default_rng(13).normal(0, 1, int(total * FPS) + 10)
        flick = np.convolve(flick, np.ones(5) / 5, mode="same")
    nframes = int(round(total * FPS))
    bounds = [int(round(s * FPS)) for s in starts[1:]] + [nframes]
    bounds_start = [0] + bounds[:-1]
    sbounds = [int(round(a1 * FPS)) for _, a1, _, _ in shots]
    sbounds[-1] = nframes
    sstart = [0] + sbounds[:-1]
    sl = src_layer(spec.get("src_line", ""))
    big_cache = {}
    cap_cache, stills, ci = {}, [], 0
    for fi in range(nframes):
        tsec = fi / FPS
        si = next(k for k in range(len(scenes)) if fi < bounds[k])
        sc = scenes[si]
        b0, b1 = bounds_start[si], bounds[si]
        kk = next(k for k in range(len(shots)) if fi < sbounds[k])
        sh = shots[kk][2]
        c0f, c1f = sstart[kk], sbounds[kk]
        p = (fi - c0f) / max(1, c1f - c0f)
        if sh.get("proof"):                   # 실물 증거 화면 (자르지 않고 카드로)
            fr = proof_frame(proofs[sh["proof"]], sh, p, accent, bgc).convert("RGB")
        else:                                 # 하드 컷 + 첫 4프레임 살짝 펀치
            k4 = fi - c0f
            punch = 0.04 * (1 - k4 / 4) if kk > 0 and sh.get("_new") and k4 < 4 else 0.0
            fr = srcs[sh["img"]].resize((W, H), Image.BILINEAR, box=view(srcs[sh["img"]], sh, p, punch))
        # 반전 직전 무음 구간: 화면도 살짝 어두워진다
        dim = 0
        for s0, e0 in sil:
            if s0 <= tsec < e0 + 0.05:
                dim = min(1, (tsec - s0) / 0.25) * 0.3
        fr = Image.composite(black, fr, vig)
        if dim:
            fr = Image.blend(fr, black, dim)
        if horror:                            # 촛불처럼 아주 약하게 깜빡임
            fl = float(np.clip(0.06 + 0.05 * flick[fi], 0, 0.16))
            fr = Image.blend(fr, black, fl)
        fr = fr.convert("RGBA")
        if grains:
            fr.alpha_composite(grains[(fi // 3) % len(grains)])   # 3프레임마다 바뀌는 입자 (용량 절약)
        if sc.get("_big") and tsec >= sc["_big"][1]:
            bt = sc["_big"][0]
            if bt not in big_cache:
                big_cache[bt] = big_image(bt, accent)
            bi = big_cache[bt]
            k5 = (tsec - sc["_big"][1]) * FPS
            sz = 1.28 - 0.28 * min(1, k5 / 5)
            if sz > 1.001:
                bi = bi.resize((int(bi.width * sz), int(bi.height * sz)), Image.BILINEAR)
            fr.alpha_composite(bi, (int((W - SAFE_R) / 2 + 20 - bi.width / 2), int(820 - bi.height / 2)))
        fr.alpha_composite(sl)
        fr.alpha_composite(tl)
        fr.alpha_composite(lg, (W - SAFE_R // 2 - lg.width - 10, 240))   # 인스타 상단 가림 영역(위 230px) 아래로 (2026-11-02)
        if fi == 0:
            fr.convert("RGB").save(out_dir / f"{ep.name}_thumb.jpg", quality=92)   # 썸네일: 자막 없이
        while ci + 1 < len(caps) and tsec >= caps[ci + 1][0]:
            ci += 1
        c0, c1, ct, emph = caps[ci]
        if c0 <= tsec < c1 + 0.05 and ct:
            key = (ct, tuple(emph))
            if key not in cap_cache:
                cap_cache[key] = sub_image(ct, emph, accent)
            ci_img = cap_cache[key]
            k = (tsec - c0) * FPS
            sc_ = 0.88 + 0.12 * min(1, k / 3) if c0 > 0 else 1.0
            if sc_ < 1:
                ci_img = ci_img.resize((int(ci_img.width * sc_), int(ci_img.height * sc_)), Image.BILINEAR)
            cx = (W - SAFE_R) / 2 + 20
            fr.alpha_composite(ci_img, (int(cx - ci_img.width / 2), int(SUB_Y - ci_img.height / 2 + 40)))
        fr = fr.convert("RGB")
        if fi == min(b1 - 1, b0 + int(FPS * 0.9)):
            stills.append(fr.copy())
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise SystemExit("ffmpeg 인코딩 실패")
    tw, th, cols = 270, 480, 6
    rows_n = (len(stills) + cols - 1) // cols
    sh = Image.new("RGB", (tw * cols, th * rows_n), C["bg"])
    for i, s in enumerate(stills):
        sh.paste(s.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sh.save(ep / "short_preview.jpg", quality=82)
    chars = sum(len(sc["say"]) for sc in scenes)
    print(f"{ep.name}: {total:.1f}초, 장면 {len(scenes)}개, 대본 {chars}자 → {video}")
    return total


def rows(ep, spec, a, total=None):
    yt = spec.get("youtube", {})
    hook = " ".join(spec["hook"])
    loop = spec.get("format") == "loop"
    no = spec.get("no")
    title = yt.get("title", hook)
    if no:
        title = f"{title} 【오싹기록 #{no}】"
    tags = spec.get("tags", f"#{spec['series']}")
    desc = "\n\n".join(x for x in [
        yt.get("summary", ""),
        "실제 기록을 바탕으로 각색한 이야기입니다. 그림과 내레이션은 AI로 재구성했습니다." if spec.get("adapted")
        else "실제 기록을 바탕으로 한 이야기입니다. 그림과 내레이션은 AI로 재구성했습니다." if not spec.get("legend")
        else "전해지는 이야기를 기록에 따라 옮겼습니다. 그림과 내레이션은 AI로 재구성했습니다.",
        spec.get("sources", ""), "매일 저녁 6시·밤 10시 · 인스타그램 @ossak_alarm", tags + " #shorts"] if x)
    video = f"{BASE}{ep.name}/{ep.name}.mp4"
    cover = f"{BASE}{ep.name}/{ep.name}_thumb.jpg"
    out = {}
    if a.date:
        ytime = a.yt_time or ("22:00" if loop else "18:00")
        out["youtube"] = ["'" + a.date, "'" + ytime, spec["id"], "루프형" if loop else "서사형", title, desc,
                          tags.replace("#", "").replace(" ", ","), yt.get("pinned", ""), video, cover, "대기", "",
                          f"{total:.0f}초" if total else "", "", "", "", "", spec.get("hook_type", "")]
        if not loop and not a.no_ig:
            # 캡션 첫 줄(…더 보기 전 약 125자) = 댓글 질문 하나. 영상이 이미 훅을 하니 제목을 반복하지 않는다 (2026-11-02)
            ask = yt.get("pinned", "")
            ig = spec.get("instagram", {}).get("caption") or "\n\n".join(x for x in [
                (ask + " 댓글로 남겨 주세요.") if ask else "", yt.get("summary", ""),
                spec.get("sources", ""), tags] if x)
            out["instagram"] = ["'" + (a.ig_date or a.date), "'" + a.ig_time, "인스타 릴스", spec["id"], spec["series"],
                                spec.get("title", hook), hook, spec.get("risk", "저"), "예약", ig, "", f"{video}\n{cover}"]
    (ep / "short_rows.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--images", action="store_true", help="빠진 세로 그림 그리기")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--date", help="유튜브 업로드일 (행 생성)")
    ap.add_argument("--yt-time")
    ap.add_argument("--ig-date", help="인스타 릴스 날짜 (기본 = --date)")
    ap.add_argument("--ig-time", default="21:30")
    ap.add_argument("--no-ig", action="store_true")
    ap.add_argument("--voice", default="auto", choices=["auto", "google", "melo"])
    ap.add_argument("--rows-only", action="store_true")
    ap.add_argument("--force-breath", action="store_true", help="호흡 검수 실패를 무시 (사용자가 직접 확인했을 때만)")
    a = ap.parse_args()
    ep = pathlib.Path(a.episode).resolve()
    spec = json.loads((ep / "short.json").read_text())
    if a.images:
        return images(ep, spec, a.only, a.force)
    if a.rows_only:
        return rows(ep, spec, a)
    total = build(ep, spec, a)
    rows(ep, spec, a, total)


if __name__ == "__main__":
    main()
