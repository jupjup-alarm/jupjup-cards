"""썸네일 1280×720. python3 lib/thumb.py episodes/<편>

2026-11-04 벤치마크 분석 반영(새 형식, video.json thumb에 img가 있으면):
  - 배경: 사람의 상황이 보이는 그림(thumb.img 문구 → lib/illust.py), 아래쪽을 어둡게
  - 글자: 하단 2줄 대형 — 1줄 대상 호명(thumb.age, 흰색), 2줄 숫자·손익(thumb.big, 노랑), 검은 테두리, 폭 80~95%
  - 막내: 오른쪽, 놀람·걱정 같은 표정(thumb.mood, 기본 surprised)
  - thumb.sub는 쓰지 않는다(있으면 작은 칩으로 위에)
img가 없으면 예전 형식(크림 배경 + 큰 숫자 + 노란 띠).
"""
import json, pathlib, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

LIB = pathlib.Path(__file__).resolve().parent
ROOT = LIB.parent
BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
C = {"bg": "#FFF8EC", "ink": "#1F2A44", "green": "#1F5C4B", "greenTint": "#E3F1EB", "orange": "#E8693A", "amber": "#F2B544",
     "yellow": "#FFD54A", "sky": "#8FD3FF"}


def font(size):
    return ImageFont.truetype(BLACK, size, index=1)


def fit(d, text, maxw, start, stroke=0):
    s = start
    while s > 40 and d.textlength(text, font=font(s)) + stroke * 2 > maxw:
        s -= 4
    return font(s)


def make_old(ep, spec, t, pose="point"):
    W, H = 1280, 720
    im = Image.new("RGB", (W, H), C["bg"]); d = ImageDraw.Draw(im)
    d.ellipse([820, 110, 1260, 550], fill=C["greenTint"])
    ch = Image.open(ROOT / "assets" / "char" / f"{pose}_cut.png"); ch.thumbnail((470, 600))
    im.paste(ch, (1040 - ch.width // 2, H - ch.height), ch)
    d.rounded_rectangle([40, 34, 270, 96], radius=31, fill=C["green"])
    d.text((62, 40), "효도", font=font(40), fill="white"); d.text((150, 40), "알람", font=font(40), fill=C["amber"])
    bf = font(46); bw = d.textlength(t["age"], font=bf)
    d.rounded_rectangle([44, 140, 44 + bw + 56, 214], radius=37, outline=C["orange"], width=6, fill="white")
    d.text((72, 146), t["age"], font=bf, fill=C["orange"])
    big = fit(d, t["big"], 780, 210)
    d.text((40, 222), t["big"], font=big, fill=C["orange"], stroke_width=4, stroke_fill="white")
    sf = fit(d, t["sub"], 760, 112); sw = d.textlength(t["sub"], font=sf)
    d.rectangle([40, 548, 40 + sw + 36, 660], fill=C["amber"])
    d.text((58, 540), t["sub"], font=sf, fill=C["ink"])
    return im


def make_new(ep, spec, t):
    import illust
    W, H = 1280, 720
    src = illust.cached(t["img"], ep / "out" / "illust", w=1216, h=688)
    bg = Image.open(src).convert("RGB")
    r = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * r + 1), int(bg.height * r + 1)), Image.LANCZOS)
    x0 = (bg.width - W) // 2; y0 = int((bg.height - H) * 0.3)
    im = bg.crop((x0, y0, x0 + W, y0 + H))
    # 아래쪽 어둡게(글자 자리)
    shade = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(shade)
    for y in range(H):
        a = max(0, (y - H * 0.38) / (H * 0.62))
        sd.line([(0, y), (W, y)], fill=int(205 * min(1, a) ** 1.2))
    im = Image.composite(Image.new("RGB", (W, H), (10, 10, 14)), im, shade)
    # 막내(오른쪽, 표정)
    mood = t.get("mood", "surprised")
    cf = ROOT / "assets" / "char" / f"{mood}_cut.png"
    if not cf.exists():
        cf = ROOT / "assets" / "char" / "point_cut.png"
    ch = Image.open(cf); ch.thumbnail((420, 560))
    glow = Image.new("RGBA", ch.size, (0, 0, 0, 0)); glow.putalpha(ch.split()[3].filter(ImageFilter.GaussianBlur(10)))
    white = Image.new("RGBA", ch.size, (255, 255, 255, 255)); white.putalpha(ch.split()[3].filter(ImageFilter.MaxFilter(9)))
    px, py = W - ch.width - 10, H - ch.height + 10  # 아래에 붙여 세우고, 글자가 그 위에 얹힌다
    im.paste(white, (px, py), white); im.paste(ch, (px, py), ch)
    d = ImageDraw.Draw(im)
    # 브랜드
    d.rounded_rectangle([28, 24, 244, 82], radius=29, fill=C["green"])
    d.text((48, 28), "효도", font=font(38), fill="white"); d.text((131, 28), "알람", font=font(38), fill=C["amber"])
    if t.get("sub"):
        sf = font(40); sw = d.textlength(t["sub"], font=sf)
        d.rounded_rectangle([28, 96, 28 + sw + 44, 156], radius=30, fill=(0, 0, 0))
        d.text((50, 100), t["sub"], font=sf, fill="white")
    # 하단 2줄 대형
    maxw = W - 80
    f1 = fit(d, t["age"], maxw * 0.85, 112, 8)
    f2 = fit(d, t["big"], maxw, 176, 10)
    h2 = f2.getbbox(t["big"])[3]
    y2 = H - 40 - h2
    y1 = y2 - f1.getbbox(t["age"])[3] - 6
    d.text((40, y1), t["age"], font=f1, fill="white", stroke_width=8, stroke_fill="black")
    d.text((40, y2), t["big"], font=f2, fill=C["yellow"], stroke_width=10, stroke_fill="black")
    return im


def make(ep, pose="point"):
    spec = json.loads((ep / "video.json").read_text()); t = spec["thumb"]
    im = make_new(ep, spec, t) if t.get("img") else make_old(ep, spec, t, pose)
    out = ep / "out" / f"{spec['id']}_thumb.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=92)
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(LIB))
    print(make(pathlib.Path(sys.argv[1]).resolve()))
