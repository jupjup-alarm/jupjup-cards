#!/usr/bin/env python3
"""줍줍알람 숏츠(릴스) 렌더러 — 모션그래픽 세로 영상 1080×1920 MP4.

사용법:
    python3 reel.py reels/specs/<slug>.json

결과:
    reels/<slug>/reel.mp4        (인스타 릴스 게시용, H.264 + 무음 AAC)
    reels/<slug>/cover.jpg       (훅 장면 정지 화면)
    reels/<slug>/<slug>.mp4, <slug>_thumb.jpg (같은 파일의 이름 붙은 사본 — manifest 주소는 이쪽)
    reels/<slug>/preview.jpg     (장면별 정지 화면 모음, 점검용)
    reels/<slug>/manifest.json   (공개 주소)

원고(JSON):
{
  "slug": "2026-10-25-seoripul-reel",
  "series": "임대알람",
  "scenes": [
    {"type": "hook", "dur": 3.5, "chips": ["임대알람"], "lines": ["서초에서", "월 {n}만원대"],
     "count": {"to": 36}, "sub": "청년예술인 SH 임대 잔여 6호", "face": "깜짝"},
    {"type": "points", "dur": 5.5, "eyebrow": "가격", "title": "얼마예요?",
     "rows": [["보증금", "2,807만~6,234만원"], ["월 임대료", "36만5,700~81만2,200원"]], "text": "선택"},
    {"type": "cta", "dur": 4, "lines": ["저장해두고", "일정 놓치지 마세요"], "highlight": "일정"}
  ]
}
- hook: lines 안의 {n} 자리에 0 → count.to 로 숫자가 올라감 (원고 숫자 그대로).
- points: rows 2~4개. 한 줄씩 차례로 들어옴.
- 배치: 핵심 내용은 화면 세로 가운데(피드 4:5 미리보기 영역 y≈285~1635)에 모은다. 위 300px(릴스 탭·계정명),
  아래 420px(캡션), 오른쪽 140px(좋아요·댓글 버튼, y 1000 아래)에는 글자·캐릭터를 두지 않는다.
"""
import base64
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from render import THEMES, FACES, BELL, esc, hl, rgba, photo_uri, unit  # noqa: E402
WARN = []
CUT_TIMES, POP_TIMES = [], []   # 템포형: 컷이 바뀌는 시각·튀어나오는 시각 (효과음용)

OWNER_REPO = "jupjup-alarm/jupjup-cards"
BRANCH = os.environ.get("CARDS_BRANCH", "main")
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER_REPO}/{BRANCH}"
W, H, FPS = 1080, 1920, 30
NAVY = "#0F1E3D"


def font_face():
    out = []
    for fam, fn, extra in [("Black Han Sans", "BlackHanSans-Regular.ttf", ""),
                           ("Noto Sans KR", "NotoSansKR-VF.ttf", "font-weight:100 900;")]:
        b64 = base64.b64encode((ROOT / "fonts" / fn).read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{fam}';src:url(data:font/ttf;base64,{b64});{extra}}}")
    return "\n".join(out)


def char_svg(face):
    name = FACES.get(face, "happy") if face != "closing" else "closing"
    return (ROOT / "templates" / f"char_{name}.svg").read_text()


def talk_svg(detail="#0F1E3D"):
    """입이 움직이는 종이 (내레이터). .mouth 타원의 크기를 JS가 음성 크기에 맞춰 바꾼다."""
    d = detail
    return f'''<svg viewBox="0 0 200 200" width="100%" height="100%">
  <circle cx="100" cy="34" r="10" fill="{d}"/>
  <path d="M54 110 Q38 96 40 80" fill="none" stroke="{d}" stroke-width="7" stroke-linecap="round"/>
  <path d="M146 110 Q162 96 160 80" fill="none" stroke="{d}" stroke-width="7" stroke-linecap="round"/>
  <path d="M100 40 C68 40 54 66 54 96 L54 132 L40 152 L160 152 L146 132 L146 96 C146 66 132 40 100 40 Z" fill="#FF5233"/>
  <rect x="36" y="146" width="128" height="14" rx="7" fill="{d}"/>
  <ellipse cx="84" cy="172" rx="12" ry="8" fill="{d}"/><ellipse cx="116" cy="172" rx="12" ry="8" fill="{d}"/>
  <ellipse class="eye" cx="84" cy="98" rx="6" ry="7" fill="#0F1E3D"/><ellipse class="eye" cx="116" cy="98" rx="6" ry="7" fill="#0F1E3D"/>
  <ellipse cx="70" cy="116" rx="7" ry="4" fill="#FFB4A3"/><ellipse cx="130" cy="116" rx="7" ry="4" fill="#FFB4A3"/>
  <ellipse class="mouth" cx="100" cy="120" rx="9" ry="2.5" fill="#0F1E3D"/>
</svg>'''


BREATH_END = re.compile(r"[,，.?!…]+[\"'”’)]*$")


def word_times(words, t0, dur, spans=None):
    """단어가 켜질 시각. spans = 실제 음성에서 말소리가 나는 구간들(쉼으로 나뉨, t0 기준 상대 초).
    대본의 숨 표시(쉼표·문장 끝) 개수와 실제 쉼 개수가 맞으면 묶음마다 그 말소리 구간에 맞춰 켠다."""
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if BREATH_END.search(w):
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    if not spans or len(spans) != len(groups):
        spans, groups = [(0.0, dur)], [words]
    out = []
    for (a, b), g in zip(spans, groups):
        weights = [len(w) + 1 for w in g]
        tot, acc = sum(weights), 0.0
        for k in weights:
            out.append(t0 + a + (b - a) * acc / tot)
            acc += k
    return out


def say_html(text, t0, dur, th, spans=None, fast=False, end=None):
    """내레이션에 맞춰 단어가 하나씩 켜지는 자막. 숫자가 든 단어는 강조색.
    쉼표·문장 끝 = 숨 쉬는 곳 → 실제 음성의 쉼 위치에 맞춰 다음 묶음이 켜진다.
    fast(2026-11-03 템포형): 지금 말하는 구절(숨 단위)만 크게 보여주고, 다음 구절이 나오면 바뀐다."""
    words = str(text or "").split()
    if not words:
        return ""
    times = word_times(words, t0, dur, spans)
    if fast:
        phrases, cur = [], []
        for w, at in zip(words, times):
            cur.append((w, at))
            if BREATH_END.search(w) or len(cur) >= 7:
                phrases.append(cur); cur = []
        if cur:
            phrases.append(cur)
        out = []
        for k, ph in enumerate(phrases):
            a = ph[0][1]
            b = phrases[k + 1][0][1] if k + 1 < len(phrases) else (end if end else t0 + dur + 0.6)
            ws = []
            for w, at in ph:
                num = any(c.isdigit() for c in w)
                cls = "w wn" if num else "w"
                style = f' style="--hl:{th["hl"]}"' if num else ""
                ws.append(f'<span class="{cls}" data-w="{at:.2f}"{style}>{unit(esc(w))}</span>')
            out.append(f'<div class="ph" data-a="{a:.2f}" data-b="{b:.2f}">{" ".join(ws)}</div>')
        return f'<div class="say fast">{"".join(out)}</div>'
    out = []
    for w, at in zip(words, times):
        num = any(c.isdigit() for c in w)
        cls = "w wn" if num else "w"
        style = f' style="--hl:{th["hl"]}"' if num else ""
        out.append(f'<span class="{cls}" data-w="{at:.2f}"{style}>{unit(esc(w))}</span>')
    return f'<div class="say">{" ".join(out)}</div>'


def bg_html(src, start, end, credit=None, pos=None, cuts=False):
    """풀화면 배경: 지도(maps/)는 단지 쪽으로 천천히 확대, 사진은 천천히 확대하며 옆으로 흐름.
    cuts(템포형): 사진을 약 1.8초마다 다른 구도(확대·위치)로 끊어 보여준다 — 한 장으로도 컷이 바뀌는 느낌."""
    uri = photo_uri(src)
    if src and not uri:
        WARN.append(f"배경 {src} 없음 → 색 배경으로 만듦")
    if not uri:
        return "", False
    is_map = str(src).startswith("maps/")
    credit = credit or ("© NAVER Corp." if is_map else "")
    motion = "zoom" if is_map else ("cuts" if cuts else "pan")
    if cuts:
        n = max(1, int((end - start) / 1.8))
        CUT_TIMES.extend(start + (end - start) * k / n for k in range(1, n))
    return (f'<img class="bgimg {motion}" data-s="{start:.3f}" data-e="{end:.3f}" src="{uri}" alt="" '
            f'style="object-position:{esc(pos or "center 45%")}">'
            f'<div class="bgshade"></div>'
            + (f'<div class="hcredit">{esc(credit)}</div>' if credit else "")), True


def beat_html(sc, th, start, end):
    """이야기 장면: 풀화면 배경 + 숫자(또는 핵심어) 하나 크게 + 내레이션 자막."""
    fast = sc.get("_fast")
    back, has_bg = bg_html(sc.get("bg"), start, end, sc.get("bg_credit"), sc.get("bg_pos"), cuts=fast)
    if not has_bg:
        back = f'<div class="blob" style="background:{th["spark"]}"></div>'
    ink = "#FFFFFF" if has_bg else (th.get("fg") or th["ink"])
    vs, vd = sc.get("_vs"), sc.get("_vd")
    if vs is None:
        vs, vd = start + 0.3, max(0.8, (end - start) - 0.9)
    eyebrow = (f'<div class="bchip in" data-in="{start + 0.1:.2f}" style="background:{th["chip_bg"]};color:{th["chip_fg"]}">'
               f'{esc(sc["eyebrow"])}</div>' if sc.get("eyebrow") else "")
    big = (f'<div class="big in pop" data-in="{start + 0.25:.2f}"><span class="pulse" data-p="{start + 0.7:.2f}" '
           f'style="display:inline-block">{hl(sc["big"], sc.get("highlight"), th["hl"])}</span></div>'
           if sc.get("big") else "")
    bsub = (f'<div class="bsub in" data-in="{start + 0.45:.2f}">{unit(esc(sc["big_sub"]))}</div>'
            if sc.get("big_sub") else "")
    proof = proof_html(sc.get("proof"), th, start, end) if fast else ""
    if proof:   # 증거 카드가 나오면 큰 숫자는 물러나고 카드가 그 자리를 채운다 (자막은 계속)
        pat = start + min(1.1, (end - start) * 0.3)
        eyebrow = eyebrow.replace('class="bchip in"', f'class="bchip in" data-out="{pat:.2f}"')
        big = big.replace('class="big in pop"', f'class="big in pop" data-out="{pat:.2f}"')
        bsub = bsub.replace('class="bsub in"', f'class="bsub in" data-out="{pat:.2f}"')
    if fast and sc.get("big"):
        POP_TIMES.append(start + 0.25)
    return f'''
<section class="scene beat{' onbg' if has_bg else ''}{' fastb' if fast else ''}" data-dark="1" data-s="{start:.3f}" data-e="{end:.3f}" style="background:{th['bg']};color:{ink}">
  {back}
  {proof}
  <div class="bbody">{eyebrow}{big}{bsub}{say_html(sc.get("say"), vs, vd, th, sc.get("_vspans"), fast=fast, end=end)}</div>
</section>'''


def num_of(v):
    """'13억원'·'3억9,050만원'·'56만5,050원' → 억 단위 숫자 (막대 길이용). 못 읽으면 None."""
    t = str(v).replace(",", "").replace(" ", "")
    m = re.match(r"(?:(\d+(?:\.\d+)?)억)?(?:(\d+(?:\.\d+)?)천)?(?:(\d+(?:\.\d+)?)만)?(\d+)?원?", t)
    if not m or not any(m.groups()):
        return None
    eok, cheon, man, won = (float(x) if x else 0 for x in m.groups())
    return eok + cheon * 0.1 + man / 10000 + won / 1e8


def proof_html(pf, th, start, end):
    """증거 카드 (2026-11-03): 말로만 하지 않고 근거를 화면에 띄운다. 장면 중간에 튀어나옴.
    kind compare = 비교 막대(이 집 vs 옆 단지 실거래), doc = 공고문 요약 메모(형광펜), image = 평면도·조감도·배치도."""
    if not pf:
        return ""
    at = start + min(1.1, (end - start) * 0.3)
    POP_TIMES.append(at)
    kind = pf.get("kind")
    src = f'<div class="pfsrc">{esc(pf.get("src") or "")}</div>' if pf.get("src") else ""
    if kind == "compare":
        items = pf.get("items") or []
        ns = [it.get("n") if it.get("n") is not None else num_of(it.get("value")) for it in items]
        mx = max([x for x in ns if x] or [1])
        rows = ""
        for k, (it, n) in enumerate(zip(items, ns)):
            w = 100 * (n or 0) / mx
            col = th["hl"] if k == 0 else "rgba(255,255,255,.55)"
            rows += (f'<div class="pfrow"><div class="pfl">{esc(it.get("label"))}</div>'
                     f'<div class="pfbar"><i class="grow" data-g="{at + 0.25 + k * 0.35:.2f}" data-w="{w:.1f}" style="background:{col}"></i></div>'
                     f'<div class="pfv" style="color:{col if k == 0 else "#fff"}">{unit(esc(it.get("value")))}</div></div>')
        body = f'<div class="pfhead">{esc(pf.get("head") or "비교해보면")}</div>{rows}{src}'
        cls = "pf cmp"
    elif kind == "doc":
        mark = pf.get("mark")
        lines = "".join(f'<div class="pfln{" mk" if mark is not None and k == int(mark) else ""}">'
                        f'<span class="hlbg" data-g="{at + 0.6:.2f}" style="background:{rgba(th["hl"], .55)}"></span>'
                        f'<span class="tx">{unit(esc(ln))}</span></div>'
                        for k, ln in enumerate(pf.get("lines") or []))
        body = (f'<div class="pfdochead"><span class="pfdoctag">공고문 요약</span>{esc(pf.get("head") or "")}</div>'
                f'{lines}{src}')
        cls = "pf doc"
    elif kind == "image":
        uri = photo_uri(pf.get("img"))
        if not uri:
            WARN.append(f"증거 이미지 {pf.get('img')} 없음 → 카드 뺌")
            return ""
        body = (f'<div class="pfimg"><img src="{uri}" alt=""></div>'
                f'<div class="pfsrc">{esc(pf.get("credit") or pf.get("src") or "")}</div>')
        cls = "pf img"
    else:
        WARN.append(f"알 수 없는 증거 카드: {kind}")
        return ""
    return f'<div class="{cls} in pop" data-in="{at:.2f}">{body}</div>'''


def scene_html(sc, th, idx, start, end):
    t = sc["type"]
    a = f'data-s="{start:.3f}" data-e="{end:.3f}"'
    if t == "hook":
        chips = "".join(
            f'<span class="chip" '
            f'style="background:{th["chip_bg"] if i == 0 else "transparent"};color:{th["chip_fg"] if i == 0 else th["ink"]};'
            f'border:3px solid {th["outline"]}">{esc(c)}</span>'
            for i, c in enumerate(sc.get("chips", [])))
        lines = ""
        acc = sc.get("accent_line", 2 if sc.get("basis") else None)  # 주비서식(2026-11-02): 그 줄 전체 강조색
        for i, ln in enumerate(sc["lines"]):
            txt = esc(ln)
            if "{n}" in txt:
                txt = txt.replace("{n}", f'<span class="num pulse" data-p="{start + 0.35:.2f}" '
                                          f'style="display:inline-block;color:{th["hl"]}">{esc(sc["count"]["to"])}</span>')
                txt = f'<span style="color:{th["hl"]}">{txt}</span>'
            elif acc and i + 1 == int(acc):
                txt = f'<span style="color:{th["hl"]}">{txt}</span>'
            lines += f'<div class="hline punch" data-p="{start:.2f}">{unit(txt)}</div>'
        src = sc.get("photo") or sc.get("bg")
        uri = photo_uri(src)
        if src and not uri:
            WARN.append(f"사진 {src} 없음 → 사진 없이 만듦")
        if uri:
            bg = th["bg"]
            grad = (f"linear-gradient(180deg,{rgba(bg, .45)} 0%,{rgba(bg, .1)} 22%,{rgba(bg, .2)} 36%,"
                    f"{rgba(bg, .86)} 50%,{bg} 62%,{bg} 100%)")
            is_map = str(src).startswith("maps/")
            credit = sc.get("photo_credit") or sc.get("bg_credit") or ("© NAVER Corp." if is_map else "")
            back = (f'<img class="hph {"zoom" if is_map else "kb"}" data-s="{start:.3f}" data-e="{end:.3f}" src="{uri}" alt="" '
                    f'style="object-position:{esc(sc.get("photo_pos") or sc.get("bg_pos") or "center 40%")}">'
                    f'<div class="hshade" style="background:{grad}"></div>'
                    + (f'<div class="hcredit">{esc(credit)}</div>' if credit else ""))
            cls = "scene hook photo"
        else:
            back = f'<div class="blob" style="background:{th["spark"]}"></div>'
            cls = "scene hook"
        return f'''
<section class="{cls}" data-dark="1" {a} style="background:{th['bg']}">
  {back}
  <div class="chips">{chips}</div>
  {f'<div class="hbasis" style="color:{th["sub"] if not uri else "#FFFFFF"}">{esc(sc["basis"])}</div>' if sc.get("basis") else ''}
  <div class="hlines" style="color:{th['ink'] if th.get('fg') is None else th['fg']}">{lines}</div>
  <div class="hsub in" data-in="{start + 0.25:.2f}" style="color:{th['sub']}">{esc(sc.get('sub'))}</div>
  <div class="char bounce in" data-in="{start + 0.15:.2f}">{char_svg(sc.get('face', '깜짝'))}</div>
</section>'''
    if t == "beat":
        return beat_html(sc, th, start, end)
    if t == "points":
        rows = "".join(
            f'<div class="row in" data-in="{start + 0.55 + i * 0.35:.2f}" style="background:{th["tint"]}">'
            f'<div class="rl" style="color:{th["accent"]}">{esc(r[0])}</div>'
            f'<div class="rv">{esc(r[1])}</div></div>'
            for i, r in enumerate(sc["rows"]))
        text = (f'<div class="ptext in" data-in="{start + 0.55 + len(sc["rows"]) * 0.35 + 0.2:.2f}">{esc(sc["text"])}</div>'
                if sc.get("text") else "")
        return f'''
<section class="scene points" {a}>
  <div class="eyebrow in" data-in="{start + 0.1:.2f}" style="color:{th['accent']}">{esc(sc.get('eyebrow'))}</div>
  <div class="ptitle in" data-in="{start + 0.2:.2f}">{unit(esc(sc.get('title')))}</div>
  <div class="rows">{rows}</div>
  {text}
</section>'''
    if t == "plan":
        uri = photo_uri(sc.get("image"))
        if not uri:
            WARN.append(f"평면도 {sc.get('image')} 없음")
        meta = " · ".join(f'<span style="color:{th["accent"]}">{esc(r[0])}</span> {unit(esc(r[1]))}'
                          for r in (sc.get("rows") or [])[:2])
        img = f'<img src="{uri}" alt="">' if uri else ''
        return f'''
<section class="scene points plan" {a}>
  <div class="eyebrow in" data-in="{start + 0.1:.2f}" style="color:{th['accent']}">{esc(sc.get('eyebrow') or '평면도')}</div>
  <div class="ptitle in" data-in="{start + 0.2:.2f}">{unit(esc(sc.get('title')))}</div>
  <div class="planbox in pop" data-in="{start + 0.35:.2f}">{img}</div>
  <div class="pmeta in" data-in="{start + 0.7:.2f}">{meta}</div>
  <div class="pcred">{esc(sc.get('credit') or '이미지: 사업주체 제공 평면도 · 실제와 다를 수 있음')}</div>
</section>'''
    if t == "cta":
        lines = "".join(f'<div class="cline in pop" data-in="{start + 0.25 + i * 0.2:.2f}">{hl(ln, sc.get("highlight"), th["accent"])}</div>'
                        for i, ln in enumerate(sc["lines"]))
        return f'''
<section class="scene cta" {a} style="background:{th['soft']}">
  <div class="cchar bounce in" data-in="{start + 0.05:.2f}">{talk_svg() if sc.get('_voiced') else char_svg('closing')}</div>
  <div class="clines">{lines}</div>
  {f'<div class="cask in" data-in="{start + 0.7:.2f}" style="color:{th["accent"]}">{esc(sc["ask"])}</div>' if sc.get("ask") else ""}
  <div class="btns in" data-in="{start + 0.9:.2f}">
    <span class="btn" style="background:{th['btn']}">팔로우하고 알림 받기</span>
  </div>
  <div class="disc in" data-in="{start + 1.1:.2f}">정보 제공 목적이며 투자 권유가 아닙니다.<br>신청 전 입주자모집공고 원문을 꼭 확인하세요.</div>
</section>'''
    raise ValueError(f"알 수 없는 장면: {t}")


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{word-break:keep-all;width:1080px;height:1920px;overflow:hidden;background:#fff;font-family:'Noto Sans KR',sans-serif;color:#0F1E3D}
.scene{position:absolute;inset:0;opacity:0;padding:440px 84px 520px;display:flex;flex-direction:column;overflow:hidden}
.brand{position:absolute;left:84px;top:300px;display:flex;align-items:center;gap:12px;font-weight:900;font-size:34px;z-index:5}
.bar{position:absolute;left:84px;right:84px;top:370px;height:8px;border-radius:4px;background:rgba(15,30,61,.12);z-index:5;overflow:hidden}
.bar i{display:block;height:100%;width:0}
.hook{justify-content:center;padding-bottom:560px}
.blob{position:absolute;width:900px;height:900px;border-radius:50%;right:-380px;top:180px;opacity:.13}
.chips{display:flex;gap:16px;margin-bottom:40px}
.chip{font-weight:900;font-size:40px;padding:10px 26px;border-radius:14px}
.hlines{font-family:'Black Han Sans';font-size:190px;line-height:1.08;letter-spacing:-2px}
.hline{white-space:nowrap}
.hbasis{font-size:44px;font-weight:700;line-height:1.35;margin:-12px 0 28px;word-break:keep-all;position:relative;max-width:850px}
.hook.photo .hbasis{text-shadow:0 2px 12px rgba(0,0,0,.45)}
.hsub{font-size:52px;font-weight:700;margin-top:44px;line-height:1.4;white-space:pre-line}
.char{position:absolute;right:170px;bottom:420px;width:320px;height:320px}
.unit{font-family:'Noto Sans KR',sans-serif;font-weight:900;font-size:.82em;letter-spacing:0}
.hph{position:absolute;left:0;top:0;width:1080px;height:1250px;object-fit:cover;transform-origin:center 40%}
.hshade{position:absolute;inset:0}
.hcredit{position:absolute;right:84px;top:400px;font-size:26px;font-weight:500;color:rgba(255,255,255,.85);
 text-shadow:0 1px 6px rgba(0,0,0,.6);max-width:760px;text-align:right}
.hook.photo{justify-content:flex-end}
.hook.photo .char{display:none}
.hook.photo .chips,.hook.photo .hlines,.hook.photo .hsub{position:relative}
.hook.photo .hlines{font-size:170px;text-shadow:0 4px 24px rgba(0,0,0,.25)}
.points{justify-content:center}
.planbox{flex-shrink:0;height:640px;border-radius:32px;border:3px solid #E3E7ED;background:#fff;display:flex;align-items:center;justify-content:center;padding:24px;margin-bottom:24px;overflow:hidden}
.plan .ptitle{font-size:92px;margin-bottom:24px}
.pmeta{font-size:42px;font-weight:800;line-height:1.35}
.planbox img{max-width:100%;max-height:100%;object-fit:contain}
.pcred{font-size:26px;color:#5B6472;margin-top:18px}
.voiced .plan .planbox{height:520px}
.voiced .plan .ptitle{font-size:88px}
.eyebrow{font-size:50px;font-weight:900;margin-bottom:18px}
.ptitle{white-space:pre-line;font-family:'Black Han Sans';font-size:124px;line-height:1.12;margin-bottom:56px;letter-spacing:-1px}
.rows{display:flex;flex-direction:column;gap:26px}
.row{border-radius:32px;padding:44px 46px;display:flex;align-items:center;gap:30px}
.rl{flex:0 0 230px;font-size:44px;font-weight:900}
.rv{font-size:58px;font-weight:800;line-height:1.3;white-space:pre-line}
.ptext{white-space:pre-line;margin-top:48px;font-size:46px;font-weight:600;color:#5B6472;line-height:1.45}
.cta{align-items:center;justify-content:center;text-align:center;padding-top:420px;padding-bottom:460px}
.cchar{width:380px;height:380px;margin-bottom:30px}
.cline{font-family:'Black Han Sans';font-size:100px;line-height:1.15}
.btns{margin-top:56px}
.btn{display:inline-block;color:#fff;font-weight:900;font-size:46px;padding:26px 54px;border-radius:999px}
.disc{margin-top:48px;font-size:30px;color:#5B6472;line-height:1.5}
.in{opacity:0}
.narrator{position:absolute;left:60px;bottom:430px;width:210px;height:210px;z-index:6;opacity:0}
.voiced .hook .char{display:none}
.voiced .hook{padding-bottom:640px}
.voiced .points{padding-bottom:660px}
.voiced .ptitle{font-size:108px;margin-bottom:36px}
.voiced .rows{gap:20px}
.voiced .row{padding:32px 40px}
.voiced .rv{font-size:52px}
.voiced .ptext{font-size:42px;margin-top:32px}
.beat{padding:0}
.bgimg{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;transform-origin:center 45%}
.bgshade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(8,14,30,.55) 0%,rgba(8,14,30,.05) 17%,rgba(8,14,30,.08) 27%,rgba(8,14,30,.78) 39%,rgba(8,14,30,.92) 50%,rgba(8,14,30,.95) 100%)}
.bgimg.zoom{height:1300px;transform-origin:center center}
.bbody{position:absolute;left:84px;right:84px;bottom:670px;display:flex;flex-direction:column;align-items:flex-start}
.bchip{font-weight:900;font-size:44px;padding:10px 28px;border-radius:14px;margin-bottom:26px}
.big{font-family:'Black Han Sans';font-size:176px;line-height:1.05;letter-spacing:-2px;white-space:pre;transform-origin:left center}
.onbg .big{text-shadow:0 6px 30px rgba(0,0,0,.45)}
.bsub{font-size:50px;font-weight:800;margin-top:18px;opacity:.9;white-space:pre-line;line-height:1.3}
.say{margin-top:44px;font-size:54px;font-weight:800;line-height:1.42;max-width:912px}
.say .w{opacity:.32;transition:none}
.say .w.on{opacity:1}
.say .wn.on{color:var(--hl)}
.cask{margin-top:34px;font-size:54px;font-weight:900}
.voiced .beat .bbody{bottom:680px}
/* ── 템포형 (tempo: fast, 2026-11-03) ── */
.tbar{position:absolute;left:54px;right:54px;top:300px;z-index:8;background:rgba(10,12,20,.86);border-radius:22px;
 padding:16px 26px;font-family:'Black Han Sans';font-size:62px;line-height:1.12;color:#fff;text-align:center;letter-spacing:-1px}
.tbl{white-space:nowrap;overflow:hidden}
.tb .brand,.tb .bar{top:-200px}
.tb .hook{padding-top:560px}
.tb .hcredit{top:470px}
.fast .beat .bbody{bottom:440px}
.fast .say.fast{margin-top:30px;min-height:190px;max-width:912px}
.say.fast .ph{display:none;font-size:66px;font-weight:900;line-height:1.3;text-shadow:0 3px 14px rgba(0,0,0,.55)}
.say.fast .ph.on{display:block}
.say.fast .w{opacity:.45}
.say.fast .w.on{opacity:1}
.fast .big{font-size:186px}
.pf{position:absolute;left:70px;right:70px;top:500px;z-index:4;border-radius:30px;padding:30px 34px;box-shadow:0 18px 50px rgba(0,0,0,.45)}
.pf.cmp{background:rgba(10,14,28,.92);color:#fff}
.pfhead{font-size:40px;font-weight:900;margin-bottom:20px;opacity:.9}
.pfrow{display:grid;grid-template-columns:1fr;gap:6px;margin-bottom:18px}
.pfl{font-size:36px;font-weight:700;opacity:.85}
.pfbar{height:44px;border-radius:12px;background:rgba(255,255,255,.1);overflow:hidden}
.pfbar i{display:block;height:100%;width:0;border-radius:12px}
.pfv{font-family:'Black Han Sans';font-size:64px;line-height:1.05}
.pfsrc{font-size:26px;font-weight:500;opacity:.7;margin-top:10px}
.pf.doc{background:#FFFDF6;color:#1B2230;border:2px solid #E6DFC8}
.pfdochead{font-size:38px;font-weight:900;margin-bottom:16px;display:flex;align-items:center;gap:14px}
.pfdoctag{font-size:28px;font-weight:900;color:#fff;background:#1B2230;border-radius:10px;padding:6px 14px}
.pfln{position:relative;font-size:46px;font-weight:800;line-height:1.5;padding:2px 6px}
.pfln .hlbg{position:absolute;left:0;top:18%;height:64%;width:0;border-radius:8px;z-index:0}
.pfln .tx{position:relative;z-index:1}
.pf.doc .pfsrc{color:#5B6472;opacity:1}
.pf.img{background:#fff;color:#1B2230;padding:20px}
.pfimg{height:470px;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:18px;background:#F3F5F8}
.pfimg img{max-width:100%;max-height:100%;object-fit:contain}
.pf.img .pfsrc{color:#5B6472;opacity:1}
.fast .narrator{left:auto;right:60px;bottom:auto;top:470px;width:170px;height:170px}
.tb .narrator{top:520px}
"""

JS = """
const ease=x=>1-Math.pow(1-x,3);
const back=x=>{const c=1.70158,c3=c+1;return 1+c3*Math.pow(x-1,3)+c*Math.pow(x-1,2)};
const cl=x=>Math.max(0,Math.min(1,x));
const TOTAL=__TOTAL__;
function fmt(n){return Math.round(n).toLocaleString('ko-KR')}
window.renderAt=function(t){
  document.querySelectorAll('.scene').forEach(s=>{
    const a=+s.dataset.s,e=+s.dataset.e;
    const o=(a<=0.001?1:cl((t-a)/0.3))*(e>=TOTAL-0.01?1:cl((e-t)/0.3));
    s.style.opacity=o; s.style.visibility=o>0?'visible':'hidden';
    const z=1+0.03*cl((t-a)/(e-a)); s.style.transform='scale('+z+')';
  });
  document.querySelectorAll('.in').forEach(el=>{
    const p=cl((t-(+el.dataset.in))/0.45);
    const k=el.classList.contains('pop')?back(p):ease(p);
    const out=el.dataset.out?cl((t-(+el.dataset.out))/0.25):0;
    el.style.opacity=ease(p)*(1-out);
    if(el.dataset.out){el.style.display=out>=1?'none':'';}
    el.style.transform=el.classList.contains('pop')?'translateY('+((1-k)*80)+'px) scale('+(0.85+0.15*k)+')':'translateY('+((1-k)*60)+'px)';
  });
  document.querySelectorAll('.kb').forEach(el=>{
    const a=+el.dataset.s,e=+el.dataset.e; el.style.transform='scale('+(1.0+0.10*cl((t-a)/(e-a)))+')';
  });
  document.querySelectorAll('.zoom').forEach(el=>{
    const a=+el.dataset.s,e=+el.dataset.e; el.style.transform='scale('+(1.0+0.55*ease(cl((t-a)/(e-a))))+')';
  });
  document.querySelectorAll('.pan').forEach(el=>{
    const a=+el.dataset.s,e=+el.dataset.e,p=cl((t-a)/(e-a));
    el.style.transform='scale('+(1.14+0.06*p)+') translateX('+((p-0.5)*-5)+'%)';
  });
  document.querySelectorAll('.say .w').forEach(el=>{el.classList.toggle('on', t>=+el.dataset.w)});
  document.querySelectorAll('.say.fast .ph').forEach(el=>{el.classList.toggle('on', t>=+el.dataset.a-0.05 && t<+el.dataset.b-0.05)});
  document.querySelectorAll('.say.fast').forEach(sy=>{ if(![...sy.children].some(c=>c.classList.contains('on'))&&sy.children.length){
    const ch=[...sy.children]; const first=ch[0]; if(t<+first.dataset.a) first.classList.add('on'); else ch[ch.length-1].classList.add('on'); }});
  const CUTS=[[1.12,'50% 45%',0],[1.38,'30% 40%',-2],[1.26,'70% 55%',2],[1.55,'50% 35%',0],[1.2,'40% 60%',-1.5]];
  document.querySelectorAll('.cuts').forEach(el=>{
    const a=+el.dataset.s,e=+el.dataset.e,n=Math.max(1,Math.floor((e-a)/1.8)),seg=(e-a)/n;
    const k=Math.max(0,Math.min(n-1,Math.floor((t-a)/seg))),q=cl((t-a-k*seg)/seg),c=CUTS[k%CUTS.length];
    el.style.transformOrigin=c[1]; el.style.transform='scale('+(c[0]+0.05*q)+') translateX('+(c[2]*q)+'%)';
  });
  document.querySelectorAll('.grow').forEach(el=>{el.style.width=(+el.dataset.w*ease(cl((t-(+el.dataset.g))/0.7)))+'%'});
  document.querySelectorAll('.pfln.mk .hlbg').forEach(el=>{el.style.width=(100*ease(cl((t-(+el.dataset.g))/0.5)))+'%'});
  document.querySelectorAll('.punch').forEach(el=>{
    const k=ease(cl((t-(+el.dataset.p))/0.25)); el.style.transform='scale('+(1.05-0.05*k)+')'; el.style.transformOrigin='left center';
  });
  document.querySelectorAll('.pulse').forEach(el=>{
    const q=cl((t-(+el.dataset.p))/0.45); el.style.transform='scale('+(1+0.18*Math.sin(Math.PI*q))+')';
  });
  document.querySelectorAll('.bounce').forEach(el=>{
    const p=cl((t-(+el.dataset.in))/0.45);
    if(p>=1){el.style.transform='translateY('+(Math.sin((t-(+el.dataset.in))*4)*12)+'px) rotate('+(Math.sin((t-(+el.dataset.in))*2.6)*4)+'deg)';}
  });
  document.querySelectorAll('[data-count]').forEach(el=>{
    const p=cl((t-(+el.dataset.cs))/(+el.dataset.cd));
    el.textContent=fmt((+el.dataset.count)*ease(p));
  });
  let dark=false;document.querySelectorAll('.scene').forEach(s=>{if(s.dataset.dark&&t>=+s.dataset.s&&t<+s.dataset.e-0.15)dark=true});
  document.querySelector('.brand').style.color=dark?'#FFFFFF':'#0F1E3D';
  document.querySelector('.bar').style.background=dark?'rgba(255,255,255,.2)':'rgba(15,30,61,.12)';
  document.querySelector('.bar i').style.width=(100*cl(t/TOTAL))+'%';
  const nar=document.querySelector('.narrator');
  if(nar){
    const ctaS=+(document.querySelector('.cta')||{dataset:{s:1e9}}).dataset.s;
    let pfOn=0; document.querySelectorAll('.pf').forEach(p=>{const sc=p.closest('.scene'); if(t>=+p.dataset.in-0.2&&t<+sc.dataset.e) pfOn=1;});
    nar.style.opacity=cl((t-0.4)/0.4)*cl((ctaS-t)/0.3)*(1-pfOn);
    nar.style.transform='translateY('+(Math.sin(t*3.2)*8)+'px) rotate('+(Math.sin(t*2.1)*3)+'deg)';
    nar.querySelectorAll('rect,circle,path,ellipse:not(.eye):not(.mouth)').forEach(x=>{
      if(x.getAttribute('fill')!=='#FF5233'&&!x.getAttribute('fill')?.startsWith('#FFB4')){
        if(x.getAttribute('fill')&&x.getAttribute('fill')!=='none')x.setAttribute('fill',dark?'#FFFFFF':'#0F1E3D');
        if(x.getAttribute('stroke'))x.setAttribute('stroke',dark?'#FFFFFF':'#0F1E3D');}});
  }
  const v=MOUTH.length?(MOUTH[Math.min(MOUTH.length-1,Math.round(t*30))]||0):0;
  document.querySelectorAll('.mouth').forEach(m=>{m.setAttribute('ry',(2.5+12*v).toFixed(2));m.setAttribute('rx',(9+4*v).toFixed(2))});
  const blink=(t%3.7)<0.12;
  document.querySelectorAll('.eye').forEach(e=>e.setAttribute('ry',blink?'1':'7'));
};
"""


LEAD, TAIL = 0.35, 0.5   # (음성 없을 때) 장면 시작 후 말하기까지, 말 끝난 뒤 다음 장면까지 (초)
FIRST_LEAD = 0.05        # 첫 장면(훅)은 바로 말하기 시작 — 1초 안에 훅이 들리게
# 2026-11-03 사용자 "대사가 쉬는 부분이 많다": 음성 앞뒤 무음을 잘라 붙이고, 장면 사이 숨은 0.12+0.25초만.
V_LEAD, V_TAIL, V_LAST_TAIL = 0.12, 0.25, 1.1


def lead(i):
    return FIRST_LEAD if i == 0 else V_LEAD


def speech_spans(path, min_pause=0.15, noise="-38dB"):
    """음성 파일에서 말소리 구간들 [(시작, 끝)…] (앞뒤 무음 제외, 문장 안 쉼으로 나뉨)."""
    total = audio_len(path)
    log = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-af", f"silencedetect=n={noise}:d={min_pause}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    sil, s0 = [], None
    for line in log.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            s0 = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and s0 is not None:
            sil.append((s0, float(m.group(1)))); s0 = None
    if s0 is not None:
        sil.append((s0, total))
    spans, pos = [], 0.0
    for a, b in sil:
        if a - pos > 0.05:
            spans.append((pos, a))
        pos = b
    if total - pos > 0.05:
        spans.append((pos, total))
    return spans


def breath_marks(text):
    """대본에서 숨 쉬는 곳(쉼표·문장 끝) 수 = 기대하는 말소리 구간 수 - 1."""
    words = str(text or "").split()
    n = sum(1 for w in words[:-1] if BREATH_END.search(w))
    return n + 1 if words else 0


def audio_len(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _speed(f, speed, tmp):
    if f and f.exists() and abs(speed - 1.0) > 0.01:   # 말 빠르기 조정 (음높이 유지)
        tmp.mkdir(parents=True, exist_ok=True)
        g = tmp / f.name
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(f), "-filter:a", f"atempo={speed}", str(g)], check=True)
        return g
    return f


def voice_segments(spec):
    """장면별 음성 조각 {file, s0, s1, spans}. spans는 s0 기준 상대 초.
    - voices/<id>/full.mp3가 있으면(2026-11-03, 대본 전체를 한 번에 읽힌 것 — 장면 사이도 말이 이어짐)
      장면 수 - 1개의 가장 긴 쉼을 장면 경계로 써서 잘라 쓴다.
    - 없으면 장면별 01.mp3… 의 앞뒤 무음을 잘라 쓴다."""
    n = len(spec["scenes"])
    v = str(spec.get("voice") or "").split(" ")[0].strip()
    if not v:
        return [None] * n
    d = ROOT / v
    speed = float(spec.get("voice_speed", 1.0))
    tmp = ROOT / "reels" / spec["slug"] / "_voice"
    full = _speed(d / "full.mp3", speed, tmp)
    if full and full.exists() and n > 1:
        sp = speech_spans(full, min_pause=0.12)
        gaps = sorted(range(len(sp) - 1), key=lambda j: sp[j + 1][0] - sp[j][1], reverse=True)[:n - 1]
        if len(sp) >= n and len(gaps) == n - 1:
            cut = sorted(gaps)
            groups, k0 = [], 0
            for g in cut + [len(sp) - 1]:
                groups.append(sp[k0:g + 1]); k0 = g + 1
            out = []
            for grp in groups:
                a, b = grp[0][0], grp[-1][1]
                out.append({"file": full, "s0": max(0.0, a - 0.03), "s1": b + 0.06,
                            "spans": [(x - a, y - a) for x, y in grp]})
            return out
        WARN.append(f"한 번에 읽은 음성(full.mp3)에서 장면 경계 {n - 1}곳을 못 찾음 → 장면별 파일 사용")
    out = []
    for i in range(n):
        f = _speed(d / f"{i + 1:02d}.mp3", speed, tmp)
        if not (f and f.exists()):
            out.append(None)
            continue
        sp = speech_spans(f) or [(0.0, audio_len(f))]
        a, b = sp[0][0], sp[-1][1]
        out.append({"file": f, "s0": max(0.0, a - 0.03), "s1": b + 0.06, "spans": [(x - a, y - a) for x, y in sp]})
    return out


def timeline(spec):
    """장면별 (시작, 길이, 음성 조각). 음성이 있으면 말 길이에 딱 맞춘다 (빈 시간 없이)."""
    segs = voice_segments(spec)
    voiced = any(segs)
    t, out = 0.0, []
    last = len(spec["scenes"]) - 1
    for i, (sc, g) in enumerate(zip(spec["scenes"], segs)):
        if g:
            d = lead(i) + (g["s1"] - g["s0"]) + (V_LAST_TAIL if i == last else V_TAIL)
        elif voiced:
            d = float(sc.get("dur", 2.5))
        else:
            d = float(sc.get("dur", 5))
        out.append((t, d, g))
        t += d
    return out, t


def envelope(tl, total):
    """음성 크기 → 프레임별 입 벌림(0~1)."""
    import numpy as np
    n = int(round(total * FPS))
    env = np.zeros(n)
    sr, hop = 16000, 16000 // FPS
    for i, (start, _, g) in enumerate(tl):
        if not g:
            continue
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{g['s0']:.3f}", "-to", f"{g['s1']:.3f}", "-i", str(g["file"]),
                              "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True, check=True).stdout
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
        k = len(a) // hop
        rms = np.sqrt((a[:k * hop].reshape(k, hop) ** 2).mean(axis=1))
        off = int(round((start + lead(i)) * FPS))
        env[off:off + k] = rms[: max(0, min(k, n - off))]
    if env.max() > 0:
        env = env / (np.percentile(env[env > 0], 90) + 1e-6)
    env = np.clip(env, 0, 1)
    env[env < 0.12] = 0
    sm = env.copy()
    for i in range(1, n):          # 닫힐 때는 천천히
        sm[i] = max(env[i], sm[i - 1] * 0.55)
    return [round(float(x), 3) for x in sm]


def build(spec):
    th = dict(THEMES.get(spec.get("series", "줍줍알람"), THEMES["줍줍알람"]))
    tl, total = timeline(spec)
    voiced = any(f for _, _, f in tl)
    fast = spec.get("tempo") == "fast"
    CUT_TIMES.clear(); POP_TIMES.clear()
    scenes = []
    for i, (sc, (t, d, f)) in enumerate(zip(spec["scenes"], tl)):
        sc = dict(sc, _voiced=voiced, _fast=fast)
        if fast and i:
            CUT_TIMES.append(t)
        if sc["type"] == "beat" and not sc.get("bg") and spec.get("bg"):
            sc["bg"] = spec["bg"]                      # 장면에 배경이 없으면 원고 전체 배경(단지 사진·지도)
            sc.setdefault("bg_credit", spec.get("bg_credit"))
        if sc.get("bg") == "none":
            sc["bg"] = None
        if f:                                          # 자막 단어가 켜지는 시간 = 이 장면 음성 구간
            sc["_vs"], sc["_vd"] = t + lead(i), f["s1"] - f["s0"]
            if sc.get("say"):                          # 호흡 검사: 대본의 숨 표시 vs 실제 쉼
                spans, want = list(f["spans"]), breath_marks(sc["say"])
                extra = []
                while len(spans) > want > 0:           # 대본에 없는 쉼은 가장 짧은 것부터 합침
                    k = min(range(len(spans) - 1), key=lambda j: spans[j + 1][0] - spans[j][1])
                    extra.append(spans[k + 1][0] - spans[k][1])
                    spans[k:k + 2] = [(spans[k][0], spans[k + 1][1])]
                if len(spans) == want:
                    sc["_vspans"] = spans
                if len(spans) < want:
                    WARN.append(f"호흡: 장면 {i + 1} 쉼표에서 안 쉼 (대본 숨 {want - 1}곳 / 실제 {len(spans) - 1}곳) "
                                f"→ 자막은 글자 수로 맞춤")
                elif extra and max(extra) > 0.25:
                    WARN.append(f"호흡: 장면 {i + 1} 대본에 없는 곳에서 {max(extra):.2f}초 쉼 (③ 대본 쉼표 위치 확인)")
        scenes.append(scene_html(sc, th, i, t, t + d))
    mouth = envelope(tl, total) if voiced else []
    narrator = f'<div class="narrator">{talk_svg()}</div>' if voiced else ""
    tbar = ""
    if spec.get("title_bar"):   # 템포형: 영상 내내 맨 위에 고정되는 제목 (2026-11-03, 주비서·양집사·베리스식)
        tl_ = str(spec["title_bar"]).split("\n")[:2]
        tbar = ('<div class="tbar">' + "".join(
            f'<div class="tbl"{f" style=\"color:{th["hl"]}\"" if k == len(tl_) - 1 and len(tl_) > 1 else ""}>{unit(esc(x))}</div>'
            for k, x in enumerate(tl_)) + '</div>')
    body_cls = " ".join(c for c in ("voiced" if voiced else "", "fast" if fast else "", "tb" if tbar else "") if c)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_face()}{CSS}</style></head><body class="{body_cls}">
<div class="brand">{BELL.format(s=40, c=th['accent'])}<span>줍줍알람</span></div>
<div class="bar"><i style="background:{th['accent']}"></i></div>
{tbar}
{''.join(scenes)}
{narrator}
<script>const MOUTH={json.dumps(mouth)};{JS.replace('__TOTAL__', f'{total:.3f}')}</script></body></html>"""
    return page, total, tl


FIT_JS = """
() => {
  // 아래 말하는 캐릭터(왼쪽 아래, y≈1270~)·캡션 자리(아래 420px)와 겹치지 않게: 내용 맨 아래가 1250px을 넘으면 글자 크기를 6%씩 줄임 (최대 5번)
  // 훅 자막은 한 줄씩 끊기지 않게: 가장 긴 줄이 폭(912px)에 들어올 때까지 훅 글자 전체를 같이 줄임
  document.querySelectorAll('.hlines').forEach(h => {
    const max = 1080 - 84 * 2;
    let fs = parseFloat(getComputedStyle(h).fontSize), n = 0;
    while ([...h.querySelectorAll('.hline')].some(l => l.scrollWidth > max) && n < 40) { fs *= 0.96; h.style.fontSize = fs + 'px'; n++; }
  });
  const voiced = document.body.classList.contains('voiced');
  const fast = document.body.classList.contains('fast');
  document.querySelectorAll('.tbl').forEach(l => { let n = 0;   // 맨 위 고정 제목은 줄마다 한 줄로
    while (l.scrollWidth > l.clientWidth + 1 && n < 30) { l.style.fontSize = (parseFloat(getComputedStyle(l).fontSize) * 0.95) + 'px'; n++; } });
  document.querySelectorAll('.scene').forEach(s => {
    const LIMIT = (fast && s.classList.contains('beat')) ? 1500 : ((voiced && !s.classList.contains('cta')) ? 1250 : 1480);  // 마무리 장면엔 말하는 캐릭터가 없음
    const vis = s.style.opacity, vv = s.style.visibility;
    s.style.opacity = 1; s.style.visibility = 'visible';
    s.querySelectorAll('.in').forEach(e => { e.dataset.o = e.style.opacity; e.style.opacity = 1; });
    const bottom = () => Math.max(...[...s.children].filter(k => !['blob','char','hph','hshade','hcredit','bgimg','bgshade','pf'].some(c => k.classList.contains(c)))
                                       .map(k => k.getBoundingClientRect().bottom));
    let k = 0;
    // 이야기 장면: 큰 숫자가 한 줄을 넘지 않게, 묶음 맨 위가 상단 가림 영역(420px)에 닿지 않게
    s.querySelectorAll('.big').forEach(b => { let n = 0;
      while (b.scrollWidth > 912 && n < 30) { b.style.fontSize = (parseFloat(getComputedStyle(b).fontSize) * 0.95) + 'px'; n++; } });
    const pf = s.querySelector('.pf');
    if (pf) { let n = 0;   // 증거 카드(큰 숫자가 물러난 뒤 자리)가 아래 자막과 겹치면 카드 그림 높이 → 카드 글자 순으로 줄임
      const sy = s.querySelector('.say');
      const top = () => sy ? sy.getBoundingClientRect().top : 1500;
      while (pf.getBoundingClientRect().bottom + 30 > top() && n < 16) {
        const im = pf.querySelector('.pfimg');
        if (im && parseFloat(getComputedStyle(im).height) > 280) im.style.height = (parseFloat(getComputedStyle(im).height) * 0.9) + 'px';
        else pf.querySelectorAll('.pfhead,.pfl,.pfv,.pfln,.pfdochead,.pfsrc').forEach(e => { e.style.fontSize = (parseFloat(getComputedStyle(e).fontSize) * 0.94) + 'px'; });
        n++; }
    }
    s.querySelectorAll('.bbody').forEach(b => { let n = 0;
      while (b.getBoundingClientRect().top < (fast ? 470 : 430) && n < 12) {
        b.querySelectorAll('.big,.say,.bsub').forEach(e => { e.style.fontSize = (parseFloat(getComputedStyle(e).fontSize) * 0.94) + 'px'; }); n++; } });
    while (bottom() > LIMIT && k < 5) {
      s.querySelectorAll('.ptitle,.rv,.rl,.ptext,.hlines,.hsub,.cline,.eyebrow,.cask').forEach(e => {
        e.style.fontSize = (parseFloat(getComputedStyle(e).fontSize) * 0.94) + 'px'; });
      s.querySelectorAll('.planbox').forEach(e => { e.style.height = (parseFloat(getComputedStyle(e).height) * 0.9) + 'px'; });
      s.querySelectorAll('.row').forEach(e => { const cs = getComputedStyle(e);
        e.style.paddingTop = e.style.paddingBottom = (parseFloat(cs.paddingTop) * 0.85) + 'px'; });
      k++;
    }
    s.querySelectorAll('.in').forEach(e => { e.style.opacity = e.dataset.o || ''; });
    s.style.opacity = vis; s.style.visibility = vv;
  });
}
"""


def sfx_files():
    """효과음 2개를 직접 만든다 (외부 음원 없음 — 저작권 걱정 없음). 목소리보다 훨씬 작게."""
    d = Path(os.environ.get("TMPDIR", "/tmp")) / "jupjup_sfx"
    d.mkdir(exist_ok=True)
    spec = {"whoosh": "anoisesrc=d=0.32:c=pink:a=0.6,highpass=f=700,lowpass=f=5000,afade=t=in:d=0.12,afade=t=out:st=0.14:d=0.18,volume=0.22",
            "pop": "sine=f=1250:d=0.09,afade=t=out:st=0.01:d=0.08,volume=0.28"}
    out = {}
    for k, f in spec.items():
        p = d / f"{k}.wav"
        if not p.exists():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f, "-ar", "44100", "-ac", "2", str(p)], check=True)
        out[k] = p
    return out


def main(path):
    spec = json.loads(Path(path).read_text())
    slug = spec["slug"]
    out = ROOT / "reels" / slug
    frames = out / "_frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    page, total, tl = build(spec)
    (out / "reel.html").write_text(page)  # 작업용 (저장소에 올리지 않음)

    from playwright.sync_api import sync_playwright
    n = int(round(total * FPS))
    stills = []
    starts = []
    acc = 0.0
    for t0, d, _ in tl:
        starts.append(t0 + (1.0 if t0 == 0 else min(d - 0.3, 2.6)))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.set_content(page)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.evaluate(FIT_JS)   # 내용이 아래 캐릭터·캡션 자리까지 내려가면 글자를 조금씩 줄임
        for f in range(n):
            pg.evaluate(f"renderAt({f / FPS:.4f})")
            pg.screenshot(path=str(frames / f"{f:05d}.jpg"), type="jpeg", quality=92)
        for i, s in enumerate(starts):
            pg.evaluate(f"renderAt({s:.3f})")
            fp = out / f"_still{i}.jpg"
            pg.screenshot(path=str(fp), type="jpeg", quality=90)
            stills.append(fp)
        b.close()

    mp4 = out / "reel.mp4"
    voices = [(t0 + lead(i), g["file"], g["s0"], g["s1"]) for i, (t0, _, g) in enumerate(tl) if g]
    if spec.get("tempo") == "fast" and spec.get("sfx", True):   # 템포형 효과음: 컷마다 휙, 숫자·카드가 튀어나올 때 톡
        sfx = sfx_files()
        voices += [(round(x, 3), sfx["whoosh"], None, None) for x in sorted(set(round(c, 2) for c in CUT_TIMES)) if 0.2 < x < total - 0.3]
        voices += [(round(x, 3), sfx["pop"], None, None) for x in sorted(set(round(c, 2) for c in POP_TIMES)) if 0.2 < x < total - 0.3]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "%05d.jpg"),
           "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    for _, f, _a, _b in voices:
        cmd += ["-i", str(f)]
    if voices:
        def trim(a, b):
            return f"atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS," if a is not None else ""
        fl = "".join(f"[{k + 2}:a]{trim(a, b)}aformat=sample_rates=44100:channel_layouts=stereo,adelay={int(t0 * 1000)}:all=1[v{k}];"
                     for k, (t0, _f, a, b) in enumerate(voices))
        fl += "[1:a]" + "".join(f"[v{k}]" for k in range(len(voices))) + \
              f"amix=inputs={len(voices) + 1}:normalize=0:duration=first,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=44100,atrim=0:{total:.3f}[aout]"
        cmd += ["-filter_complex", fl, "-map", "0:v", "-map", "[aout]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    shutil.rmtree(frames)
    shutil.rmtree(out / "_voice", ignore_errors=True)

    from PIL import Image
    shutil.copy(stills[0], out / "cover.jpg")
    ims = [Image.open(s) for s in stills]
    tw = 360
    th_ = int(H * tw / W)
    sheet = Image.new("RGB", (tw * len(ims) + 20 * (len(ims) + 1), th_ + 40), "#DDDDDD")
    for i, im in enumerate(ims):
        sheet.paste(im.resize((tw, th_)), (20 + i * (tw + 20), 20))
    sheet.save(out / "preview.jpg", quality=88)
    for s in stills:
        s.unlink()

    # 내려받아도 구분되게 slug 이름 사본 (git은 같은 내용을 한 번만 저장 — 용량 그대로, 2026-11-02 유튜브 업로드용)
    shutil.copy(mp4, out / f"{slug}.mp4")
    shutil.copy(out / "cover.jpg", out / f"{slug}_thumb.jpg")
    try:  # 유튜브·인스타 표지용 큰 글자 썸네일 (thumb.py) — 사진이 없으면 첫 프레임 사본 그대로
        import thumb
        td = thumb.from_reel_spec(spec)
        if td:
            thumb.make([td])
    except Exception as e:
        WARN.append(f"썸네일 실패: {e}")
    base = f"{RAW_BASE}/reels/{slug}"
    manifest = {"slug": slug, "duration": round(total, 2), "voiced": bool(voices), "video": f"{base}/{slug}.mp4",
                "cover": f"{base}/{slug}_thumb.jpg", "size_mb": round(mp4.stat().st_size / 1e6, 2), "warnings": WARN}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
