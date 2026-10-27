#!/usr/bin/env python3
"""두아이 살림노트(@2kids_note) 카드뉴스 렌더러.

카드 원고(JSON) → 1080×1350 JPG (인스타 4:5) + 미리보기 + 공개 주소 목록

사용법:
    python3 2kids/render.py 2kids/specs/<slug>.json

결과:
    2kids/cards/<slug>/01.jpg … NN.jpg
    2kids/cards/<slug>/preview.jpg
    2kids/cards/<slug>/manifest.json
표준출력 첫 줄: {"slug", "warnings"} / 그 뒤: 공개 이미지 주소 (줄바꿈 구분 → 발행계획 U열에 그대로)
"""
import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OWNER_REPO = "jupjup-alarm/jupjup-cards"
BRANCH = os.environ.get("CARDS_BRANCH", "main")
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER_REPO}/{BRANCH}"
W, H = 1080, 1350

PAPER, INK, YEL, SAGE, LINE, CORAL = "#FBF7EF", "#2B3040", "#F5C84C", "#9DBB97", "#E6DFD1", "#E8735F"
MUTED, SOFT = "#6B6A66", "#F3EDE1"

DISCLOSURE_SHORT = "광고 · 링크 구매 시 수수료를 받아요"
DISCLOSURE_FULL = {
    "toss": "이 콘텐츠는 토스쇼핑 쉐어링크 활동의 일환으로,\n링크를 통한 구매가 발생하면 일정 수수료를 지급받습니다.",
    "coupang": "이 포스팅은 쿠팡 파트너스 활동의 일환으로,\n이에 따른 일정액의 수수료를 제공받습니다.",
}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def mark(text, words=None, cls="mk"):
    """**굵게** 또는 highlight 단어를 형광펜으로."""
    t = esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", lambda m: f'<span class="{cls}">{m.group(1)}</span>', t)
    for w in (words if isinstance(words, list) else ([words] if words else [])):
        w = esc(w)
        if w and w in t and f'">{w}</span>' not in t:
            t = t.replace(w, f'<span class="{cls}">{w}</span>', 1)
    return t


def L(v):
    return v if isinstance(v, list) else ([v] if v else [])


# ---------------------------------------------------------------- 그림 요소
def twins_svg(width=420, bg=None):
    """프로필의 쌍둥이 뒷모습(1번 리본, 2번 방울)."""
    b = f'<rect x="-20" y="-20" width="240" height="200" fill="{bg}"/>' if bg else ""
    def bow(x, y):
        return (f'<path d="M{x-10} {y-7}L{x-10} {y+7}L{x} {y}Z" fill="{CORAL}"/>'
                f'<path d="M{x+10} {y-7}L{x+10} {y+7}L{x} {y}Z" fill="{CORAL}"/><circle cx="{x}" cy="{y}" r="3.2" fill="{CORAL}"/>')
    def pom(x, y):
        return f'<circle cx="{x-4.6}" cy="{y}" r="4.8" fill="{CORAL}"/><circle cx="{x+4.6}" cy="{y}" r="4.8" fill="{CORAL}"/>'
    body = (f'<path d="M18 160 Q18 132 60 132 Q102 132 102 170L18 170Z" fill="{PAPER}"/>'
            f'<path d="M98 160 Q98 132 140 132 Q182 132 182 170L98 170Z" fill="{PAPER}"/>'
            + "".join(f'<circle cx="{x}" cy="94" r="11.5" fill="{INK}"/>' for x in (30, 90, 110, 170))
            + f'<circle cx="60" cy="104" r="30" fill="{INK}"/><circle cx="140" cy="104" r="30" fill="{INK}"/>'
            + bow(38, 80) + bow(82, 80) + pom(118, 80) + pom(162, 80)
            + f'<text x="60" y="158" text-anchor="middle" font-family="Noto Sans KR" font-weight="900" font-size="26" fill="{INK}">1</text>'
            + f'<text x="140" y="158" text-anchor="middle" font-family="Noto Sans KR" font-weight="900" font-size="26" fill="{INK}">2</text>')
    h = width * 100 / 200
    return f'<svg width="{width}" height="{h:.0f}" viewBox="0 66 200 100" aria-hidden="true">{b}{body}</svg>'


def heads_icon(size=40):
    return (f'<svg width="{size}" height="{size*0.62:.0f}" viewBox="0 0 64 40" aria-hidden="true">'
            f'<circle cx="20" cy="22" r="14" fill="{INK}"/><circle cx="44" cy="22" r="14" fill="{INK}"/>'
            f'<circle cx="8" cy="14" r="6" fill="{INK}"/><circle cx="56" cy="14" r="6" fill="{INK}"/>'
            f'<path d="M12 8l-5-4v8zM12 8l5-4v8z" fill="{CORAL}"/><circle cx="50" cy="7" r="3" fill="{CORAL}"/><circle cx="56" cy="7" r="3" fill="{CORAL}"/></svg>')


ICONS = {  # 24 그리드 선 아이콘 (직접 그림)
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.5"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/>',
    "calc": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h2M14 12h2M8 16h2M14 16h2"/>',
    "check": '<path d="M5 12l4 4 10-10"/>',
    "bell": '<path d="M6 16v-5a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    "story": '<circle cx="12" cy="12" r="9" stroke-dasharray="3 2.4"/><path d="M12 8v8M8 12h8"/>',
    "bookmark": '<path d="M6 3h12v18l-6-4-6 4z"/>',
    "send": '<path d="M21 3 3 10.5l7 2.5 2.5 7z"/><path d="M21 3 10 13"/>',
    "chat": '<path d="M4 5h16v11H9l-5 4z"/>',
    "cart": '<path d="M3 4h3l2 11h11l2-8H7"/><circle cx="10" cy="19" r="1.6"/><circle cx="17" cy="19" r="1.6"/>',
}


def icon(name, size=36, color=INK, sw=2.2):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS.get(name, "")}</svg>')


def rings(n=13):
    return '<div class="rings">' + '<i></i>' * n + '</div>'


def header(n, total, dark=False):
    return (f'<div class="hdr{" dark" if dark else ""}"><div class="brand">{heads_icon(46)}<span>두아이 살림노트</span></div>'
            f'<span class="pg">{n} / {total}</span></div>')


def footer(note=None):
    nt = f'<div class="note">{esc(note)}</div>' if note else ""
    return f'<div class="foot">{nt}<div class="handle">@2kids_note</div></div>'


def tape(cls=""):
    return f'<div class="tape {cls}"></div>'


def is_ad(spec):
    """상품(제휴 링크)을 다루는 카드뉴스만 광고 표시. 원고에 "ad": true가 있어야 함 (정보 카드는 생략)."""
    return bool(spec.get("ad"))


# ---------------------------------------------------------------- 카드 종류
def c_cover_full(c, n, total, spec):
    """꽉 찬 실사 표지 (2026-10-27, @donnamu_grow 참고 — 첫 장은 실사로 피드에서 눈에 띄게).
    photo: 2kids/photos/mood/…jpg (Pixabay 무료·출처 표기 불필요) · photo_pos: "center 40%" 처럼 위치 조정
    · photo_lift: 200 처럼 숫자(px)를 주면 사진을 키워 위로 올림 (얼굴이 아래 글자에 가릴 때)."""
    src = c.get("photo") or ""
    p = Path(src) if Path(src).is_absolute() else ROOT / src
    chips = "".join(f'<span class="fchip{" c2" if i else ""}">{esc(x)}</span>' for i, x in enumerate(L(c.get("chips"))[:2]))
    main = "".join(f'<div class="fitw">{mark(x, c.get("highlight"), "fmk")}</div>' for x in L(c.get("lines")))
    sub = f'<div class="fsub">{esc(c.get("sub"))}</div>' if c.get("sub") else ""
    pos = esc(c.get("photo_pos") or "center 40%")
    lift = int(c.get("photo_lift") or 0)   # 사진을 위로 올리기(px): 얼굴이 아래 글자에 가릴 때 160~260
    lift_css = f";top:-{lift}px;height:{1350 + lift}px" if lift else ""
    return f'''<div class="card fullphoto">
  <img class="fbg" src="{p.as_uri()}" style="object-position:{pos}{lift_css}">
  <div class="fshade"></div>
  <div class="fhead">{header(n, total)}</div>
  {f'<div class="disc-top fdisc">{icon("tag", 30, "#FFFFFF")}<span>{DISCLOSURE_SHORT}</span></div>' if is_ad(spec) else ""}
  <div class="zoom fbody">
    <div class="chips">{chips}</div>
    <div class="ftitle">{main}</div>
    {sub}
    <div class="fhandle">@2kids_note</div>
  </div>
</div>'''


def c_cover(c, n, total, spec):
    """표지. theme: deal(잉크 배경·특가) | note(종이 배경). 대가성 문구 이미지 안에 고정.
    "photo_style": "full" + "photo" → 꽉 찬 실사 표지 (c_cover_full). 사진 파일이 없으면 기본 표지로."""
    if c.get("photo_style") == "full" and c.get("photo"):
        src = c["photo"]
        if (Path(src) if Path(src).is_absolute() else ROOT / src).exists():
            return c_cover_full(c, n, total, spec)
        WARN.append("PHOTO: 파일 없음 " + src + " → 기본 표지")
    theme = c.get("theme") or ("deal" if spec.get("series") == "오늘 특가" else "note")
    dark = theme == "deal"
    chips = "".join(f'<span class="chip{" c2" if i else ""}">{esc(x)}</span>' for i, x in enumerate(L(c.get("chips"))[:2]))
    main = "".join(f'<div class="fitw">{mark(x, c.get("highlight"))}</div>' for x in L(c.get("lines")))
    sub = f'<div class="csub">{mark(c.get("sub"), None, "mk2")}</div>' if c.get("sub") else ""
    badge = ""
    if c.get("badge"):
        bl = "".join(f"<div>{esc(x)}</div>" for x in L(c["badge"]))
        badge = f'<div class="badge">{bl}</div>'
    hand = f'<div class="hand cover-hand">{esc(c["hand"])}</div>' if c.get("hand") else ""
    return f'''<div class="card cover {'dark' if dark else 'paper'}">
  {header(n, total, dark)}
  {f'<div class="disc-top">{icon("tag", 30, INK if not dark else YEL)}<span>{DISCLOSURE_SHORT}</span></div>' if is_ad(spec) else ""}
  <div class="zoom cbody">
    <div class="chips">{chips}</div>
    <div class="ctitle">{main}</div>
    {sub}
    {hand}
  </div>
  {badge}
  <div class="band">{twins_svg(560)}</div>
</div>'''


def c_deal(c, n, total, spec):
    """특가 상세: 제품명, 정가/할인가/할인율, 단가, 마감."""
    num = esc(c.get("num") or f"{n-1:02d}")
    tags = "".join(f'<span class="tg">{esc(t)}</span>' for t in L(c.get("tags")))
    pct = f'<div class="stamp"><b>{esc(c["percent"])}</b><span>할인</span></div>' if c.get("percent") else ""
    orig = f'<div class="orig">{esc(c["original"])}</div>' if c.get("original") else ""
    unit = (f'<div class="unit">{icon("calc", 34)}<span>{mark(c["unit"])}</span></div>') if c.get("unit") else ""
    dl = (f'<div class="deadline">{icon("clock", 34, PAPER)}<span>{esc(c["deadline"])}</span></div>') if c.get("deadline") else ""
    desc = "".join(f'<li>{mark(x)}</li>' for x in L(c.get("points")))
    desc = f'<ul class="pts">{desc}</ul>' if desc else ""
    return f'''<div class="card inner">{rings()}
  <div class="col">
    {header(n, total)}
    <div class="zoom">
      <div class="dhead"><span class="num">{num}</span><div class="dname">{mark(c.get("name"))}</div></div>
      <div class="tgs">{tags}</div>
      <div class="pricebox">{tape()}
        {orig}
        <div class="sale"><span class="mkb">{esc(c.get("price"))}</span></div>
        {pct}
        {unit}
      </div>
      {dl}
      {desc}
    </div>
    {footer(c.get("note"))}
  </div>
</div>'''


def c_calc(c, n, total, spec):
    """두 배 계산기: 1명 vs 쌍둥이 막대 비교 + 결과."""
    rows = c.get("rows") or []
    mx = max([float(r.get("amount") or 0) for r in rows] + [1])
    bars = ""
    for i, r in enumerate(rows):
        pct = max(14, float(r.get("amount") or 0) / mx * 100)
        bars += (f'<div class="brow"><div class="blabel">{esc(r.get("label"))}</div>'
                 f'<div class="btrack"><div class="bar b{i % 3}" style="width:{pct:.0f}%"><span>{esc(r.get("value"))}</span></div></div></div>')
    res = f'<div class="result">{tape("t2")}<div class="rl">{mark(c.get("result"))}</div></div>' if c.get("result") else ""
    hand = f'<div class="hand">{esc(c["hand"])}</div>' if c.get("hand") else ""
    title = "".join(f"<div>{mark(x)}</div>" for x in L(c.get("title")))
    return f'''<div class="card inner">{rings()}
  <div class="col">
    {header(n, total)}
    <div class="zoom">
      <div class="eyebrow">{icon("calc", 34, INK)}<span>{esc(c.get("eyebrow") or "두 배 계산기")}</span></div>
      <div class="title">{title}</div>
      <div class="bars">{bars}</div>
      {res}
      {hand}
    </div>
    {footer(c.get("note"))}
  </div>
</div>'''


def c_list(c, n, total, spec):
    """숫자 리스트 (최대 4개)."""
    items = ""
    for i, it in enumerate((c.get("items") or [])[:4], 1):
        it = it if isinstance(it, list) else [it, ""]
        sub = f'<div class="id">{mark(it[1])}</div>' if len(it) > 1 and it[1] else ""
        items += f'<div class="item"><div class="inum">{i}</div><div class="itx"><div class="ib">{mark(it[0])}</div>{sub}</div></div>'
    title = "".join(f"<div>{mark(x)}</div>" for x in L(c.get("title")))
    eb = f'<div class="eyebrow">{icon(c.get("icon") or "box", 34)}<span>{esc(c["eyebrow"])}</span></div>' if c.get("eyebrow") else ""
    return f'''<div class="card inner">{rings()}
  <div class="col">
    {header(n, total)}
    <div class="zoom">{eb}
      <div class="title">{title}</div>
      <div class="items">{items}</div>
    </div>
    {footer(c.get("note"))}
  </div>
</div>'''


def c_compare(c, n, total, spec):
    """비교표: cols(머리줄), rows, best(강조 열 번호, 1부터)."""
    cols = c.get("cols") or []
    best = int(c.get("best") or 0)
    head = "".join(f'<th class="{"best" if j == best else ""}">{esc(x)}</th>' for j, x in enumerate(cols))
    body = ""
    for r in c.get("rows") or []:
        body += "<tr>" + "".join(
            f'<td class="{"best" if j == best else ("rh" if j == 0 else "")}">{mark(x)}</td>' for j, x in enumerate(r)) + "</tr>"
    title = "".join(f"<div>{mark(x)}</div>" for x in L(c.get("title")))
    eb = f'<div class="eyebrow">{icon("tag", 34)}<span>{esc(c.get("eyebrow") or "가격 비교")}</span></div>'
    hand = f'<div class="hand">{esc(c["hand"])}</div>' if c.get("hand") else ""
    return f'''<div class="card inner">{rings()}
  <div class="col">
    {header(n, total)}
    <div class="zoom">{eb}
      <div class="title">{title}</div>
      <table class="cmp"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
      {hand}
    </div>
    {footer(c.get("note"))}
  </div>
</div>'''


def c_info(c, n, total, spec):
    """정보 카드: eyebrow, title, rows [[라벨, 값]] 2~5개, text(선택), note(출처 등)."""
    rows = ""
    for r in (c.get("rows") or [])[:5]:
        r = r if isinstance(r, list) else [r, ""]
        val = esc(r[1]).replace("\\n", "<br>").replace("\n", "<br>")
        val = re.sub(r"\*\*(.+?)\*\*", lambda m: f'<span class="mk">{m.group(1)}</span>', val)
        rows += f'<div class="irow"><div class="ik">{esc(r[0])}</div><div class="iv">{val}</div></div>'
    title = "".join(f"<div>{mark(x)}</div>" for x in L(c.get("title")))
    text = f'<div class="itext">{mark(c.get("text"))}</div>' if c.get("text") else ""
    eb = f'<div class="eyebrow">{icon(c.get("icon") or "bell", 34)}<span>{esc(c.get("eyebrow") or "핵심 정리")}</span></div>'
    return f'''<div class="card inner">{rings()}
  <div class="col">
    {header(n, total)}
    <div class="zoom">{eb}
      <div class="title">{title}</div>
      <div class="ibox">{tape()}{rows}</div>
      {text}
    </div>
    {footer(c.get("note"))}
  </div>
</div>'''


def c_check(c, n, total, spec):
    """구매 팁 체크리스트 (최대 3개) + 포스트잇."""
    items = ""
    for it in (c.get("items") or [])[:3]:
        it = it if isinstance(it, list) else [it, ""]
        sub = f'<div class="id">{mark(it[1])}</div>' if len(it) > 1 and it[1] else ""
        items += f'<div class="ck"><div class="box">{icon("check", 40, INK, 3)}</div><div class="itx"><div class="ib">{mark(it[0])}</div>{sub}</div></div>'
    title = "".join(f"<div>{mark(x)}</div>" for x in L(c.get("title")))
    post = f'<div class="postit">{tape("t3")}{esc(c["postit"])}</div>' if c.get("postit") else ""
    return f'''<div class="card inner">{rings()}
  <div class="col">
    {header(n, total)}
    <div class="zoom">
      <div class="eyebrow">{icon("check", 34)}<span>{esc(c.get("eyebrow") or "우리 집 체크")}</span></div>
      <div class="title">{title}</div>
      <div class="cks">{items}</div>
      {post}
    </div>
    {footer(c.get("note"))}
  </div>
</div>'''


def c_photo(c, n, total, spec):
    """사진은행 실사 1장 + 한 줄 설명. image: 저장소 기준 경로 또는 절대경로 (얼굴 가린 사진만)."""
    src = c.get("image") or ""
    p = Path(src)
    if not p.is_absolute():
        p = (ROOT / src)
    img = f'<img src="{p.as_uri()}">' if p.exists() else '<div class="noimg">사진 없음</div>'
    if not p.exists():
        WARN.append("PHOTO: 파일 없음 " + src)
    badge = f'<span class="tg dark">{esc(c["badge"])}</span>' if c.get("badge") else ""
    return f'''<div class="card inner">{rings()}
  <div class="col">
    {header(n, total)}
    <div class="zoom">
      <div class="dhead"><span class="num">{esc(c.get("num") or f"{n-1:02d}")}</span><div class="dname">{mark(c.get("name"))}</div></div>
      <div class="tgs">{badge}</div>
      <div class="photo">{tape()}{img}</div>
      <div class="pcap">{mark(c.get("text"))}</div>
    </div>
    {footer(c.get("note"))}
  </div>
</div>'''


def c_closing(c, n, total, spec):
    """마무리. 상품 글(ad)이면 링크 위치 안내 + 대가성 문구, 정보 글이면 공유 유도.
    share: 누구에게 보내면 좋은지 한 줄 (예: "어린이집 보내는 친구한테 보내주세요")."""
    lines = "".join(f'<div class="fitw">{mark(x, c.get("highlight"))}</div>' for x in L(c.get("lines") or ["필요할 때", "꺼내 보세요"]))
    btns = (f'<div class="btns"><span class="btn">{icon("bookmark", 38, PAPER)}저장</span>'
            f'<span class="btn">{icon("send", 38, PAPER)}공유</span>'
            f'<span class="btn ghost">{heads_icon(44)}팔로우</span></div>')
    if is_ad(spec):
        where = c.get("where") or "스토리 하이라이트"
        how = {"story": ("story", "링크는 스토리 · 하이라이트에"),
               "dm": ("chat", f'댓글에 “{c.get("keyword", "")}” 남기면 DM으로'),
               "profile": ("bookmark", "링크는 프로필에")}.get(c.get("link", "story"))
        disc = DISCLOSURE_FULL.get(spec.get("platform", "coupang"), DISCLOSURE_FULL["coupang"])
        mid = f'<div class="howto">{icon(how[0], 44, INK)}<span>{esc(how[1])}</span></div><div class="where hand">{esc(where)}</div>'
        tail = f'<div class="disc">{esc(disc)}</div>'
    else:
        share = c.get("share") or "필요한 친구한테 보내주세요"
        mid = f'<div class="howto">{icon("send", 44, INK)}<span>{esc(share)}</span></div>'
        mid += f'<div class="where hand">{esc(c["where"])}</div>' if c.get("where") else ""
        tail = ""
    return f'''<div class="card closing paper">
  {header(n, total)}
  <div class="zoom ccol">
    <div class="ctitle2">{lines}</div>
    {mid}
    {btns}
  </div>
  <div class="band small">{twins_svg(420)}</div>
  {tail}
</div>'''


BUILDERS = {"info": c_info, "cover": c_cover, "deal": c_deal, "calc": c_calc, "list": c_list, "compare": c_compare,
            "check": c_check, "photo": c_photo, "closing": c_closing}
WARN = []

# ---------------------------------------------------------------- 스타일
CSS = """
@font-face{font-family:'Noto Sans KR';src:url('NOTO') format('truetype');font-weight:100 900}
@font-face{font-family:'Hand';src:url('HAND') format('truetype')}
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;overflow:hidden;font-family:'Noto Sans KR',sans-serif;color:#2B3040;word-break:keep-all;-webkit-font-smoothing:antialiased}
.card{width:1080px;height:1350px;position:relative;overflow:hidden;display:flex;flex-direction:column}
.paper,.inner{background-color:#FBF7EF;background-image:radial-gradient(#E3DACA 2px,transparent 2.2px);background-size:40px 40px;background-position:20px 20px}
.dark{background:#2B3040;color:#FBF7EF}
.hdr{display:flex;align-items:center;justify-content:space-between;height:64px}
.brand{display:flex;align-items:center;gap:12px;font-size:28px;font-weight:900;letter-spacing:-0.01em}
.hdr.dark .brand svg circle[fill="#2B3040"]{fill:#FBF7EF}
.pg{font-size:28px;font-weight:700;color:#8A877F;letter-spacing:.04em}
.hdr.dark .pg{color:#C9C3B6}
.mk{background:linear-gradient(transparent 58%,#F5C84C 58%,#F5C84C 92%,transparent 92%);padding:0 4px;margin:0 -4px}
.dark .mk{background:none;color:#F5C84C}
.mk2{color:#2B3040;font-weight:900}
.dark .mk2{color:#F5C84C}
.mkb{background:linear-gradient(transparent 55%,#F5C84C 55%,#F5C84C 94%,transparent 94%);padding:0 10px}
/* 표지 */
.cover{padding:56px 72px 0}
.disc-top{display:flex;align-items:center;gap:10px;align-self:flex-start;margin-top:22px;font-size:26px;font-weight:700;padding:8px 18px 8px 14px;border-radius:12px;background:#FFFFFF;border:2.5px solid #2B3040}
.dark .disc-top{background:transparent;border-color:#F5C84C;color:#F5C84C}
.cbody{margin-top:92px;display:flex;flex-direction:column}
.chips{display:flex;gap:14px}
.chip{font-size:32px;font-weight:900;padding:10px 26px;border-radius:999px;background:#2B3040;color:#F5C84C}
.dark .chip{background:#F5C84C;color:#2B3040}
.chip.c2{background:transparent;color:inherit;border:3px solid currentColor;padding:7px 23px}
.ctitle{margin-top:44px;font-size:132px;font-weight:900;line-height:1.16;letter-spacing:-0.035em}
.fitw{white-space:nowrap}
.csub{margin-top:34px;font-size:44px;font-weight:500;line-height:1.45;color:#4A4D58}
.dark .csub{color:#D9D4C8}
.hand{font-family:'Hand';font-size:54px;line-height:1.25;color:#E8735F;transform:rotate(-2deg);margin-top:28px}
.dark .hand{color:#F2A97E}
.badge{position:absolute;right:60px;bottom:236px;z-index:2;width:250px;height:250px;border-radius:50%;background:#E8735F;color:#FFFFFF;display:flex;flex-direction:column;align-items:center;justify-content:center;transform:rotate(9deg);font-weight:900;line-height:1.12;text-align:center;box-shadow:0 10px 0 rgba(43,48,64,.16)}
.badge div:first-child{font-size:38px}
.badge div:nth-child(2){font-size:58px;letter-spacing:-0.03em}
.badge div:nth-child(3){font-size:30px}
.dark .badge{background:#E8735F;color:#FFFFFF}
.band{position:absolute;left:0;right:0;bottom:0;height:330px;background:#F5C84C;display:flex;justify-content:center;align-items:flex-end;overflow:hidden}
.band svg{display:block;margin-bottom:-2px}
.band.small{height:250px}
/* 꽉 찬 실사 표지 */
.fullphoto{background:#2B3040;color:#FFFFFF;padding:56px 72px 0}
.fbg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0}
.fshade{position:absolute;inset:0;z-index:1;background:linear-gradient(180deg,rgba(20,22,30,.55) 0%,rgba(20,22,30,0) 18%,rgba(20,22,30,0) 38%,rgba(20,22,30,.62) 60%,rgba(20,22,30,.92) 100%)}
.fhead,.fbody,.fdisc{position:relative;z-index:2}
.fhead .brand,.fhead .pg{color:#FFFFFF}
.fhead .brand svg circle[fill="#2B3040"]{fill:#FFFFFF}
.fdisc{background:rgba(20,22,30,.55);border-color:#FFFFFF;color:#FFFFFF}
.fbody{margin-top:auto;padding-bottom:78px;display:flex;flex-direction:column}
.fchip{font-size:30px;font-weight:900;padding:8px 22px;border-radius:10px;background:#9DBB97;color:#2B3040}
.fchip.c2{background:transparent;color:#FFFFFF;border:3px solid #FFFFFF;padding:5px 19px}
.ftitle{margin-top:30px;font-size:104px;font-weight:900;line-height:1.2;letter-spacing:-0.035em;text-shadow:0 4px 24px rgba(0,0,0,.35)}
.fmk{color:#F5C84C}
.fsub{margin-top:26px;font-size:40px;font-weight:700;line-height:1.4;color:#F1ECE2;text-shadow:0 2px 12px rgba(0,0,0,.4)}
.fhandle{margin-top:34px;font-size:28px;font-weight:700;color:rgba(255,255,255,.8)}
/* 속지 */
.inner{flex-direction:row}
.rings{width:88px;flex-shrink:0;border-right:3px solid #E6DFD1;display:flex;flex-direction:column;align-items:center;justify-content:space-around;padding:56px 0;background:#F6F0E4}
.rings i{display:block;width:26px;height:26px;border-radius:50%;border:3.5px solid #2B3040;background:#FFFFFF}
.col{flex:1;padding:52px 68px 46px 60px;display:flex;flex-direction:column;min-width:0}
.zoom{display:flex;flex-direction:column}
.col>.zoom{margin-top:44px}
.eyebrow{display:flex;align-items:center;gap:12px;font-size:32px;font-weight:900;color:#2B3040;align-self:flex-start;background:#9DBB97;padding:8px 20px 8px 14px;border-radius:12px}
.title{margin-top:28px;font-size:76px;font-weight:900;line-height:1.24;letter-spacing:-0.03em}
.dhead{display:flex;align-items:center;gap:26px}
.num{font-size:84px;font-weight:900;line-height:1;color:#E8735F;letter-spacing:-0.04em}
.dname{font-size:58px;font-weight:900;line-height:1.22;letter-spacing:-0.025em;white-space:pre-line}
.tgs{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}
.tg{font-size:28px;font-weight:700;padding:6px 18px;border-radius:10px;background:#FFFFFF;border:2.5px solid #2B3040}
.tg.dark{background:#2B3040;color:#FBF7EF}
.tape{position:absolute;top:-22px;left:50%;width:170px;height:46px;margin-left:-85px;background:rgba(157,187,151,.78);transform:rotate(-3deg)}
.tape.t2{background:rgba(232,115,95,.55);left:auto;right:60px;margin:0;transform:rotate(4deg)}
.tape.t3{background:rgba(255,255,255,.75);width:120px;margin-left:-60px}
.pricebox{position:relative;margin-top:44px;background:#FFFFFF;border:3.5px solid #2B3040;border-radius:30px;padding:46px 48px 40px;box-shadow:10px 12px 0 #2B3040}
.orig{font-size:40px;font-weight:500;color:#8A877F;text-decoration:line-through;text-decoration-thickness:3px}
.sale{font-size:112px;font-weight:900;letter-spacing:-0.04em;line-height:1.15;margin-top:4px;white-space:nowrap}
.stamp{position:absolute;right:40px;top:-46px;width:170px;height:170px;border-radius:50%;background:#E8735F;color:#FFFFFF;display:flex;flex-direction:column;align-items:center;justify-content:center;transform:rotate(10deg);line-height:1}
.stamp b{font-size:60px;font-weight:900;letter-spacing:-0.03em}
.stamp span{font-size:28px;font-weight:700;margin-top:6px}
.unit{display:flex;align-items:center;gap:14px;margin-top:26px;padding-top:26px;border-top:3px dashed #E6DFD1;font-size:40px;font-weight:700}
.deadline{display:flex;align-items:center;gap:14px;align-self:flex-start;margin-top:44px;background:#2B3040;color:#FBF7EF;font-size:36px;font-weight:900;padding:14px 26px;border-radius:16px}
.pts{list-style:none;margin-top:34px;display:flex;flex-direction:column;gap:14px}
.pts li{font-size:36px;font-weight:500;line-height:1.45;padding-left:38px;position:relative}
.pts li:before{content:'';position:absolute;left:4px;top:22px;width:16px;height:16px;border-radius:50%;background:#9DBB97}
.bars{margin-top:52px;display:flex;flex-direction:column;gap:30px}
.brow{display:flex;flex-direction:column;gap:12px}
.blabel{font-size:36px;font-weight:700}
.btrack{background:#EFE8DA;border-radius:18px;height:96px;overflow:hidden}
.bar{height:100%;border-radius:18px;display:flex;align-items:center;justify-content:flex-end;padding:0 26px;font-size:42px;font-weight:900;white-space:nowrap}
.bar.b0{background:#9DBB97}.bar.b1{background:#F5C84C}.bar.b2{background:#E8735F;color:#FFFFFF}
.result{position:relative;margin-top:56px;background:#FFFFFF;border:3.5px solid #2B3040;border-radius:26px;padding:40px 44px;box-shadow:10px 12px 0 #2B3040}
.rl{font-size:50px;font-weight:900;line-height:1.35;letter-spacing:-0.02em}
.items{margin-top:46px;display:flex;flex-direction:column;gap:22px}
.item{display:flex;gap:28px;align-items:flex-start;background:#FFFFFF;border:3px solid #2B3040;border-radius:24px;padding:30px 34px}
.inum{width:72px;height:72px;flex-shrink:0;border-radius:50%;background:#F5C84C;display:flex;align-items:center;justify-content:center;font-size:44px;font-weight:900}
.itx{display:flex;flex-direction:column;gap:8px;min-width:0}
.ib{font-size:44px;font-weight:900;line-height:1.3;letter-spacing:-0.02em}
.id{font-size:33px;font-weight:500;color:#55585F;line-height:1.42}
.cmp{margin-top:48px;width:100%;border-collapse:separate;border-spacing:0;background:#FFFFFF;border:3.5px solid #2B3040;border-radius:26px;overflow:hidden}
.cmp th{font-size:34px;font-weight:900;padding:26px 18px;background:#2B3040;color:#FBF7EF}
.cmp th.best{background:#F5C84C;color:#2B3040}
.cmp td{font-size:38px;font-weight:700;padding:28px 18px;text-align:center;border-top:2.5px solid #E6DFD1}
.cmp td.rh{font-size:32px;color:#55585F;font-weight:700;background:#FBF7EF}
.cmp td.best{background:#FDF4D6;font-weight:900}
.ibox{position:relative;margin-top:48px;background:#FFFFFF;border:3.5px solid #2B3040;border-radius:28px;padding:20px 40px;box-shadow:10px 12px 0 #2B3040}
.irow{display:flex;gap:28px;padding:26px 0;border-top:2.5px dashed #E6DFD1;align-items:flex-start}
.irow:first-child{border-top:none}
.ik{width:190px;flex-shrink:0;font-size:32px;font-weight:700;color:#6B6A66;line-height:1.4;padding-top:4px}
.iv{flex:1;font-size:40px;font-weight:900;line-height:1.38;letter-spacing:-0.02em}
.itext{margin-top:40px;font-size:36px;font-weight:500;line-height:1.5}
.cks{margin-top:48px;display:flex;flex-direction:column;gap:36px}
.ck{display:flex;gap:28px;align-items:flex-start}
.box{width:68px;height:68px;flex-shrink:0;border:4px solid #2B3040;border-radius:14px;background:#FFFFFF;display:flex;align-items:center;justify-content:center;margin-top:2px}
.postit{position:relative;align-self:flex-end;margin-top:52px;width:440px;background:#F5C84C;padding:40px 36px 34px;font-family:'Hand';font-size:52px;line-height:1.3;transform:rotate(2.5deg);box-shadow:6px 8px 0 rgba(43,48,64,.14)}
.photo{position:relative;margin-top:36px;height:690px;border-radius:24px;border:3.5px solid #2B3040;background:#EFE8DA;box-shadow:10px 12px 0 #2B3040}
.photo img{width:100%;height:100%;object-fit:cover;border-radius:20px;display:block}
.noimg{display:flex;height:100%;align-items:center;justify-content:center;font-size:34px;color:#8A877F}
.pcap{margin-top:44px;font-size:42px;font-weight:700;line-height:1.45}
.foot{margin-top:auto;display:flex;flex-direction:column;gap:10px;padding-top:24px}
.note{font-size:25px;font-weight:500;color:#6B6A66;line-height:1.45}
.handle{font-size:28px;font-weight:900;color:#2B3040}
/* 마무리 */
.closing{padding:56px 72px 0;align-items:center}
.closing .hdr{align-self:stretch}
.ccol{align-items:center;margin-top:84px;text-align:center}
.ctitle2{font-size:104px;font-weight:900;line-height:1.2;letter-spacing:-0.035em}
.howto{display:flex;align-items:center;gap:16px;margin-top:56px;background:#FFFFFF;border:3.5px solid #2B3040;border-radius:999px;padding:20px 40px;font-size:42px;font-weight:900;box-shadow:8px 10px 0 #2B3040}
.where{margin-top:30px;font-size:50px}
.btns{display:flex;gap:22px;margin-top:52px}
.btn{display:flex;align-items:center;gap:14px;border-radius:999px;padding:20px 40px;font-size:38px;font-weight:900;background:#2B3040;color:#FBF7EF}
.btn.ghost{background:#FFFFFF;color:#2B3040;border:3.5px solid #2B3040;padding:16px 38px}
.disc{position:absolute;left:0;right:0;bottom:262px;text-align:center;font-size:24px;font-weight:500;color:#6B6A66;line-height:1.5;white-space:pre-line}
"""

FIT_JS = """
() => {
  const card = document.querySelector('.card');
  const warn = [];
  document.querySelectorAll('.fitw').forEach(el => {
    let fs = parseFloat(getComputedStyle(el).fontSize), n = 0;
    const max = el.parentElement.getBoundingClientRect().width;
    while (el.scrollWidth > max + 1 && n < 50) { fs *= 0.97; el.style.fontSize = fs + 'px'; n++; }
    if (n > 12) warn.push('line shrunk ' + Math.round(fs) + 'px: ' + el.textContent.slice(0, 12));
  });
  const z = document.querySelector('.zoom');
  const limit = () => {
    const f = card.querySelector('.foot'); if (f) return f.getBoundingClientRect().top - 8;
    const b = card.querySelector('.badge') || card.querySelector('.band'); if (card.classList.contains('closing')) { const d = card.querySelector('.disc') || card.querySelector('.band'); return d.getBoundingClientRect().top - 16; }
    if (card.classList.contains('fullphoto')) return 1351;
    return card.querySelector('.band').getBoundingClientRect().top - 24;
  };
  const over = () => z.getBoundingClientRect().bottom > limit() || card.scrollHeight > 1351;
  let k = 1;
  while (over() && k > 0.6) { k -= 0.03; z.style.zoom = k; }
  if (k < 1) warn.push('zoom ' + k.toFixed(2));
  if (over()) warn.push('OVERFLOW');
  const bd = card.querySelector('.cover .badge');
  if (bd) {
    const b = bd.getBoundingClientRect();
    for (const el of card.querySelectorAll('.ctitle .fitw, .csub, .hand')) {
      const r = el.getBoundingClientRect();
      if (r.bottom > b.top + 20 && r.right > b.left + 20 && r.top < b.bottom) warn.push('text overlaps badge');
    }
  }
  return [...new Set(warn)];
}
"""


def page(body):
    css = CSS.replace("NOTO", (ROOT / "fonts" / "NotoSansKR-VF.ttf").as_uri()).replace(
        "HAND", (HERE / "fonts" / "GamjaFlower-Regular.ttf").as_uri())
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


def render(spec_path):
    from playwright.sync_api import sync_playwright
    from PIL import Image

    spec = json.loads(Path(spec_path).read_text())
    slug = spec["slug"]
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise SystemExit("slug는 영문 소문자·숫자·하이픈만")
    cards = spec["cards"]
    total = len(cards)
    out = HERE / "cards" / slug
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("[0-9][0-9].jpg"):
        old.unlink()
    warnings, urls = {}, []
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H})
        for i, card in enumerate(cards, 1):
            WARN.clear()
            body = BUILDERS[card.get("type", "list")](card, i, total, spec)
            tmp = out / f"_tmp_{i:02d}.html"
            tmp.write_text(page(body))
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(200)
            w = WARN + pg.evaluate(FIT_JS)
            if w:
                warnings[f"{i:02d}"] = w
            pg.screenshot(path=str(out / f"{i:02d}.jpg"), type="jpeg", quality=93,
                          clip={"x": 0, "y": 0, "width": W, "height": H})
            tmp.unlink()
            urls.append(f"{RAW_BASE}/2kids/cards/{slug}/{i:02d}.jpg")
        br.close()
    ims = [Image.open(out / f"{i:02d}.jpg") for i in range(1, total + 1)]
    tw, th = W // 4, H // 4
    sheet = Image.new("RGB", (tw * total + 14 * (total + 1), th + 28), "#D9D4C8")
    for k, im in enumerate(ims):
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (14 + k * (tw + 14), 14))
    sheet.save(out / "preview.jpg", quality=88)
    (out / "manifest.json").write_text(json.dumps(
        {"slug": slug, "title": spec.get("title"), "count": total, "urls": urls, "warnings": warnings},
        ensure_ascii=False, indent=2))
    print(json.dumps({"slug": slug, "warnings": warnings}, ensure_ascii=False))
    print("\n".join(urls))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for sp in sys.argv[1:]:
        render(sp)
