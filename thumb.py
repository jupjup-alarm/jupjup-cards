"""유튜브 쇼츠 썸네일 (1080×1920) — 2026-11-02, 사용자 피드백 "썸네일이 너무 구려서".

릴스 첫 프레임(cover.jpg)은 영상용이라 글자가 작고 빈 공간이 많다. 쇼츠 목록·검색에서
작게 보여도 읽히도록, 사진을 꽉 채우고 큰 글자 2줄을 가운데(정사각 안전 영역)에 둔다.

사용:  python3 thumb.py thumbs/<slug>.json   →  reels/<slug>/<slug>_thumb.jpg 덮어씀
원고:
{
  "slug": "2026-10-27-gyeyang-kaive-reel",
  "photo": "photos/mood/….jpg",          # 꽉 채울 사진 (저장소 경로)
  "photo_pos": "center 40%",             # 선택
  "credit": "이미지: LH 제공 조감도 · 실제와 다를 수 있음",   # 조감도일 때만
  "chip": "내집마련",                     # 시리즈 태그
  "badge": "11/4 마감",                   # 빨간 띠 (마감·일정·결과)
  "basis": "계양신도시 카이브 유보라 1,110세대",   # 근거 한 줄 (작게)
  "lines": ["3기 신도시", "국평 7억대"]     # 큰 글자 2줄, 둘째 줄은 노란색
}
"""
import base64, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unit(s):
    """Black Han Sans에 없는 ㎡ 같은 기호는 굵은 Noto로 (가늘게 떨어지지 않게)."""
    return esc(s).replace("㎡", '<span class="u">㎡</span>')


def uri(p):
    p = ROOT / p
    mime = {".png": "image/png", ".webp": "image/webp"}.get(p.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def html(d):
    fd = FONTS.as_uri()
    l1, l2 = (d["lines"] + [""])[:2]
    credit = f'<div class="credit">{esc(d["credit"])}</div>' if d.get("credit") else ""
    badge = f'<span class="badge">{esc(d["badge"])}</span>' if d.get("badge") else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'BH';src:url('{fd}/Pretendard-Black.otf')}}
@font-face{{font-family:'NS';src:url('{fd}/Pretendard-Medium.otf');font-weight:100 500}}
@font-face{{font-family:'NS';src:url('{fd}/Pretendard-Bold.otf');font-weight:600 700}}
@font-face{{font-family:'NS';src:url('{fd}/Pretendard-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'NS';src:url('{fd}/Pretendard-Black.otf');font-weight:900}}
html,body{{margin:0;width:1080px;height:1920px;overflow:hidden;background:#000;word-break:keep-all}}
.ph{{position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover;object-position:{d.get('photo_pos','center 45%')};
  filter:saturate(1.15) contrast(1.05)}}
.sh{{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(0,0,0,.55) 0%,rgba(0,0,0,.05) 18%,rgba(0,0,0,.15) 30%,rgba(0,0,0,.72) 44%,
  rgba(0,0,0,.78) 66%,rgba(0,0,0,.25) 82%,rgba(0,0,0,.55) 100%)}}
.brand{{position:absolute;top:120px;left:0;right:0;text-align:center;font:800 40px 'NS';color:#fff;letter-spacing:2px;opacity:.95}}
.brand b{{color:#FFD43B}}
.box{{position:absolute;left:60px;right:60px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;align-items:center;text-align:center;gap:26px}}
.tags{{display:flex;gap:16px;align-items:center}}
.chip{{font:900 44px 'NS';color:#111;background:#fff;padding:10px 26px;border-radius:14px}}
.badge{{font:900 44px 'NS';color:#fff;background:#FF3B30;padding:10px 26px;border-radius:14px}}
.basis{{font:700 46px 'NS';color:rgba(255,255,255,.92);line-height:1.3;white-space:nowrap}}
.l{{font-family:'BH';line-height:1.1;letter-spacing:-6px;white-space:nowrap;
  text-shadow:0 6px 0 rgba(0,0,0,.55),0 0 40px rgba(0,0,0,.6)}}
.l1{{color:#fff;font-size:190px}}
.l2{{color:#FFD43B;font-size:200px}}
.u{{font-family:'NS';font-weight:900;font-size:.8em;letter-spacing:0}}
.credit{{position:absolute;bottom:90px;left:0;right:0;text-align:center;font:500 28px 'NS';color:rgba(255,255,255,.8)}}
</style></head><body>
<img class="ph" src="{uri(d['photo'])}">
<div class="sh"></div>
<div class="brand">🔔 <b>줍줍</b>알람</div>
<div class="box">
  <div class="tags"><span class="chip">{esc(d.get('chip'))}</span>{badge}</div>
  <div class="basis">{esc(d.get('basis'))}</div>
  <div class="l l1">{unit(l1)}</div>
  <div class="l l2">{unit(l2)}</div>
</div>
{credit}
<script>
for (const el of document.querySelectorAll('.l,.basis')) {{
  let fs = parseFloat(getComputedStyle(el).fontSize);
  while (el.scrollWidth > 960 && fs > 30) {{ fs -= 4; el.style.fontSize = fs + 'px'; }}
}}
</script></body></html>"""


def make(items):
    """items: 원고 dict 목록 → 썸네일 파일 경로 목록."""
    outs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        for d in items:
            out = ROOT / "reels" / d["slug"]
            out.mkdir(parents=True, exist_ok=True)
            tmp = out / "_thumb.html"   # 글꼴(file://)을 읽으려면 파일로 열어야 함
            tmp.write_text(html(d))
            pg.goto(tmp.as_uri(), wait_until="load")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            tmp.unlink()
            f = out / f"{d['slug']}_thumb.jpg"
            pg.screenshot(path=str(f), type="jpeg", quality=90)
            outs.append(f)
        b.close()
    return outs


def from_reel_spec(spec):
    """릴스 원고(hook 장면)에서 썸네일 원고를 만든다. spec["thumb"]가 있으면 그 값이 우선."""
    hook = next((s for s in spec["scenes"] if s["type"] == "hook"), None)
    if not hook and spec.get("style") == "story" and spec["scenes"]:   # 이야기형(2026-11-05): 첫 장면 첫 컷 + thumb.lines
        s0 = spec["scenes"][0]
        sh = (s0.get("shots") or [None])[0]
        sh = {"img": sh} if isinstance(sh, str) else (sh or {})
        photo = sh.get("img")
        if not photo or not (ROOT / photo).exists():
            return None
        d = {"slug": spec["slug"], "photo": photo, "photo_pos": sh.get("pos") or "center 45%", "credit": sh.get("credit") or "",
             "chip": spec.get("series", ""), "badge": "", "basis": "", "lines": [s0.get("word") or ""]}
        d.update(spec.get("thumb") or {})
        return d
    if not hook:
        return None
    photo = hook.get("photo") or (hook.get("bg") if str(hook.get("bg", "")).startswith("photos/") else None)
    if not photo:
        photo = next((s["bg"] for s in spec["scenes"] if str(s.get("bg", "")).startswith("photos/")), None)
    if not photo or not (ROOT / photo).exists():
        return None
    n = str((hook.get("count") or {}).get("to", ""))
    lines = [l.replace("{n}", n) for l in hook.get("lines", [])][:2]
    chips = hook.get("chips") or []
    d = {"slug": spec["slug"], "photo": photo, "photo_pos": hook.get("photo_pos") or "center 45%",
         "credit": hook.get("photo_credit") or "", "chip": chips[0] if chips else spec.get("series", ""),
         "badge": chips[1] if len(chips) > 1 else "", "basis": hook.get("basis") or hook.get("sub") or "",
         "lines": lines}
    d.update(spec.get("thumb") or {})
    return d


def main(paths):
    for f in make([json.loads(Path(p).read_text()) for p in paths]):
        print(f.relative_to(ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])
