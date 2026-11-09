"""접촉 시트 — 여러 이미지를 번호 붙여 한 장으로 (2026-11-09 사용자 결정 "이미지는 한 장씩 열지 말고 한 장으로 모아 보기").

예약 작업(①④⑦⑧)이 사진 후보·카드 장·영상 프레임·스크린샷을 Read로 한 장씩 열면 장마다 이미지 토큰이 든다.
이 도구로 한 장에 모아 그 한 장만 열고, 문제가 보이는 번호만 원본으로 다시 연다.

  python3 tools/contact.py photos/mood/a.jpg photos/mood/b.jpg … -o /tmp/sheet.jpg
  python3 tools/contact.py cards/<slug> -o /tmp/cards.jpg            # 폴더면 그 안의 NN.jpg (없으면 jpg·png 전부)
  python3 tools/contact.py reels/<slug>/reel.mp4 --every 1.5 -o /tmp/frames.jpg   # 영상이면 N초 간격 프레임
옵션: --cols 4 (열 수) · --width 1800 (시트 가로 px, 글자 검사면 1800 이상) · --max 24 (최대 장 수)
출력 마지막 줄에 [번호] → 파일 목록을 찍는다.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMG = {".jpg", ".jpeg", ".png", ".webp"}


def frames(video, every):
    tmp = Path(tempfile.mkdtemp(prefix="contact_"))
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=1/{every}", str(tmp / "f%03d.jpg")], check=True)
    return sorted(tmp.glob("f*.jpg"))


def collect(items, every):
    out = []
    for it in items:
        p = Path(it)
        if p.is_dir():
            nn = sorted(x for x in p.glob("[0-9][0-9].jpg"))
            out += nn or sorted(x for x in p.iterdir() if x.suffix.lower() in IMG and x.name != "contact.jpg")
        elif p.suffix.lower() in (".mp4", ".mov", ".webm"):
            out += frames(p, every)
        elif p.suffix.lower() in IMG:
            out.append(p)
    return out


def font(size):
    for f in ("fonts/Pretendard-Bold.otf", "fonts/Pretendard-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(str(Path(__file__).resolve().parents[1] / f) if not f.startswith("/") else f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build(paths, out, cols=4, width=1800):
    cols = max(1, min(cols, len(paths)))
    tw = width // cols
    ims = []
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((tw - 8, tw * 2))
            ims.append(im)
        except OSError:
            ims.append(None)
    th = max((im.height for im in ims if im), default=tw) + 34
    sheet = Image.new("RGB", (tw * cols, th * ((len(paths) + cols - 1) // cols)), "white")
    d = ImageDraw.Draw(sheet)
    f = font(20)
    for k, im in enumerate(ims):
        x, y = (k % cols) * tw, (k // cols) * th
        if im:
            sheet.paste(im, (x + 4, y + 30))
        d.rectangle([x + 4, y + 2, x + 64, y + 28], fill="black")
        d.text((x + 10, y + 4), f"[{k + 1}]", fill="white", font=f)
    sheet.save(out, quality=86)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="+")
    ap.add_argument("-o", "--out", default="/tmp/contact.jpg")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--width", type=int, default=1800)
    ap.add_argument("--every", type=float, default=1.5)
    ap.add_argument("--max", type=int, default=24)
    a = ap.parse_args()
    paths = collect(a.items, a.every)[: a.max]
    if not paths:
        sys.exit("이미지 없음")
    build(paths, a.out, a.cols, a.width)
    print(a.out)
    print(" · ".join(f"[{k + 1}] {p.name}" for k, p in enumerate(paths)))


if __name__ == "__main__":
    main()
