"""공고 공유 썸네일(og.jpg, 1200×630) — 디자인 시안 B를 남색 하나로 (사용자 결정 2026-10-29).
사진(조감도) 있으면 사진 위 아래쪽 어둡게 + 글자, 없으면 남색 배경. 문구는 build.py og_lines() 값만 재배치(새 숫자 없음)."""
import json, re, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / "og_assets"
W, H = 1200, 630
BHS = str(REPO / "fonts/BlackHanSans-Regular.ttf")
NOTO = str(REPO / "fonts/NotoSansKR-VF.ttf")
NOGLYPH = set("·・‧∙•㎡")  # Black Han Sans에 없는 글자 → Noto Bold

# 토큰 (site/static/style.css :root + render.py THEMES)
INK, INK_SUB, BAND, PAPER = "#0F1E3D", "#5B6472", "#F4F6F9", "#FFFFFF"
CORAL, CORAL_STRONG, CORAL_TINT = "#FF5233", "#C8361A", "#FFF1EC"
THEME = {  # render.py THEMES 중 표지에 쓰는 값
    "줍줍알람": dict(bg="#0F1E3D", chip_bg="#FF5233", chip_fg="#FFFFFF", hl="#FF7A5C", sub="#C9D1E0"),
    "내집마련": dict(bg="#1E4FD8", chip_bg="#FFFFFF", chip_fg="#1E4FD8", hl="#FFD84D", sub="#DCE6FF"),
    "임대알람": dict(bg="#0E5C4A", chip_bg="#3DDC97", chip_fg="#0B2E25", hl="#7FF0BE", sub="#CDEBE0"),
}
KIND_SERIES = {"mujeonwi": "줍줍알람", "rental": "임대알람", "public": "내집마련", "newlywed": "내집마련", "private": "내집마련"}

_fc = {}


def bhs(sz):
    k = ("b", sz)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(BHS, sz)
    return _fc[k]


def noto(sz, w="Bold"):
    k = ("n", sz, w)
    if k not in _fc:
        f = ImageFont.truetype(NOTO, sz)
        f.set_variation_by_name(w)
        _fc[k] = f
    return _fc[k]


def runs(t, f):
    """Black Han Sans에 없는 글자만 같은 크기 Noto Bold로 바꿔 그린다."""
    if f.path != BHS:
        return [(t, f)]
    out, cur, cm = [], "", None
    for ch in t:
        m = ch in NOGLYPH
        if cm is not None and m != cm:
            out.append((cur, noto(f.size, "Bold") if cm else f)); cur = ""
        cm = m; cur += ch
    if cur:
        out.append((cur, noto(f.size, "Bold") if cm else f))
    return out


def tw(dr, t, f):
    return sum(dr.textlength(s, font=g) for s, g in runs(t, f))


def text(dr, x, base, t, f, fill, align="l"):
    """기준선(base) 위에 그림. align l/m/r."""
    w = tw(dr, t, f)
    if align == "m":
        x -= w / 2
    elif align == "r":
        x -= w
    for s, g in runs(t, f):
        dr.text((x, base), s, font=g, fill=fill, anchor="ls")
        x += dr.textlength(s, font=g)
    return w


def spans(dr, x, base, parts, align="l"):
    """parts = [(문자열, 글꼴, 색)] 한 줄에 이어 그림."""
    tot = sum(tw(dr, s, f) for s, f, _ in parts)
    if align == "m":
        x -= tot / 2
    elif align == "r":
        x -= tot
    for s, f, c in parts:
        x += text(dr, x, base, s, f, c)
    return tot


def fit(dr, t, maker, start, maxw, lo):
    sz = start
    while sz > lo and tw(dr, t, maker(sz)) > maxw:
        sz -= 2
    return maker(sz)


def ellipsize(dr, t, f, maxw):
    if tw(dr, t, f) <= maxw:
        return t
    while t and tw(dr, t + "…", f) > maxw:
        t = t[:-1]
    return t.rstrip() + "…"


def chip(dr, x, y, t, f, h, fill=None, fg="#FFFFFF", outline=None, pad=22, r=None):
    w = tw(dr, t, f) + pad * 2
    r = h // 2 if r is None else r
    if fill:
        dr.rounded_rectangle((x, y, x + w, y + h), r, fill=fill)
    if outline:
        dr.rounded_rectangle((x, y, x + w, y + h), r, outline=outline, width=3)
    # 글자 세로 가운데: Noto는 'lm' 앵커가 안정적
    dr.text((x + pad, y + h / 2 + 1), t, font=f, fill=fg, anchor="lm")
    return w


def paste_icon(im, name, x, y, size):
    ic = Image.open(ASSETS / f"{name}.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    im.paste(ic, (int(x), int(y)), ic)


def photo_bg(src, pos):
    im = Image.open(REPO / src).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    fy = 0.5
    m = re.search(r"(\d+(?:\.\d+)?)%\s*$", str(pos or ""))
    if m:
        fy = min(max(float(m.group(1)) / 100, 0), 1)
    x, y = (im.width - W) // 2, round((im.height - H) * fy)
    return im.crop((x, y, x + W, y + H))


def shade(im, stops, color=(0, 0, 0)):
    """세로 그라데이션 덮개. stops=[(y비율, 불투명도)]"""
    col = []
    for yy in range(H):
        t = yy / (H - 1)
        for (a, va), (b, vb) in zip(stops, stops[1:]):
            if a <= t <= b:
                v = va + (vb - va) * ((t - a) / (b - a) if b > a else 0)
                break
        else:
            v = stops[-1][1]
        col.append(int(255 * v))
    a = Image.new("L", (1, H))
    a.putdata(col)
    ov = Image.new("RGBA", (W, H), (*color, 0))
    ov.putalpha(a.resize((W, H)))
    base = im.convert("RGBA")
    base.alpha_composite(ov)
    return base.convert("RGB")


# ───────── 문구 → 구조 (og_lines 값만 재배치, 새 숫자 없음) ─────────
def segs(big):
    out = []
    for s in [x for x in big.split(" · ") if x]:
        toks = s.split(" ")
        # 값 = 숫자가 처음 나오는 토큰부터 (면적 '84㎡'·'84A'는 라벨 쪽)
        isnum = lambda t: any(c.isdigit() for c in t) and not re.search(r"(㎡|형|[A-Z])$", t)
        i = next((j for j, t in enumerate(toks) if isnum(t)), len(toks))
        if 0 < i < len(toks) and toks[i - 1] in ("약", "최대", "최저"):  # 한정어는 숫자와 떼지 않음
            i -= 1
        out.append((" ".join(toks[:i]), " ".join(toks[i:])))
    return out


def hero(big):
    """(위 작은 줄, [(라벨, 값)]) — 경쟁률은 'N대 1'을 주인공으로."""
    ss = segs(big)
    comp = [s for s in ss if s[1].endswith("대 1")]
    if comp and len(ss) > 1:
        other = [(" ".join(x for x in s if x)) for s in ss if s not in comp]
        return " · ".join(other), comp[:1]
    return "", ss


METRO = ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종")


def place(loc):
    """'경기 이천시' → '이천시', '서울 중구'·'인천'은 그대로."""
    t = loc.split(" ")
    return loc if len(t) < 2 or t[0] in METRO else t[-1]


def credit_short(c):
    return re.sub(r"^이미지:\s*", "", c or "")


def render(L, photo=None, credit=None):
    kind, st, title, loc, big, small = L[:6]
    head = L[6] if len(L) > 6 else None  # 윗줄을 지역·유형 대신 훅으로 (줍줍 '통장 없이' 등)
    th = dict(THEME["줍줍알람"])  # 시리즈 색 대신 남색 하나 (사용자 결정)
    if photo:
        im = photo_bg(photo["image"], photo.get("pos"))
        im = shade(im, [(0, .5), (.14, .35), (.26, .66), (.78, .74), (1, .82)])  # 가운데 글자 아래가 어둡게
        th = dict(THEME["줍줍알람"], sub="#E6EAF1")
    else:
        im = Image.new("RGB", (W, H), th["bg"])
    dr = ImageDraw.Draw(im)
    X = 64
    maxw = W - X * 2
    paste_icon(im, "bell_white", X - 4, 40, 50)
    text(dr, X + 52, 80, "줍줍알람", noto(32, "Bold"), "#FFFFFF")
    if credit:  # 사이트 .hero-credit처럼 어두운 판 위에 (밝은 사진에서도 읽히게)
        cf = noto(20, "Medium")
        ct = credit_short(credit)
        cw = tw(dr, ct, cf)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ov).rounded_rectangle((W - 40 - cw - 14, 48, W - 26, 82), 6, fill=(15, 30, 61, 170))
        im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
        dr = ImageDraw.Draw(im)
        text(dr, W - 33, 72, ct, cf, "#FFFFFF", "r")
    kick, rows = hero(big)
    if len(rows) == 2:  # 보증금 · 월 — 윗줄은 어디·무엇(훅), 아랫줄에 두 금액
        l1 = [(head or (place(loc) + " " + kind), "#FFFFFF")]
        l2 = [(rows[0][0] + " ", "#FFFFFF"), (rows[0][1], th["hl"]), (" · " + rows[1][0] + " ", "#FFFFFF"), (rows[1][1], th["hl"])]
        sub = small
    elif kick:  # 경쟁률 (예전 형식)
        l1 = [(kick, "#FFFFFF")]
        l2 = [(rows[0][1], th["hl"])]
        sub = small
    else:
        l1 = [(head or (place(loc) + " " + kind), "#FFFFFF")]
        l2 = [((rows[0][0] + " ") if rows[0][0] else "", "#FFFFFF"), (rows[0][1], th["hl"])]
        sub = small
    sz = 96
    while sz > 60 and max(sum(tw(dr, s, bhs(sz)) for s, _ in ln) for ln in (l1, l2)) > maxw:
        sz -= 4
    fs = fit(dr, sub, lambda s: noto(s, "Medium"), 34, maxw, 26)
    # 글자 묶음(칩~작은 줄)을 세로 가운데에 (사용자 요청 2026-10-29 "제목이 아래로 치우침")
    sub_h = 62 if sub else 0                         # 작은 줄이 없으면(훅만) 그만큼 묶음이 작아짐
    blk = 58 + 2 * int(sz * 1.12) + sub_h + 12       # 칩 + 두 줄 + 작은 줄 + 아랫부분
    top = max(118, (H - blk) // 2 + 14)              # 위 로고(~90px)와 겹치지 않게, 살짝 아래로 무게
    yb = top + blk - 12
    if sub:
        text(dr, X, yb, sub, fs, th["sub"])
    yb -= sub_h
    for ln in (l2, l1):
        spans(dr, X, yb, [(s, bhs(sz), c) for s, c in ln if s]); yb -= int(sz * 1.12)
    # 칩: 시리즈색 칩(분류) + 테두리 칩(상태)
    f = noto(30, "Bold")
    y = yb - 56 - 2
    one = not kick and not (head and head != (place(loc) + " " + kind) and kind not in head)  # 윗줄에 유형이 보이면 칩은 상태 하나
    x = X + chip(dr, X, y, st if one else kind, f, 56, fill=th["chip_bg"], fg=th["chip_fg"], r=12) + 12
    if not one:
        chip(dr, x, y, st, f, 56, outline="#FFFFFF", fg="#FFFFFF", r=12)
    return im


