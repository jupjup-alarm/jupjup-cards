#!/usr/bin/env python3
"""줍줍알람 카드뉴스 렌더러.

카드 원고(JSON) → 1080×1350 JPG + 미리보기 + Claude Design 캔버스용 .dc.html

사용법:
    python3 render.py specs/2026-10-24-gyeonggi.json
    python3 render.py specs/*.json

결과:
    cards/<slug>/01.jpg … NN.jpg   (인스타 게시용)
    cards/<slug>/preview.jpg       (한눈에 보기)
    cards/<slug>/dc/*.dc.html      (캔버스 아트보드용)
    cards/<slug>/manifest.json     (공개 이미지 주소 목록, 넘침 경고)
표준출력 마지막 줄에 공개 이미지 주소들을 줄바꿈으로 출력.
"""
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
TPL = ROOT / "templates"
OWNER_REPO = "jupjup-alarm/jupjup-cards"
BRANCH = os.environ.get("CARDS_BRANCH", "main")   # 이미지를 올릴 브랜치 (공개 주소에 들어감)
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER_REPO}/{BRANCH}"
W, H = 1080, 1350

# ---------------------------------------------------------------- 시리즈 테마
THEMES = {
    "줍줍알람": dict(bg="#0F1E3D", logo="#FF5233", chip_bg="#FF5233", chip_fg="#FFFFFF", outline="#FF5233",
                  hl="#FF7A5C", sub="#C9D1E0", ink="#FFFFFF", spark="#FF5233",
                  accent="#E0401F", tint="#FFF1EC", soft="#FFF1EC", btn="#0F1E3D"),
    "강남로또": dict(bg="#121212", logo="#FF5233", chip_bg="#C9A24A", chip_fg="#121212", outline="#C9A24A",
                  hl="#E5C77A", sub="#BDBDBD", ink="#C9A24A", spark="#C9A24A",
                  accent="#8A6A1F", tint="#F7F1E3", soft="#F7F1E3", btn="#121212"),
    "내집마련": dict(bg="#1E4FD8", logo="#FFFFFF", chip_bg="#FFFFFF", chip_fg="#1E4FD8", outline="#FFFFFF",
                  hl="#FFD84D", sub="#DCE6FF", ink="#FFFFFF", spark="#FFD84D",
                  accent="#1E4FD8", tint="#EEF3FF", soft="#EEF3FF", btn="#1E4FD8"),
    "임대알람": dict(bg="#0E5C4A", logo="#3DDC97", chip_bg="#3DDC97", chip_fg="#0B2E25", outline="#3DDC97",
                  hl="#7FF0BE", sub="#CDEBE0", ink="#FFFFFF", spark="#3DDC97",
                  accent="#0E7A5F", tint="#E8F7F1", soft="#E8F7F1", btn="#0E5C4A"),
    "이번주청약": dict(bg="#FF5233", fg="#0F1E3D", logo="#0F1E3D", chip_bg="#0F1E3D", chip_fg="#FFFFFF", outline="#0F1E3D",
                  chip2_fg="#0F1E3D", body="#FFFFFF", hl="#FFFFFF", sub="#0F1E3D", ink="#0F1E3D", spark="#FFFFFF",
                  accent="#E0401F", tint="#F2F4F7", soft="#FFF1EC", btn="#0F1E3D"),
    "주거꿀팁": dict(bg="#4B2A8C", logo="#FFFFFF", chip_bg="#FFFFFF", chip_fg="#4B2A8C", outline="#FFFFFF",
                  hl="#FFD84D", sub="#E3DAFF", ink="#FFFFFF", spark="#FFD84D",
                  accent="#4B2A8C", tint="#F1ECFA", soft="#F1ECFA", btn="#4B2A8C"),
}
NAVY, GRAY, LINE = "#0F1E3D", "#5B6472", "#E3E7ED"
FACES = {"깜짝": "surprise", "신남": "happy", "윙크": "wink"}

BELL = ('<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M6 16v-5a6 6 0 0 1 12 0v5l2 2H4l2-2z"></path>'
        '<path d="M10 20a2 2 0 0 0 4 0"></path></svg>')
ARROW = ('<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.4" '
         'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="M13 6l6 6-6 6"></path></svg>')
FOLLOW = ('<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" '
          'stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="4"></circle>'
          '<path d="M2 21a7 7 0 0 1 14 0"></path><path d="M19 8v6M16 11h6"></path></svg>')
SAVE = ('<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12v18l-6-4-6 4z"></path></svg>')


def esc(s):
    return html.escape(str(s or ""))


def hl(text, word, color):
    """text 안의 word(들)를 색으로 강조. **굵게** 표기도 강조로 처리."""
    t = esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", lambda m: f'<span style="color:{color}">{m.group(1)}</span>', t)
    words = word if isinstance(word, list) else ([word] if word else [])
    for w in words:
        w = esc(w)
        if w and w in t and f">{w}<" not in t:
            t = t.replace(w, f'<span style="color:{color}">{w}</span>', 1)
    return t


def lines(v):
    return v if isinstance(v, list) else [v]


def char_svg(face, th, closing=False):
    name = "closing" if closing else FACES.get(face, "happy")
    s = (TPL / f"char_{name}.svg").read_text()
    if not closing:
        s = s.replace('fill="#FFFFFF"', f'fill="{th["ink"]}"').replace('stroke="#FFFFFF"', f'stroke="{th["ink"]}"')
        s = s.replace('stroke="#FF5233"', f'stroke="{th["spark"]}"')
        if th.get("body"):
            s = s.replace('fill="#FF5233"', f'fill="{th["body"]}"')
    else:
        s = s.replace('stroke="#FF5233"', f'stroke="{th["accent"]}"')
    return s


# ---------------------------------------------------------------- 카드 HTML
def header(n, total, th, light=True):
    bell = BELL.format(s=36, c=th["logo"] if th["logo"] != "#FFFFFF" else th["accent"])
    return (f'<div class="hdr"><div class="brand">{bell}<span>줍줍알람</span></div>'
            f'<span class="pg">{n} / {total}</span></div>')


def note_html(card):
    note = card.get("note")
    return f'<div class="note">{esc(note)}</div>' if note else ""


def cover(card, th, n, total):
    chips = card.get("chips") or []
    chip_html = ""
    for i, c in enumerate(chips[:2]):
        cls = "chip" if i == 0 else "chip2"
        chip_html += f'<span class="{cls}">{esc(c)}</span>'
    main = "".join(f'<div class="fitw">{hl(l, card.get("highlight"), th["hl"])}</div>'
                   for l in lines(card.get("lines", [])))
    fg = th.get("fg", "#FFFFFF")
    return f'''
<div class="card cover" style="background:{th['bg']};color:{fg}">
  <div class="brand big">{BELL.format(s=44, c=th['logo'])}<span>줍줍알람</span></div>
  <div class="zoom cover-main">
    <div class="chips">{chip_html}</div>
    <div class="cover-title">{main}</div>
    <div class="cover-sub" style="color:{th['sub']}">{esc(card.get('sub'))}</div>
  </div>
  <div class="swipe"><span>넘겨서 확인하기</span>{ARROW.replace('#FFFFFF', fg)}</div>
  <div class="char">{char_svg(card.get('face'), th)}</div>
</div>'''


def info(card, th, n, total):
    rows = card.get("rows") or []
    rows_html = "".join(
        f'<div class="row" style="background:{th["tint"]}"><span class="rl" style="color:{th["accent"]}">{esc(k)}</span>'
        f'<span class="rv">{hl(v, card.get("highlight"), th["accent"])}</span></div>' for k, v in rows)
    para = card.get("text")
    para_html = "".join(f'<p>{hl(p, card.get("highlight"), th["accent"])}</p>' for p in lines(para)) if para else ""
    title = "".join(f"<div>{hl(t, card.get('title_highlight'), th['accent'])}</div>" for t in lines(card.get("title", "")))
    return f'''
<div class="card light" style="background:#FFFFFF">
  {header(n, total, th)}
  <div class="zoom body">
    <div class="eyebrow" style="color:{th['accent']}">{esc(card.get('eyebrow'))}</div>
    <div class="title">{title}</div>
    <div class="rows">{rows_html}</div>
    {f'<div class="para">{para_html}</div>' if para_html else ''}
  </div>
  {note_html(card)}
  <div class="handle">@jupjup_alarm</div>
</div>'''


SERIES_CHIP = {"줍줍알람": ("#FF5233", "#FFFFFF"), "강남로또": ("#C9A24A", "#121212"), "내집마련": ("#1E4FD8", "#FFFFFF"),
               "임대알람": ("#0E5C4A", "#FFFFFF"), "주거꿀팁": ("#4B2A8C", "#FFFFFF")}


def week(card, th, n, total):
    """주간 일정 목록: items = [{date, dow, series, name, point}] 최대 4개."""
    items_html = ""
    for it in (card.get("items") or [])[:4]:
        sb, sf = SERIES_CHIP.get(str(it.get("series", "")).strip("[]"), ("#0F1E3D", "#FFFFFF"))
        items_html += (
            f'<div class="witem"><div class="wdate"><span class="wd">{esc(it.get("date"))}</span>'
            f'<span class="ww">{esc(it.get("dow"))}</span></div>'
            f'<div class="wtxt"><span class="wchip" style="background:{sb};color:{sf}">{esc(str(it.get("series", "")).strip("[]"))}</span>'
            f'<span class="wname">{esc(it.get("name"))}</span>'
            f'<span class="wpoint">{esc(it.get("point"))}</span></div></div>')
    return f'''
<div class="card light" style="background:#FFFFFF">
  {header(n, total, th)}
  <div class="zoom body wk">
    <div class="eyebrow" style="color:{th['accent']}">{esc(card.get('eyebrow') or '이번 주 일정')}</div>
    <div class="title nowrap">{esc(card.get('title'))}</div>
    <div class="witems">{items_html}</div>
  </div>
  {note_html(card)}
  <div class="handle">@jupjup_alarm</div>
</div>'''


def check(card, th, n, total):
    items = card.get("items") or []
    items_html = ""
    for i, it in enumerate(items[:3], 1):
        bold, desc = (it + [""])[:2] if isinstance(it, list) else (it, "")
        items_html += (f'<div class="item"><span class="num" style="color:{th["accent"]}">{i:02d}</span>'
                       f'<div class="itxt"><span class="ib">{esc(bold)}</span>'
                       f'{f"<span class=id>{esc(desc)}</span>" if desc else ""}</div></div>')
    title = "".join(f"<div>{esc(t)}</div>" for t in lines(card.get("title", "")))
    return f'''
<div class="card light" style="background:#FFFFFF">
  {header(n, total, th)}
  <div class="zoom body">
    <div class="eyebrow" style="color:{th['accent']}">{esc(card.get('eyebrow') or '신청 전 체크')}</div>
    <div class="title">{title}</div>
    <div class="items">{items_html}</div>
  </div>
  {note_html(card)}
  <div class="handle">@jupjup_alarm</div>
</div>'''


def closing(card, th, n, total):
    ls = "".join(f'<div class="fitw">{hl(l, card.get("highlight"), th["accent"])}</div>'
                 for l in lines(card.get("lines") or ["저장해두고", "일정 놓치지 마세요"]))
    return f'''
<div class="card light closing" style="background:{th['soft']}">
  {header(n, total, th)}
  <div class="char-c">{char_svg(None, th, closing=True)}</div>
  <div class="zoom close-title">{ls}</div>
  <div class="btns">
    <div class="btn" style="background:{th['btn']}">{FOLLOW}<span>팔로우</span></div>
    <div class="btn ghost" style="border-color:{th['btn']};color:{th['btn']}">{SAVE.format(c=th['btn'])}<span>저장하기</span></div>
  </div>
  <div class="disc">{esc(card.get('disclaimer') or '정보 제공 목적이며 투자 권유가 아닙니다.\n신청 전 입주자모집공고 원문을 꼭 확인하세요.')}</div>
</div>'''


BUILDERS = {"cover": cover, "info": info, "check": check, "closing": closing, "week": week}

CSS = """
@font-face{font-family:'Black Han Sans';src:url('FONTDIR/BlackHanSans-Regular.ttf')}
@font-face{font-family:'Noto Sans KR';src:url('FONTDIR/NotoSansKR-VF.ttf');font-weight:100 900}
*{box-sizing:border-box;margin:0}
body{margin:0;width:1080px;height:1350px;overflow:hidden}
.card{width:1080px;height:1350px;padding:80px;display:flex;flex-direction:column;position:relative;overflow:hidden;
 font-family:'Noto Sans KR',sans-serif;color:#0F1E3D;word-break:keep-all;overflow-wrap:break-word}
.hdr{display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
.brand{display:flex;align-items:center;gap:12px;font-size:28px;font-weight:700}
.brand.big{gap:14px;font-size:32px}
.pg{font-size:28px;font-weight:700;color:#5B6472}
.cover-main{display:flex;flex-direction:column;gap:36px;margin-top:200px;transform-origin:left top}
.chips{display:flex;gap:16px;flex-wrap:wrap}
.chip{font-size:36px;font-weight:900;padding:10px 26px;border-radius:12px;background:var(--chip-bg);color:var(--chip-fg)}
.chip2{font-size:36px;font-weight:700;padding:7px 23px;border-radius:12px;border:3px solid var(--outline);color:var(--chip2-fg,#FFFFFF)}
.cover-title{font-family:'Black Han Sans',sans-serif;font-size:150px;line-height:1.12;letter-spacing:-2px}
.cover-title .fitw{white-space:nowrap}
.cover-sub{font-size:42px;font-weight:500;max-width:920px}
.swipe{position:absolute;left:80px;bottom:80px;display:flex;align-items:center;gap:12px;font-size:32px;font-weight:700}
.char{position:absolute;right:50px;bottom:40px;width:340px;height:340px}
.body{display:flex;flex-direction:column;margin-top:110px;transform-origin:left top}
.eyebrow{font-size:36px;font-weight:700}
.title{font-family:'Black Han Sans',sans-serif;font-size:96px;line-height:1.15;margin-top:28px}
.rows{display:flex;flex-direction:column;gap:20px;margin-top:72px}
.row{display:flex;align-items:center;gap:32px;border-radius:28px;padding:36px 48px}
.rl{width:200px;flex-shrink:0;font-size:36px;font-weight:700}
.rv{font-size:44px;font-weight:900;line-height:1.3;white-space:pre-line}
.para{margin-top:40px;display:flex;flex-direction:column;gap:18px}
.para p{font-size:38px;font-weight:500;line-height:1.5;color:#0F1E3D}
.items{display:flex;flex-direction:column;gap:24px;margin-top:80px}
.item{display:flex;align-items:flex-start;gap:28px;border:3px solid #0F1E3D;border-radius:28px;padding:40px 44px}
.num{font-family:'Black Han Sans',sans-serif;font-size:56px;line-height:1}
.itxt{display:flex;flex-direction:column;gap:8px}
.ib{font-size:44px;font-weight:900;line-height:1.3}
.id{font-size:34px;font-weight:500;color:#5B6472;line-height:1.4}
.note{margin-top:auto;font-size:25px;font-weight:500;color:#5B6472;padding-top:24px}
.handle{font-size:26px;font-weight:500;color:#5B6472;margin-top:auto;padding-top:16px}
.note+.handle{margin-top:12px;padding-top:0}
.closing{align-items:center}
.closing .hdr{align-self:stretch}
.char-c{width:440px;height:440px;margin-top:60px;flex-shrink:0}
.close-title{font-family:'Black Han Sans',sans-serif;font-size:92px;line-height:1.2;text-align:center;margin-top:30px;transform-origin:center top}
.close-title .fitw{white-space:nowrap}
.btns{display:flex;gap:24px;margin-top:56px}
.btn{display:flex;align-items:center;gap:14px;border-radius:999px;padding:24px 44px;font-size:38px;font-weight:900;color:#FFFFFF}
.btn.ghost{background:#FFFFFF;border:3px solid;padding:21px 44px}
.wk{margin-top:80px}
.title.nowrap{white-space:nowrap;margin-top:16px}
.witems{display:flex;flex-direction:column;gap:18px;margin-top:56px}
.witem{display:flex;align-items:center;gap:32px;background:#F2F4F7;border-radius:24px;padding:30px 36px}
.wdate{width:168px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;gap:2px;background:#0F1E3D;color:#FFFFFF;border-radius:18px;padding:16px 0}
.wd{font-size:44px;font-weight:900;line-height:1.1;white-space:nowrap}
.ww{font-size:28px;font-weight:700}
.wtxt{display:flex;flex-direction:column;gap:8px}
.wchip{align-self:flex-start;font-size:26px;font-weight:900;padding:4px 16px;border-radius:8px}
.wname{font-size:40px;font-weight:900;line-height:1.25}
.wpoint{font-size:30px;font-weight:500;color:#5B6472;line-height:1.35}
.disc{margin-top:auto;font-size:24px;font-weight:500;color:#5B6472;text-align:center;line-height:1.5;white-space:pre-line}
"""

# 넘침 자동 맞춤: .zoom 블록을 줄이고, 한 줄 고정(.fitw)은 폭에 맞게 줄임
FIT_JS = """
() => {
  const card = document.querySelector('.card');
  const warn = [];
  document.querySelectorAll('.fitw').forEach(el => {
    let fs = parseFloat(getComputedStyle(el).fontSize), n = 0;
    const max = el.parentElement.getBoundingClientRect().width || 920;
    while (el.scrollWidth > max + 1 && n < 40) { fs *= 0.97; el.style.fontSize = fs + 'px'; n++; }
  });
  const zoomEl = document.querySelector('.zoom');
  let z = 1;
  const over = () => card.scrollHeight > card.clientHeight + 1 ||
    [...card.querySelectorAll('.handle,.disc,.note')].some(e => e.getBoundingClientRect().bottom > 1350 - 40);
  while (zoomEl && over() && z > 0.62) { z -= 0.03; zoomEl.style.zoom = z; }
  if (z < 1) warn.push('zoom ' + z.toFixed(2));
  if (over()) warn.push('OVERFLOW');
  const cov = document.querySelector('.cover .char');
  if (cov) {  // 표지 글자가 캐릭터와 겹치는지
    const c = cov.getBoundingClientRect();
    const t = document.querySelector('.cover-sub').getBoundingClientRect();
    if (t.bottom > c.top + 30 && t.right > c.left + 30) warn.push('cover text overlaps character');
  }
  return warn;
}
"""


def page_html(body, th, font_dir):
    css = CSS.replace("FONTDIR", font_dir)
    vars_ = f":root{{--chip-bg:{th['chip_bg']};--chip-fg:{th['chip_fg']};--outline:{th['outline']};--chip2-fg:{th.get('chip2_fg', '#FFFFFF')}}}"
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{css}{vars_}</style></head><body>{body}</body></html>'


def dc_html(body, title):
    """Claude Design 캔버스 아트보드 파일 (폰트는 구글 폰트)."""
    css = CSS.split("\n", 3)[3]  # @font-face 두 줄 제외
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{esc(title)}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&amp;family=Noto+Sans+KR:wght@500;700;900&amp;display=swap">
<style>{css}</style>
</helmet>
{body}
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":1080,"height":1350}}}}'>
class Component extends DCLogic {{
  renderVals() {{ return {{}}; }}
}}
</script>
</body>
</html>
'''


def render(spec_path):
    from playwright.sync_api import sync_playwright
    from PIL import Image

    spec = json.loads(Path(spec_path).read_text())
    series = spec.get("series", "줍줍알람").strip("[]")
    th = THEMES.get(series, THEMES["줍줍알람"])
    slug = spec["slug"]
    cards = spec["cards"]
    total = len(cards)
    out = ROOT / "cards" / slug
    (out / "dc").mkdir(parents=True, exist_ok=True)
    for old in out.glob("[0-9][0-9].jpg"):
        old.unlink()

    warnings, urls, boards = {}, [], []
    font_dir = FONTS.as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for i, card in enumerate(cards, 1):
            kind = card.get("type", "info")
            body = BUILDERS[kind](card, th, i, total)
            vars_ = f'<div style="--chip-bg:{th["chip_bg"]};--chip-fg:{th["chip_fg"]};--outline:{th["outline"]};--chip2-fg:{th.get("chip2_fg", "#FFFFFF")};display:contents">{body}</div>'
            tmp = out / f"_tmp_{i:02d}.html"
            tmp.write_text(page_html(body, th, font_dir))
            page.goto(tmp.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(150)
            w = page.evaluate(FIT_JS)
            if w:
                warnings[f"{i:02d}"] = w
            jpg = out / f"{i:02d}.jpg"
            page.screenshot(path=str(jpg), type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": W, "height": H})
            tmp.unlink()
            urls.append(f"{RAW_BASE}/cards/{slug}/{i:02d}.jpg")
            title = f"{spec.get('title', slug)} {i}/{total}"
            (out / "dc" / f"{slug}-{i:02d}.dc.html").write_text(dc_html(vars_, title))
            boards.append({"file": f"{slug}-{i:02d}.dc.html", "title": title})
        browser.close()

    # 미리보기 (가로 한 줄, 1/4 크기)
    ims = [Image.open(out / f"{i:02d}.jpg") for i in range(1, total + 1)]
    tw, tht = W // 4, H // 4
    sheet = Image.new("RGB", (tw * total + 12 * (total + 1), tht + 24), "#DDDDDD")
    for k, im in enumerate(ims):
        sheet.paste(im.resize((tw, tht)), (12 + k * (tw + 12), 12))
    sheet.save(out / "preview.jpg", quality=85)

    manifest = {"slug": slug, "title": spec.get("title"), "series": series, "count": total,
                "urls": urls, "warnings": warnings, "boards": boards}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({"slug": slug, "warnings": warnings}, ensure_ascii=False))
    print("\n".join(urls))
    return manifest


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for sp in sys.argv[1:]:
        render(sp)
