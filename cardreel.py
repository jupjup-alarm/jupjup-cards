#!/usr/bin/env python3
"""카드뉴스 → 카드 영상(릴스) — 2026-11-03 사용자 결정.

인스타 카드뉴스(캐러셀)는 새 계정이라 도달이 1~5명뿐이라, 같은 카드를 세로 영상으로 넘겨 보여주는
릴스로 올린다 (팔로워가 아닌 사람에게도 추천됨 — @donnamu_grow 청약통장 카드 영상 175만 회 형식).

사용법:
    python3 cardreel.py cards/<slug>            # 카드 render.py 결과 폴더
결과 (reels/<slug>-cards/):
    <slug>-cards.mp4   1080×1920, 카드마다 약 3초(표지 2.4초), 밀어 넘기기 전환 + 작은 효과음
    <slug>-cards_thumb.jpg  표지(01.jpg를 세로 배경 위에)
    manifest.json      video·cover 공개 주소 (S열에 이 두 줄을 넣으면 시트 스크립트가 릴스로 게시)
화면: 배경은 1장(표지)을 흐리게·어둡게 깐 세로 화면, 카드는 가운데(피드 4:5 영역)에 1000px 폭.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRANCH = os.environ.get("CARDS_BRANCH", "main")
RAW = f"https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/{BRANCH}"
W, H, FPS = 1080, 1920, 30
COVER_S, CARD_S, XF = 2.4, 3.1, 0.35


def run(cmd):
    subprocess.run(cmd, check=True)


def frame(bg, card, out):
    """배경(흐림) 위에 카드 한 장을 얹은 1080×1920 이미지."""
    from PIL import Image, ImageFilter, ImageEnhance
    b = Image.open(bg).convert("RGB")
    s = max(W / b.width, H / b.height)
    b = b.resize((int(b.width * s) + 1, int(b.height * s) + 1))
    b = b.crop(((b.width - W) // 2, (b.height - H) // 2, (b.width - W) // 2 + W, (b.height - H) // 2 + H))
    b = ImageEnhance.Brightness(b.filter(ImageFilter.GaussianBlur(28))).enhance(0.45)
    c = Image.open(card).convert("RGB")
    cw = 1000
    c = c.resize((cw, int(c.height * cw / c.width)))
    y = max(300, (H - c.height) // 2 - 40)
    shadow = Image.new("RGB", (cw + 40, c.height + 40), (0, 0, 0))
    b.paste(Image.blend(b.crop(((W - cw) // 2 - 20, y - 10, (W - cw) // 2 + cw + 20, y + c.height + 30)), shadow.resize((cw + 40, c.height + 40)), 0.35),
            ((W - cw) // 2 - 20, y - 10))
    b.paste(c, ((W - cw) // 2, y))
    b.save(out, quality=92)


def main(folder):
    folder = Path(folder)
    slug = folder.name
    cards = sorted(p for p in folder.glob("[0-9][0-9].jpg"))
    if len(cards) < 2:
        sys.exit(f"카드가 2장 미만: {folder}")
    out = ROOT / "reels" / f"{slug}-cards"
    tmp = out / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    frames = []
    for k, c in enumerate(cards):
        f = tmp / f"f{k:02d}.jpg"
        frame(cards[0], c, f)
        frames.append(f)
    durs = [COVER_S] + [CARD_S] * (len(frames) - 1)
    durs[-1] += 0.8
    # 장마다 아주 천천히 확대(살아있는 느낌) → 밀어 넘기기 전환
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for f, d in zip(frames, durs):
        cmd += ["-loop", "1", "-t", f"{d + XF:.2f}", "-i", str(f)]
    fl, prev, acc = [], None, 0.0
    for k, d in enumerate(durs):
        n = int((d + XF) * FPS)
        fl.append(f"[{k}:v]scale=1188:2112,zoompan=z='min(1+0.0006*on,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={n}:s={W}x{H}:fps={FPS},setsar=1[c{k}]")
    for k in range(1, len(durs)):
        acc += durs[k - 1]
        a = f"[c0]" if k == 1 else f"[x{k - 1}]"
        fl.append(f"{a}[c{k}]xfade=transition=slideleft:duration={XF}:offset={acc:.2f}[x{k}]")
    total = sum(durs) + XF
    last = f"[x{len(durs) - 1}]"
    # 효과음: 넘길 때마다 '휙' (reel.py와 같은 직접 만든 소리)
    sys.path.insert(0, str(ROOT))
    import reel
    sfx = reel.sfx_files()["whoosh"]
    cuts = [sum(durs[:k]) for k in range(1, len(durs))]
    ai = len(durs)
    cmd += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    for _ in cuts:
        cmd += ["-i", str(sfx)]
    fl.append("".join(f"[{ai + 1 + j}:a]adelay={int(t * 1000)}:all=1[s{j}];" for j, t in enumerate(cuts))
              + f"[{ai}:a]" + "".join(f"[s{j}]" for j in range(len(cuts)))
              + f"amix=inputs={len(cuts) + 1}:normalize=0:duration=first[aout]")
    mp4 = out / f"{slug}-cards.mp4"
    cmd += ["-filter_complex", ";".join(fl), "-map", last, "-map", "[aout]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)]
    run(cmd)
    thumb = out / f"{slug}-cards_thumb.jpg"
    os.replace(frames[0], thumb)
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()
    base = f"{RAW}/reels/{slug}-cards"
    man = {"slug": f"{slug}-cards", "from_cards": slug, "duration": round(total, 2), "cards": len(cards),
           "video": f"{base}/{mp4.name}", "cover": f"{base}/{thumb.name}"}
    (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(json.dumps(man, ensure_ascii=False))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
