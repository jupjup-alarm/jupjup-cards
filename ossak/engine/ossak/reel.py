#!/usr/bin/env python3
"""오싹알람 릴스 렌더러 — 캐러셀 컷 + 내레이션으로 9:16 영상(1080×1920)을 만든다.

  python3 ossak/reel.py episodes/<편> [--date 2026-10-27] [--time 12:30] [--voice auto|google|melo]

원고: story.json(또는 episode.json)의 "reel"
  {"beats": [{"say": "내레이션 한 문장", "panel": "s02a", "sub": "자막이 달라야 할 때만(선택)"}, ...],
   "teaser": "캡션 둘째 줄(선택)"}
  - 첫 beat = 훅(표지 훅 그대로 또는 더 짧게). 첫 프레임부터 제목과 자막이 보인다(1초 룰).
  - 마지막 beat = 남은 질문 + "답은, 프로필을 눌러 확인하세요." 부기 컷(end panel)을 쓴다.
  - 전체 220~260자(약 45~55초). beat 하나 = 장면 하나 = 사실 하나.
  - 답(원인)은 말하지 않는다. 캐러셀이 먼저 올라간 다음 날 릴스를 올리므로 프로필에 답이 있다.

결과 (저장소 ossak/<편>/):
  reel.mp4 (H.264 + AAC 48kHz), reel_cover.jpg (첫 장면)
  episodes/<편>/reel_preview.jpg (장면별 정지 화면), reel_row.json (발행계획 A:L 한 행)

목소리
  - 환경변수 GOOGLE_TTS_KEY가 있으면 구글 TTS(기본 ko-KR-Chirp3-HD-Charon, TTS_VOICE·TTS_RATE로 변경)
  - 없으면 Cloudflare Workers AI MeloTTS 한국어(무료, CF_ACCOUNT_ID·CF_API_TOKEN)
  음성은 episodes/<편>/reel_audio/에 문장별로 저장해 두고, 문장이 바뀐 것만 다시 만든다.
"""
import argparse, base64, datetime, hashlib, json, os, pathlib, re, subprocess, sys, urllib.request
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from compose import font, wrap, pill, cover_fit, split_accent, C  # noqa: E402
from cf import load_env  # noqa: E402

ENGINE = pathlib.Path(__file__).resolve().parent.parent
REPO_OSSAK = ENGINE.parent
BASE = "https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/ossak/"
W, H, FPS = 1080, 1920, 30
BAND = (60, 604, 1020, 1280)          # 그림 띠 (960×676, 컷 비율 그대로)
SUB_Y, SUB_W = 1306, 860              # 자막 시작 y, 최대 폭 (오른쪽 버튼 자리 140px 비움)
GAP, END_HOLD, LEAD = 0.30, 1.6, 0.12


# ───────── 음성 ─────────
def tts_google(text, key):
    voice = os.environ.get("TTS_VOICE", "ko-KR-Chirp3-HD-Charon")
    body = {"input": {"text": text}, "voice": {"languageCode": "ko-KR", "name": voice},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 48000,
                            "speakingRate": float(os.environ.get("TTS_RATE", "1.1"))}}
    req = urllib.request.Request(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return base64.b64decode(json.load(urllib.request.urlopen(req, timeout=60))["audioContent"]), 1.0


def tts_melo(text):
    acc, tok = load_env()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/myshell-ai/melotts",
        data=json.dumps({"prompt": text, "lang": "kr"}).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=120))
    return base64.b64decode(d["result"]["audio"]), 1.28   # MeloTTS는 느려서 1.28배


def speak(text, out, mode):
    """text → out(.wav, 48kHz mono, 앞뒤 무음 제거). 캐시 키는 문장+목소리."""
    key = os.environ.get("GOOGLE_TTS_KEY", "")
    use_google = mode == "google" or (mode == "auto" and key)
    tag = hashlib.sha1((("g:" + os.environ.get("TTS_VOICE", "")) if use_google else "m:" + text).encode()
                       + text.encode()).hexdigest()[:12]
    meta = out.with_suffix(".txt")
    if out.exists() and meta.exists() and meta.read_text() == tag:
        return
    raw, tempo = tts_google(text, key) if use_google else tts_melo(text)
    tmp = out.with_suffix(".raw")
    tmp.write_bytes(raw)
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,areverse,"
          f"atempo={tempo},loudnorm=I=-16:TP=-1.5:LRA=7")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", af, "-ar", "48000", "-ac", "1", str(out)],
                   check=True)
    tmp.unlink()
    meta.write_text(tag)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True).stdout)


# ───────── 그림 ─────────
def panel_img(ep, pid):
    cands = [c for c in (ep / "panels" / f"{pid}{x}" for x in (".png", ".jpg")) if c.exists()]
    if not cands:
        raise SystemExit(f"컷 없음: {pid}")
    return Image.open(max(cands, key=lambda c: c.stat().st_mtime)).convert("RGB")


def round_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return m


def static_layer(img, title, accent_word, badge, accent):
    """장면마다 고정인 바탕: 흐린 배경 + 말머리 + 제목."""
    bg = cover_fit(img, W, H).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), C["bg"]), 0.78)
    d = ImageDraw.Draw(bg)
    _, ph = pill(d, 70, 300, badge, accent, C["navy"], 30)
    f = font("serif", 54)
    y = 300 + ph + 20
    for line in title[:3]:
        x = 70
        for seg, col in split_accent(line, accent_word):
            d.text((x, y), seg, font=f, fill=accent if col else C["ink"])
            x += d.textlength(seg, font=f)
        y += 68
    return bg, y


def sub_chunks(d, text, f):
    lines = wrap(d, text, f, SUB_W)
    return [lines[i:i + 2] for i in range(0, len(lines), 2)]


def draw_sub(fr, lines, f, color):
    d = ImageDraw.Draw(fr)
    lh = int(f.size * 1.38)
    widths = [d.textlength(l, font=f) for l in lines]
    bw, bh = max(widths) + 56, lh * len(lines) + 30
    x0 = int((W - 140) / 2 - bw / 2 + 35)   # 오른쪽 140px(버튼 자리)을 피해 가운데 정렬
    d.rounded_rectangle((x0, SUB_Y, x0 + bw, SUB_Y + bh), radius=18, fill=(8, 11, 22))
    for i, l in enumerate(lines):
        d.text((x0 + bw / 2, SUB_Y + 15 + i * lh + lh / 2), l, font=f, fill=color, anchor="mm")
    return SUB_Y + bh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--date", help="릴스 발행일 (발행계획 행 생성)")
    ap.add_argument("--time", default="12:30")
    ap.add_argument("--voice", default="auto", choices=["auto", "google", "melo"])
    a = ap.parse_args()
    ep = pathlib.Path(a.episode).resolve()
    spec = json.loads((ep / "episode.json").read_text())
    src = json.loads((ep / "story.json").read_text()) if (ep / "story.json").exists() else spec
    reel = src.get("reel") or spec.get("reel")
    if not reel:
        raise SystemExit("원고에 reel이 없어요")
    cover = spec["slides"][0]["cells"][0]["cover"]
    accent = spec.get("accent", C["amber"])
    beats = reel["beats"]
    total_chars = sum(len(b["say"]) for b in beats)

    # 1) 음성
    ad = ep / "reel_audio"
    ad.mkdir(exist_ok=True)
    for i, b in enumerate(beats, 1):
        speak(b["say"], ad / f"{i:02d}.wav", a.voice)
    durs = [dur(ad / f"{i:02d}.wav") for i in range(1, len(beats) + 1)]
    starts, t = [], LEAD
    for i, dv in enumerate(durs):
        starts.append(t)
        t += dv + (END_HOLD if i == len(beats) - 1 else GAP)
    total = t
    if total > 89:
        raise SystemExit(f"{total:.1f}초 — 90초를 넘어요. 문장을 줄이세요")

    # 2) 오디오 믹스: 내레이션 + 낮은 바람 소리(생성음)
    work = ep / "reel_work"
    work.mkdir(exist_ok=True)
    inputs, filt = [], []
    for i in range(len(beats)):
        inputs += ["-i", str(ad / f"{i + 1:02d}.wav")]
        ms = int(starts[i] * 1000)
        filt.append(f"[{i}:a]adelay={ms}|{ms}[n{i}]")
    n = len(beats)
    amb = (f"anoisesrc=color=brown:amplitude=0.5:duration={total:.2f}:sample_rate=48000,"
           f"lowpass=f=220,highpass=f=40,volume=0.07,afade=t=in:d=1.5,afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5[amb]")
    filt.append(amb)
    filt.append("".join(f"[n{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0[nar]")
    filt.append("[nar][amb]amix=inputs=2:normalize=0,alimiter=limit=0.95[out]")
    audio = work / "mix.m4a"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-t", f"{total:.2f}", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(audio)], check=True)

    # 3) 영상 프레임
    out_dir = REPO_OSSAK / ep.name
    out_dir.mkdir(parents=True, exist_ok=True)
    video = out_dir / "reel.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
                            "-shortest", str(video)], stdin=subprocess.PIPE)
    bw, bh = BAND[2] - BAND[0], BAND[3] - BAND[1]
    mask = round_mask(bw, bh, 22)
    fsub = font("sans", 52, 700)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    stills, prev = [], None
    nframes = int(round(total * FPS))
    beat_frames = [int(round(s * FPS)) for s in starts[1:]] + [nframes]
    fi = 0
    for bi, b in enumerate(beats):
        img = panel_img(ep, b["panel"])
        static, _ = static_layer(img, cover["title"], cover.get("accent_word"), cover.get("badge", spec["series"]), accent)
        big = cover_fit(img, int(bw * 1.12), int(bh * 1.12))
        chunks = sub_chunks(probe, b.get("sub", b["say"]), fsub)
        weights = [sum(len(l) for l in c) for c in chunks]
        b_start = 0 if bi == 0 else int(round(starts[bi] * FPS))
        b_end = beat_frames[bi]
        a_end = int(round((starts[bi] + durs[bi]) * FPS))
        direction = -1 if bi % 2 else 1
        last = b.get("last", bi == len(beats) - 1)
        while fi < b_end:
            p = (fi - b_start) / max(1, b_end - b_start)
            z = 1 + 0.09 * p
            cw, ch = big.width / (1.12 * z) * 1.0, big.height / (1.12 * z)
            cx = big.width / 2 + direction * (big.width - cw) / 2 * (p - 0.5) * 0.8
            cy = big.height / 2
            crop = big.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((bw, bh), Image.BILINEAR)
            fr = static.copy()
            fr.paste(crop, (BAND[0], BAND[1]), mask)
            d = ImageDraw.Draw(fr)
            # 진행 막대
            d.rectangle((BAND[0], BAND[3] + 10, BAND[0] + int(bw * fi / nframes), BAND[3] + 15), fill=accent)
            # 자막 (음성 길이에 비례해 덩어리 전환)
            span = max(1, a_end - b_start)
            k, acc, pos = 0, 0, (fi - b_start) / span * sum(weights)
            for k, wv in enumerate(weights):
                acc += wv
                if pos < acc:
                    break
            bottom = draw_sub(fr, chunks[min(k, len(chunks) - 1)], fsub, accent if last else C["ink"])
            if last:
                d.text((W / 2 - 35, bottom + 40), "@ossak_alarm", font=font("sans", 36, 700), fill=C["ink2"], anchor="mm")
            if prev is not None and fi - b_start < 6 and bi > 0:
                fr = Image.blend(prev, fr, (fi - b_start + 1) / 6)
            if fi == b_start + 8:
                stills.append(fr.copy())
            if fi == 0:
                cover_frame = fr.copy()
            enc.stdin.write(fr.tobytes())
            if fi == b_end - 1:
                prev = fr
            fi += 1
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise SystemExit("ffmpeg 인코딩 실패")

    # 4) 표지, 미리보기, 발행계획 행
    cover_frame.save(out_dir / "reel_cover.jpg", quality=92)
    tw, th, cols = 270, 480, 5
    rows_n = (len(stills) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * rows_n))
    for i, s in enumerate(stills):
        sheet.paste(s.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sheet.save(ep / "reel_preview.jpg", quality=82)
    hook = " ".join(cover["title"])
    caro = spec.get("caption", "")
    src_line = next((l for l in caro.splitlines() if l.startswith("출처")), "")
    tags = next((l for l in reversed(caro.splitlines()) if l.startswith("#")), f"#{spec['series']}")
    cap = "\n\n".join(x for x in [hook, reel.get("teaser", ""), "답은 @ossak_alarm 프로필을 눌러 확인하세요.",
                                  src_line, tags] if x)
    urls = f"{BASE}{ep.name}/reel.mp4\n{BASE}{ep.name}/reel_cover.jpg"
    if a.date:
        row = ["'" + a.date, "'" + a.time, "인스타 릴스", spec["id"], spec["series"], spec["title"], hook,
               spec.get("risk", "저"), "예약", cap, "", urls]
        (ep / "reel_row.json").write_text(json.dumps(row, ensure_ascii=False, indent=1))
    print(f"{ep.name}: {total:.1f}초, 장면 {len(beats)}개, 대본 {total_chars}자 → {video}")


if __name__ == "__main__":
    main()
