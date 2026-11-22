"""숙소 사이트용 사진·영상 만들기 (한 번 만들어 media/ 에 커밋, build.py가 public/로 복사).

python3 2kids/site/media.py            # 없는 것만 만듦
python3 2kids/site/media.py T005 --force

입력
- 2kids/travel/out/photos/T###/A_*.jpg (릴스·스레드에 쓴 사진) — 없으면 NN.jpg
- 2kids/travel/out/T###-A.mp4 · T###-A_cover.jpg (우리 채널에 올린 릴스)
- data/sheet/사진출처.json · 채널.json
출력: media/<slug>/
- p1.webp… (긴 변 1280) · p1s.webp… (카드용 긴 변 640) · reel.mp4 (720×1280) · poster.webp · media.json
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
TRAVEL = HERE.parent / "travel" / "out"
MEDIA = HERE / "media"
MAX_PHOTOS = 6


def pick_photos(sid):
    d = TRAVEL / "photos" / sid
    if not d.exists():
        return []
    fs = sorted(p for p in d.glob("*.jpg") if p.name != "thumb.jpg")
    reel = [p for p in fs if re.match(r"[A-Z]_\d+\.jpg$", p.name)]
    reel.sort(key=lambda p: (p.name[0] != "A", p.name))
    plain = [p for p in fs if re.match(r"\d+\.jpg$", p.name)]
    return (reel or plain)[:MAX_PHOTOS]


def credit_of(sid, name, src):
    m = re.search(r"(\d+)\.jpg$", name)
    n = int(m.group(1)) if m else -1
    return "쿠팡 트래블 상세" if n in src["coupang"].get(sid, []) else src["default"]


def save_webp(src, dst, long_side, q):
    im = Image.open(src).convert("RGB")
    im.thumbnail((long_side, long_side), Image.LANCZOS)
    im.save(dst, "WEBP", quality=q, method=6)
    return im.size


def make(st, channel, src, force=False):
    sid, slug = st["id"], st["slug"]
    out = MEDIA / slug
    meta_f = out / "media.json"
    if meta_f.exists() and not force:
        return json.loads(meta_f.read_text())
    out.mkdir(parents=True, exist_ok=True)
    meta = {"photos": [], "reel": None}
    for i, p in enumerate(pick_photos(sid), 1):
        w, h = save_webp(p, out / f"p{i}.webp", 1280, 74)
        save_webp(p, out / f"p{i}s.webp", 640, 70)
        meta["photos"].append({"src": f"p{i}.webp", "small": f"p{i}s.webp", "w": w, "h": h,
                               "credit": credit_of(sid, p.name, src)})
    mp4 = TRAVEL / f"{sid}-A.mp4"
    if mp4.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", "scale=720:-2",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-profile:v", "high", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(out / "reel.mp4")], check=True)
        cover = TRAVEL / f"{sid}-A_cover.jpg"
        save_webp(cover, out / "poster.webp", 1280, 72)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(out / "reel.mp4")], capture_output=True, text=True).stdout.strip() or 0)
        spec = json.loads((TRAVEL / f"{sid}-A.json").read_text()) if (TRAVEL / f"{sid}-A.json").exists() else {}
        ch = channel.get(f"{sid}-A", {})
        meta["reel"] = {"src": "reel.mp4", "poster": "poster.webp", "seconds": round(dur, 1),
                        "hook": spec.get("hook", ""), "published": ch.get("published", ""),
                        "instagram": ch.get("instagram", ""), "youtube": ch.get("youtube", "")}
    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    src = json.loads((HERE / "data/sheet/사진출처.json").read_text())
    channel = {r["slug"]: r for r in json.loads((HERE / "data/sheet/채널.json").read_text())["rows"]}
    for f in sorted((HERE / "data/stays").glob("T*.json")):
        st = json.loads(f.read_text())
        if args and st["id"] not in args:
            continue
        m = make(st, channel, src, force)
        print(st["id"], st["slug"], f"사진 {len(m['photos'])}장", "영상" if m["reel"] else "영상 없음")


if __name__ == "__main__":
    main()
