#!/usr/bin/env python3
"""오싹알람 캐러셀 조판: episode.json + panels/*.png -> slides/01.png ... (1080x1350)

사용: python3 ossak/compose.py episodes/W-0001-dyatlov
그림(패널) 위에 내레이션 박스, 부기 말풍선, 표지 제목, 정보 카드, 하단 줄을 얹는다.
글자는 전부 여기서 넣고 AI 그림에는 글자를 넣지 않는다.
"""
import argparse, json, pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H, PAD, GAP, FOOT = 1080, 1350, 44, 20, 40
AW, AH = W - 2 * PAD, H - 2 * PAD - FOOT - GAP  # 992 x 1202
C = {"bg": "#0B101D", "panel": "#0E1424", "card": "#141B30", "ink": "#EDE6D6", "ink2": "#C9CEDA",
     "mute": "#9AA3B8", "navy": "#0E1424", "line": "#2B3452", "teal": "#3FB8A8", "orange": "#E8693A",
     "amber": "#F2B544"}
FONT_FILES = {"serif": "GowunBatang-Bold.ttf", "sans": "NotoSansKR[wght].ttf", "hand": "Gaegu-Bold.ttf"}
_fc = {}


def font(kind, size, weight=500):
    k = (kind, size, weight)
    if k not in _fc:
        f = ImageFont.truetype(str(ROOT / "fonts" / FONT_FILES[kind]), size)
        if kind == "sans":
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
        _fc[k] = f
    return _fc[k]


def wrap(d, text, f, maxw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            t = f"{cur} {word}" if cur else word
            if d.textlength(t, font=f) <= maxw:
                cur = t
                continue
            if cur:
                lines.append(cur)
            cur = ""
            for ch in word:
                if d.textlength(cur + ch, font=f) <= maxw:
                    cur += ch
                else:
                    lines.append(cur)
                    cur = ch
        lines.append(cur)
    return lines


def text_block(d, x, y, text, f, fill, maxw, lh=1.45, measure=False):
    lines = wrap(d, text, f, maxw)
    step = int(f.size * lh)
    if not measure:
        for i, ln in enumerate(lines):
            d.text((x, y + i * step), ln, font=f, fill=fill)
    return len(lines) * step, max((d.textlength(l, font=f) for l in lines), default=0)


def pill(d, x, y, text, bg, fg, size=26):
    f = font("sans", size, 700)
    w = d.textlength(text, font=f) + 36
    h = int(size * 1.7)
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=bg)
    d.text((x + 18, y + h / 2), text, font=f, fill=fg, anchor="lm")
    return w, h


def cover_fit(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def rects(slide):
    lay = slide.get("layout", "one")
    if lay == "one":
        return [(PAD, PAD, AW, AH)]
    if lay == "rows":
        out, y = [], PAD
        for h in slide["heights"]:
            out.append((PAD, y, AW, h))
            y += h + GAP
        return out
    if lay == "top2":
        half = (AW - GAP) // 2
        return [(PAD, PAD, half, 560), (PAD + half + GAP, PAD, half, 560), (PAD, PAD + 580, AW, AH - 580)]
    if lay == "cols2_bottom":  # 위 그림 + 아래 카드 2개
        top = slide["heights"][0]
        half = (AW - GAP) // 2
        y = PAD + top + GAP
        return [(PAD, PAD, AW, top), (PAD, y, half, AH - top - GAP), (PAD + half + GAP, y, half, AH - top - GAP)]
    raise ValueError(lay)


def caption(base, r, cap):
    """이야기 내레이션: 어두운 반투명 박스 + 명조체 (style="note" 이면 예전 크림색 설명 박스)"""
    x, y, w, h = r
    note = cap.get("style") == "note"
    f = font("sans", cap.get("size", 32), 500) if note else font("serif", cap.get("size", 36))
    probe = ImageDraw.Draw(base)
    maxw = int(w * cap.get("maxw", 0.72)) - 56
    th, tw = text_block(probe, 0, 0, cap["text"], f, None, maxw, lh=1.45, measure=True)
    bw, bh = int(tw + 56), int(th + 30)
    pos = cap.get("pos", "tl")
    bx = x + 24 if "l" in pos else x + w - 24 - bw
    by = y + 24 if "t" in pos else y + h - 24 - bh
    if note:
        probe.rectangle((bx, by, bx + bw, by + bh), fill=C["ink"])
        text_block(probe, bx + 28, by + 13, cap["text"], f, C["navy"], maxw)
        return
    box = Image.new("RGBA", (bw, bh), (8, 11, 20, 215))
    base.alpha_composite(box, (bx, by))
    d = ImageDraw.Draw(base)
    text_block(d, bx + 28, by + 13, cap["text"], f, C["ink"], maxw)


def bubble(base, r, b):
    d = ImageDraw.Draw(base)
    x, y, w, h = r
    f = font("hand", b.get("size", 46))
    maxw = int(w * b.get("maxw", 0.5))
    th, tw = text_block(d, 0, 0, b["text"], f, None, maxw, lh=1.3, measure=True)
    bw, bh = tw + 72, th + 52
    bx = x + int(w * b.get("x", 0.46))
    by = y + int(h * b.get("y", 0.12))
    bx = min(bx, x + w - bw - 24)
    tail = b.get("tail", "left")
    if tail == "left":
        d.polygon([(bx + 4, by + 50), (bx - 26, by + 74), (bx + 4, by + 90)], fill=C["ink"])
    elif tail == "down":
        d.polygon([(bx + bw / 2 - 20, by + bh - 4), (bx + bw / 2, by + bh + 28), (bx + bw / 2 + 20, by + bh - 4)], fill=C["ink"])
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=36, fill=C["ink"])
    text_block(d, bx + 36, by + 22, b["text"], f, C["navy"], maxw, lh=1.3)


def cover(base, r, cv, accent):
    x, y, w, h = r
    shade = Image.new("RGBA", (w, int(h * 0.62)))
    sd = ImageDraw.Draw(shade)
    for i in range(shade.height):
        a = int(210 * (1 - i / shade.height) ** 1.4)
        sd.line([(0, i), (w, i)], fill=(14, 20, 36, a))
    base.alpha_composite(shade, (x, y))
    d = ImageDraw.Draw(base)
    _, ph = pill(d, x + 56, y + 56, cv["badge"], accent, C["navy"], 28)
    f = font("serif", cv.get("size", 100))
    ty = y + 56 + ph + 28
    for line in cv["title"]:
        cx = x + 56
        for seg, col in split_accent(line, cv.get("accent_word")):
            d.text((cx, ty), seg, font=f, fill=accent if col else C["ink"])
            cx += d.textlength(seg, font=f)
        ty += int(f.size * 1.2)
    d.text((x + 56, ty + 24), cv["sub"], font=font("sans", 32, 500), fill=C["ink2"])


def split_accent(line, word):
    if not word or word not in line:
        return [(line, False)]
    a, b = line.split(word, 1)
    return [(a, False), (word, True), (b, False)]


def card(base, r, cd, accent):
    d = ImageDraw.Draw(base)
    x, y, w, h = r
    d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=C["card"])
    pad = cd.get("pad", 44)
    cx, cy, cw = x + pad, y + pad, w - 2 * pad
    t = cd["type"]
    if cd.get("badge"):
        _, ph = pill(d, cx, cy, cd["badge"], cd.get("badge_color", accent), C["navy"], 26)
        if cd.get("badge_note"):
            d.text((cx + d.textlength(cd["badge"], font=font("sans", 26, 700)) + 56, cy + ph / 2), cd["badge_note"], font=font("sans", 26, 400), fill=C["mute"], anchor="lm")
        cy += ph + 28
    if cd.get("title"):
        f = font("serif", cd.get("title_size", 60))
        d.text((cx, cy), cd["title"], font=f, fill=C["ink"])
        cy += int(f.size * 1.3)
    if cd.get("subtitle"):
        d.text((cx, cy), cd["subtitle"], font=font("sans", 26, 400), fill=C["mute"])
        cy += 26 + 36
    if t == "evidence":
        n = len(cd["items"])
        iw = (cw - 24 * (n - 1)) // n
        for i, it in enumerate(cd["items"]):
            ix = cx + i * (iw + 24)
            d.rounded_rectangle((ix, cy, ix + iw, cy + cd.get("item_h", 340)), radius=16, fill=C["navy"], outline=C["line"], width=2)
            hh, _ = text_block(d, ix + 28, cy + 28, it["head"], font("serif", 40), C["ink"], iw - 56, lh=1.3)
            text_block(d, ix + 28, cy + 28 + hh + 14, it["body"], font("sans", 24, 400), C["ink2"], iw - 56, lh=1.5)
    elif t == "list":
        for it in cd["items"]:
            hf, bf = font("sans", 40, 700), font("sans", 29, 400)
            inner = cw - 64
            body_h = sum(text_block(d, 0, 0, ln, bf, None, inner, measure=True)[0] for ln in it["lines"])
            ih = 36 + 60 + body_h + 32
            border = accent if it.get("highlight") else C["line"]
            d.rounded_rectangle((cx, cy, cx + cw, cy + ih), radius=16, fill=C["navy"], outline=border, width=2)
            d.text((cx + 32, cy + 28), it["head"], font=hf, fill=C["ink"])
            if it.get("tag"):
                pill(d, cx + 32 + d.textlength(it["head"], font=hf) + 16, cy + 32, it["tag"], accent if it.get("highlight") else C["line"], C["navy"] if it.get("highlight") else C["ink"], 20)
            ly = cy + 36 + 60
            for j, ln in enumerate(it["lines"]):
                hgt, _ = text_block(d, cx + 32, ly, ln, bf, C["ink2"] if j == 0 else C["mute"], inner)
                ly += hgt
            cy += ih + 30
    elif t == "timeline":
        n = len(cd["items"])
        colw = (cw - 20 * (n - 1)) // n
        d.line((cx + 12, cy + 12, cx + cw - 12, cy + 12), fill=C["line"], width=3)
        for i, it in enumerate(cd["items"]):
            ix = cx + i * (colw + 20)
            hl = it.get("highlight")
            d.ellipse((ix, cy, ix + 24, cy + 24), fill=accent if hl else C["navy"], outline=None if hl else "#7C86A2", width=3)
            d.text((ix, cy + 40), it["head"], font=font("sans", 38, 700), fill=accent if hl else C["ink"])
            text_block(d, ix, cy + 100, it["body"], font("sans", 26, 400), C["ink2"], colw)
    elif t == "text":
        for ln in cd["lines"]:
            f = font("serif", ln.get("size", 40)) if ln.get("serif") else font("sans", ln.get("size", 22), ln.get("weight", 400))
            hgt, _ = text_block(d, cx, cy, ln["text"], f, ln.get("color", C["ink2"]), cw, lh=ln.get("lh", 1.5))
            cy += hgt + ln.get("gap", 10)
    if cd.get("border"):
        d.rounded_rectangle((x, y, x + w, y + h), radius=6, outline=cd["border"], width=2)


def build(ep):
    spec = json.loads((ep / "episode.json").read_text(encoding="utf-8"))
    accent = spec.get("accent", C["amber"])
    out = ep / "slides"
    out.mkdir(exist_ok=True)
    n = len(spec["slides"])
    for i, slide in enumerate(spec["slides"], 1):
        base = Image.new("RGBA", (W, H), C["bg"])
        for r, cell in zip(rects(slide), slide["cells"]):
            x, y, w, h = r
            if "panel" in cell:
                cands = [ep / "panels" / f'{cell["panel"]}{x}' for x in (".png", ".jpg")]
                cands = [c for c in cands if c.exists()] or cands[:1]
                src = max(cands, key=lambda c: c.stat().st_mtime if c.exists() else 0)  # png·jpg 중 최신
                if src.exists():
                    base.paste(cover_fit(Image.open(src).convert("RGB"), w, h), (x, y))
                else:
                    ImageDraw.Draw(base).rectangle((x, y, x + w, y + h), fill=C["panel"])
                    ImageDraw.Draw(base).text((x + w / 2, y + h / 2), f'[{cell["panel"]} 미생성]', font=font("sans", 28), fill=C["mute"], anchor="mm")
            if "card" in cell:
                card(base, r, cell["card"], accent)
            if "cover" in cell:
                cover(base, r, cell["cover"], accent)
            if "caption" in cell:
                caption(base, r, cell["caption"])
            if "bubble" in cell:
                bubble(base, r, cell["bubble"])
        d = ImageDraw.Draw(base)
        fy = H - PAD - FOOT / 2
        left = slide.get("footer_left", spec["footer"])
        d.text((PAD, fy), left, font=font("sans", 24, 400), fill=C["mute"], anchor="lm")
        if i == 1:
            d.text((W - PAD, fy), "넘겨보세요 →", font=font("sans", 26, 700), fill=accent, anchor="rm")
        else:
            d.text((W - PAD, fy), f"{i} / {n}", font=font("sans", 24, 400), fill=C["mute"], anchor="rm")
        base.convert("RGB").save(out / f"{i:02d}.png", optimize=True)
        print("slide", i)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    build(pathlib.Path(ap.parse_args().episode))
