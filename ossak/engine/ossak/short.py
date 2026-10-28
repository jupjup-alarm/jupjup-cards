#!/usr/bin/env python3
"""오싹알람 쇼츠 엔진 — 세로 전체화면 그림 + 내레이션 + 단어 자막으로 1080×1920 영상을 만든다.
같은 파일을 유튜브 쇼츠와 인스타 릴스에 올린다.

  python3 ossak/short.py episodes/<편> --images          # 빠진 세로 그림만 그린다 (기본 864×1536 약 156뉴런, SHORT_IMG=576x1024로 줄일 수 있음)
  python3 ossak/short.py episodes/<편> --images --only v03 --force
  python3 ossak/short.py episodes/<편> --date 2026-10-28  # 영상 + 발행 행(short_rows.json)
  python3 ossak/short.py episodes/<편> --date 2026-10-28 --rows-only

원고: episodes/<편>/short.json
{
  "id": "W-0001", "no": 1, "series": "세계기담", "format": "story" | "loop", "mood": "mystery" | "horror",
  "title": "디아틀로프 고개",                      # 사건 이름(시트용)
  "hook": ["한겨울, 신발 두고", "텐트를 떠난 9명"],  # 화면 위 고정 제목 2줄 (줄당 10자 안팎)
  "accent_word": "9명",
  "images": [{"id": "v01", "prompt": "영문 장면 묘사", "with_character": false, "nop": true}],
  "scenes": [
    {"say": "자막·내레이션 문장", "tts": "읽기용 표기(선택)", "sub": "자막이 달라야 할 때(선택)",
     "img": "v01", "move": "in|out|up|down|left|right", "zoom": 1.0, "focus": [0.5, 0.5],
     "sfx": "hit",            # 이 장면 직전 0.6초 무음 + 낮은 효과음 (반전 직전에 한 번). 공포형은 그 앞에 긴장음이 차오른다
                              # "knock": 말 시작 전 노크 세 번 / "heartbeat": 장면 내내 낮은 심장 소리. 여러 개면 ["knock", "hit"]
     "hold": 0.0,             # 말이 끝난 뒤 그림을 더 보여줄 초
     "emph": ["9명"]}         # 자막에서 말머리 색으로 칠할 단어
  ],
  "youtube": {"title": "제목 15~25자", "summary": "설명란 두세 줄(답 없이)", "pinned": "고정 댓글 질문"},
  "instagram": {"caption": "첫 줄 훅 … (선택, 없으면 자동)"},
  "sources": "출처: …", "tags": "#세계기담 #디아틀로프", "risk": "저",
  "hook_type": "권위×초자연(임금이 귀신 안부)",   # 훅 유형 — 주간 분석이 유형별 성과를 비교한다
  "adapted": true                                   # 각색했으면 설명란 문구가 바뀐다
}

화면: 위 300px·아래 420px·오른쪽 140px에는 글자를 두지 않는다. 제목은 위(y≈310~), 자막은 가운데 아래(y≈1130),
부기 로고는 오른쪽 위. 첫 프레임부터 제목·그림·첫 자막이 보인다(로고 인트로·페이드인 없음).
소리: 내레이션(구글 Umbriel) + 낮은 바람 소리(공포형은 낮은 울림 추가) + sfx 장면 앞 무음과 효과음.
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
LEAD, GAP, HIT_GAP, PGAP = 0.05, 0.22, 0.6, 0.38
SERIES = {"세계기담": ("#F2B544", "amber"), "새벽괴담": ("#3FB8A8", "teal"), "미제파일": ("#E8693A", "orange"),
          "그날의 기록": ("#E8693A", "orange"), "그 후": ("#9AA3B8", "silver")}
CHARACTER = ("Boogi, a small round owl archivist mascot: dark slate-navy feathers, two pointed ear tufts, large glowing "
             "amber eyes behind thin round silver glasses, a small amber diamond-shaped beak, a lighter navy chevron-patterned "
             "belly, short wings, carrying a small cream notebook and a little amber lantern. Cute, simple, flat webtoon character design.")
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
    prompt += " " + STYLE.format(accent=SERIES.get(spec["series"], ("", "amber"))[1])
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


def mix(total, placements, hits, silences, horror, knocks=(), beats=()):
    n = int(total * SR) + 1
    out = np.zeros(n, np.float32)
    for start, wav in placements:
        a = int(start * SR)
        out[a:a + len(wav)] += wav[:max(0, n - a)]
    rng = np.random.default_rng(11)
    amb = brown(n, rng) * (0.02 if horror else 0.012)
    if horror:
        t = np.arange(n) / SR
        amb += (0.010 * np.sin(2 * np.pi * 55 * t) + 0.006 * np.sin(2 * np.pi * 82.4 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t))
    env = np.ones(n, np.float32)
    fade = int(SR * 1.2)
    env[:fade] = np.linspace(0.3, 1, fade)
    env[-fade:] *= np.linspace(1, 0.4, fade)
    for s, e in silences:                    # 반전 직전 무음: 바람 소리도 빠진다
        a, b = int(s * SR), int(e * SR)
        r = int(0.12 * SR)
        env[a:a + r] *= np.linspace(1, 0, r)[:len(env[a:a + r])]
        env[a + r:b] = 0
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
        a = int(t0 * SR)
        seg = hs[:max(0, n - a)]
        out[a:a + len(seg)] += seg
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


def view(src, sc, p):
    """장면 진행 p(0~1)에 따른 잘라낼 상자 (src 좌표)."""
    sw, sh = src.size
    z0 = sc.get("zoom", 1.0)
    fx, fy = sc.get("focus", [0.5, 0.5])
    mv = sc["move"]
    e = p * p * (3 - 2 * p) * 0.35 + p * 0.65          # 살짝 부드러운 시작
    z = z0 * (1 + 0.08 * e) if mv == "in" else z0 * (1.08 - 0.08 * e) if mv == "out" else z0 * 1.06
    cw, ch = sw / z, sh / z
    cx, cy = fx * sw, fy * sh
    span = 0.05
    if mv == "up":
        cy += (0.5 - e) * span * 2 * sh
    elif mv == "down":
        cy -= (0.5 - e) * span * 2 * sh
    elif mv == "left":
        cx += (0.5 - e) * span * 2 * sw
    elif mv == "right":
        cx -= (0.5 - e) * span * 2 * sw
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
    if horror and "TTS_RATE" not in os.environ:
        os.environ["TTS_RATE"] = "0.95"
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
        t += (1.0 if loop else 1.3) if pi == len(paras) - 1 else PGAP
    for sc in scenes:
        sc["sfx"] = "hit" if "hit" in sc["_fx"] else ""
    total = t
    if total > 89:
        raise SystemExit(f"{total:.1f}초 — 90초를 넘어요. 문장을 줄이세요")
    if not loop and total > 66:
        print(f"주의: {total:.1f}초 — 서사형 목표 45~65초")

    work = ep / "short_work"
    work.mkdir(exist_ok=True)
    audio = mix(total, [(pstart[pi], read_wav(pwav[pi])) for pi in range(len(paras))], hits, sil, horror,
                knocks, beats)
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
    srcs = {}
    for sc in scenes:
        if sc["img"] not in srcs:
            p = ep / "vpanels" / f"{sc['img']}.jpg"
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
            srcs[sc["img"]] = im
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
    cap_cache, stills, prev, ci = {}, [], None, 0
    for fi in range(nframes):
        tsec = fi / FPS
        si = next(k for k in range(len(scenes)) if fi < bounds[k])
        sc = scenes[si]
        b0, b1 = bounds_start[si], bounds[si]
        p = (fi - b0) / max(1, b1 - b0)
        fr = srcs[sc["img"]].resize((W, H), Image.BILINEAR, box=view(srcs[sc["img"]], sc, p))
        if si > 0 and fi - b0 < 5 and sc.get("sfx") != "hit" and prev is not None:
            fr = Image.blend(prev, fr, (fi - b0 + 1) / 6)
        if fi == b1 - 1:
            prev = fr
        # 반전 직전 무음 구간: 화면도 살짝 어두워진다
        dim = 0
        for s0, e0 in sil:
            if s0 <= tsec < e0 + 0.05:
                dim = min(1, (tsec - s0) / 0.25) * 0.55
        fr = Image.composite(black, fr, vig)
        if dim:
            fr = Image.blend(fr, black, dim)
        if horror:                            # 촛불처럼 아주 약하게 깜빡임
            fl = float(np.clip(0.06 + 0.05 * flick[fi], 0, 0.16))
            fr = Image.blend(fr, black, fl)
        fr = fr.convert("RGBA")
        if grains:
            fr.alpha_composite(grains[(fi // 3) % len(grains)])   # 3프레임마다 바뀌는 입자 (용량 절약)
        fr.alpha_composite(tl)
        fr.alpha_composite(lg, (W - SAFE_R // 2 - lg.width - 10, 206))
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
            ig = spec.get("instagram", {}).get("caption") or "\n\n".join(x for x in [
                hook, yt.get("pinned", ""), spec.get("sources", ""), tags] if x)
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
