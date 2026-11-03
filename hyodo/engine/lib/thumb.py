"""썸네일 1280×720: 큰 숫자 + 대상 배지 + 한 줄 + 막내 캐릭터. python3 lib/thumb.py episodes/<편>"""
import json, pathlib, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
C = {"bg": "#FFF8EC", "ink": "#1F2A44", "green": "#1F5C4B", "greenTint": "#E3F1EB", "orange": "#E8693A", "amber": "#F2B544"}


def font(size):
    return ImageFont.truetype(BLACK, size, index=1)


def fit(d, text, maxw, start):
    s = start
    while s > 40 and d.textlength(text, font=font(s)) > maxw:
        s -= 4
    return font(s)


def make(ep, pose="point"):
    spec = json.loads((ep / "video.json").read_text()); t = spec["thumb"]
    W, H = 1280, 720
    im = Image.new("RGB", (W, H), C["bg"]); d = ImageDraw.Draw(im)
    # 오른쪽 캐릭터 원
    d.ellipse([820, 110, 1260, 550], fill=C["greenTint"])
    ch = Image.open(ROOT / "assets" / "char" / f"{pose}_cut.png"); ch.thumbnail((470, 600))
    im.paste(ch, (1040 - ch.width // 2, H - ch.height), ch)
    # 브랜드
    d.rounded_rectangle([40, 34, 270, 96], radius=31, fill=C["green"])
    d.text((62, 40), "효도", font=font(40), fill="white"); d.text((150, 40), "알람", font=font(40), fill=C["amber"])
    # 배지
    bf = font(46); bw = d.textlength(t["age"], font=bf)
    d.rounded_rectangle([44, 140, 44 + bw + 56, 214], radius=37, outline=C["orange"], width=6, fill="white")
    d.text((72, 146), t["age"], font=bf, fill=C["orange"])
    # 큰 숫자
    big = fit(d, t["big"], 780, 210)
    d.text((40, 222), t["big"], font=big, fill=C["orange"], stroke_width=4, stroke_fill="white")
    # 한 줄 (노란 띠)
    sf = fit(d, t["sub"], 760, 112); sw = d.textlength(t["sub"], font=sf)
    d.rectangle([40, 548, 40 + sw + 36, 660], fill=C["amber"])
    d.text((58, 540), t["sub"], font=sf, fill=C["ink"])
    out = ep / "out" / f"{spec['id']}_thumb.jpg"
    im.save(out, quality=92)
    return out


if __name__ == "__main__":
    print(make(pathlib.Path(sys.argv[1]).resolve()))
