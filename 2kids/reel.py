#!/usr/bin/env python3
"""두아이 살림노트(@2kids_note) 숏츠(릴스) 렌더러 — 모션그래픽 + 내레이션 세로 영상 1080×1920 MP4.

사용법:
    python3 2kids/reel.py 2kids/reels/specs/<slug>.json

결과 (2kids/reels/<slug>/):
    reel.mp4       인스타 릴스·스레드 영상 (H.264 + AAC)
    cover.jpg      표지 (훅 장면)
    preview.jpg    장면별 정지 화면 모음 (점검용)
    manifest.json  공개 주소(video, cover)·길이

원고(JSON):
{
  "slug": "2026-10-26-first-voucher-reel",
  "title": "첫만남이용권",
  "series": "돈 나오는 육아",              // 화면 위 태그
  "voice": "2kids/voices/<id>/",           // 시트 AA열 값(앞부분). 없으면 무음 + 기본 길이
  "voice_speed": 1.0,                      // 선택: 음성 빠르기 추가 조정
  "bgm": "sunny",                          // 선택: sunny(밝음)|cozy(잔잔)|bounce(경쾌)|false. 생략하면 골고루 돌려씀
  "ad": false,                             // 상품을 다루면 true → 첫 장면에 "광고 · 링크 구매 시 수수료를 받아요"
  "source": "출처: 보건복지부 · 2026.10.24",
  "scenes": [
    {"type": "hook", "dur": 3.5, "chips": ["돈 나오는 육아"], "lines": ["쌍둥이면", "{n}만 원 더"], "count": {"to": 200}, "sub": "출생신고만 하면 아이마다"},
    {"type": "say", "dur": 4, "lines": ["누구나 받는 건", "아니고요"], "highlight": "누구나", "note": "조건부터 볼게요"},
    {"type": "points", "dur": 6, "eyebrow": "핵심 정리", "title": "얼마나, 언제까지", "rows": [["대상", "2024년 이후 출생아"], ["금액", "**첫째 200만 원**"]]},
    {"type": "twins", "dur": 5, "title": "쌍둥이면 이렇게", "rows": [["바우처", "200만 원", "400만 원"]], "note": "아이마다 따로 나와요"},
    {"type": "checks", "dur": 5, "title": "신청 전 체크", "items": ["출생신고 먼저", "국민행복카드 준비", "사용 기한 확인"]},
    {"type": "cta", "dur": 3.5, "lines": ["저장해두고", "신청 놓치지 마세요"], "highlight": "저장", "share": "출산 앞둔 친구한테 보내주세요"}
  ]
}
- B형 루프 리스트: "loop": true + 장면 hook(dur 1.6) → list({"items": [["부모급여", "월 100만×2"], …] 최대 5, "step": 0.9}).
  음성 없이 배경음악만. 마지막 0.4초에 첫 장면으로 돌아가 반복 재생이 끊김 없이 이어짐.
- C형 체크: ask {"n": "1 / 3", "q": "질문", "a": "예"|"아니오", "note": 선택} — 2.8초, 0.5초 뒤 답 버튼이 눌림.
- 숫자·문구는 원고 그대로 (시트 정보조사 행과 같아야 함). **굵게** = 형광펜.
- 인스타 가림 영역(위 250px, 아래 400px)에는 핵심 글자를 두지 않는다.
- 음성은 장면 순서대로 voices/<id>/01.mp3, 02.mp3 … 를 붙이고(앞뒤 무음은 잘라냄), 장면 길이를 음성에 맞춘다.
  음성이 있으면 dur는 무시된다. 오래 보여줘야 하는 장면만 "min": 초.
"""
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OWNER_REPO = "jupjup-alarm/jupjup-cards"
BRANCH = os.environ.get("CARDS_BRANCH", "main")
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER_REPO}/{BRANCH}"
W, H, FPS = 1080, 1920, 30
LEAD, TAIL, END_HOLD = 0.15, 0.35, 1.2   # 음성 앞 여백, 뒤 여백, 마지막 장면 끝 여유

PAPER, INK, YEL, SAGE, LINE, CORAL = "#FBF7EF", "#2B3040", "#F5C84C", "#9DBB97", "#E6DFD1", "#E8735F"


def esc(s):
    return html.escape(str(s if s is not None else ""))


def mark(text, words=None):
    t = esc(text).replace("\n", "<br>")
    t = re.sub(r"\*\*(.+?)\*\*", lambda m: f'<span class="mk">{m.group(1)}</span>', t)
    for w in (words if isinstance(words, list) else ([words] if words else [])):
        w = esc(w)
        if w and w in t and f'">{w}</span>' not in t:
            t = t.replace(w, f'<span class="mk">{w}</span>', 1)
    return t


def L(v):
    return v if isinstance(v, list) else ([v] if v else [])


def font_face():
    out = []
    for fam, p, extra in [("Noto Sans KR", ROOT / "fonts" / "NotoSansKR-VF.ttf", "font-weight:100 900;"),
                          ("Hand", HERE / "fonts" / "GamjaFlower-Regular.ttf", "")]:
        b64 = base64.b64encode(p.read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{fam}';src:url(data:font/ttf;base64,{b64});{extra}}}")
    return "\n".join(out)


def twins_svg():
    """말하는 쌍둥이 (뒷모습). .tw1/.tw2 머리, .acc1 리본, .acc2 방울은 JS가 음성 크기에 맞춰 움직인다."""
    bow = lambda x, y: (f'<path d="M{x-10} {y-7}L{x-10} {y+7}L{x} {y}Z"/><path d="M{x+10} {y-7}L{x+10} {y+7}L{x} {y}Z"/>'
                        f'<circle cx="{x}" cy="{y}" r="3.2"/>')
    pom = lambda x, y: f'<circle cx="{x-4.6}" cy="{y}" r="4.8"/><circle cx="{x+4.6}" cy="{y}" r="4.8"/>'
    return f'''<svg viewBox="0 60 200 112" width="100%" height="100%">
  <path d="M18 160 Q18 132 60 132 Q102 132 102 172L18 172Z" fill="#FFFFFF" stroke="{INK}" stroke-width="2"/>
  <path d="M98 160 Q98 132 140 132 Q182 132 182 172L98 172Z" fill="#FFFFFF" stroke="{INK}" stroke-width="2"/>
  <text x="60" y="160" text-anchor="middle" font-family="Noto Sans KR" font-weight="900" font-size="24" fill="{INK}">1</text>
  <text x="140" y="160" text-anchor="middle" font-family="Noto Sans KR" font-weight="900" font-size="24" fill="{INK}">2</text>
  <g class="tw1" style="transform-origin:60px 120px"><circle cx="30" cy="94" r="11.5" fill="{INK}"/><circle cx="90" cy="94" r="11.5" fill="{INK}"/>
    <circle cx="60" cy="104" r="30" fill="{INK}"/><g class="acc1" fill="{CORAL}">{bow(38, 80)}{bow(82, 80)}</g></g>
  <g class="tw2" style="transform-origin:140px 120px"><circle cx="110" cy="94" r="11.5" fill="{INK}"/><circle cx="170" cy="94" r="11.5" fill="{INK}"/>
    <circle cx="140" cy="104" r="30" fill="{INK}"/><g class="acc2" fill="{CORAL}">{pom(118, 80)}{pom(162, 80)}</g></g>
</svg>'''


def heads_icon():
    return (f'<svg width="58" height="36" viewBox="0 0 64 40"><circle cx="20" cy="22" r="14" fill="{INK}"/><circle cx="44" cy="22" r="14" fill="{INK}"/>'
            f'<circle cx="8" cy="14" r="6" fill="{INK}"/><circle cx="56" cy="14" r="6" fill="{INK}"/>'
            f'<path d="M12 8l-5-4v8zM12 8l5-4v8z" fill="{CORAL}"/><circle cx="50" cy="7" r="3" fill="{CORAL}"/><circle cx="56" cy="7" r="3" fill="{CORAL}"/></svg>')


CHECK = ('<svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="#2B3040" stroke-width="3.2" '
         'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>')


def scene_html(sc, idx, start, end, spec):
    t = sc["type"]
    a = f'data-s="{start:.3f}" data-e="{end:.3f}"'
    at = lambda d: f'data-in="{start + d:.2f}"'
    if t == "hook":
        first = idx == 0
        if first:   # 첫 프레임부터 훅이 다 보이게 (스크롤 1초 안에 판단)
            at = lambda d: f'data-in="{start - 0.4:.2f}"' if d < 0.5 else f'data-in="{start + 0.2:.2f}"'
        chips = "".join(f'<span class="chip{" c2" if i else ""} in" {at(0.05 + i * 0.12)}>{esc(c)}</span>'
                        for i, c in enumerate(L(sc.get("chips") or [spec.get("series")])[:2]))
        lines = ""
        for i, ln in enumerate(L(sc.get("lines"))):
            txt = mark(ln, sc.get("highlight"))
            if "{n}" in txt:
                txt = txt.replace("{n}", f'<span class="num" data-count="{sc["count"]["to"]}" data-cs="{start + (0.0 if first else 0.45):.2f}" '
                                          f'data-cd="{0.6 if first else 1.0}" data-from="{0.7 if first else 0}">0</span>')
                txt = f'<span class="mk">{txt}</span>'
            lines += f'<div class="hline in pop" {at(0.15 + i * 0.2)}>{txt}</div>'
        sub = f'<div class="hsub in" {at(1.2)}>{mark(sc.get("sub"))}</div>' if sc.get("sub") else ""
        return f'''<section class="scene hook" {a}><div class="chips">{chips}</div><div class="hlines">{lines}</div>{sub}</section>'''
    if t == "say":
        lines = "".join(f'<div class="sline in pop" {at(0.15 + i * 0.22)}>{mark(ln, sc.get("highlight"))}</div>'
                        for i, ln in enumerate(L(sc.get("lines"))))
        note = f'<div class="hand in" {at(0.9)}>{esc(sc["note"])}</div>' if sc.get("note") else ""
        return f'<section class="scene say" {a}><div class="slines">{lines}</div>{note}</section>'
    if t == "points":
        rows = "".join(f'<div class="row in" {at(0.5 + i * 0.4)}><div class="rl">{esc(r[0])}</div><div class="rv">{mark(r[1])}</div></div>'
                       for i, r in enumerate((sc.get("rows") or [])[:4]))
        text = f'<div class="ptext in" {at(0.6 + len(sc.get("rows") or []) * 0.4)}>{mark(sc["text"])}</div>' if sc.get("text") else ""
        eb = f'<div class="eyebrow in" {at(0.05)}>{esc(sc.get("eyebrow") or "핵심 정리")}</div>'
        return (f'<section class="scene points" {a}>{eb}<div class="ptitle in" {at(0.15)}>{mark(sc.get("title"))}</div>'
                f'<div class="card">{rows}</div>{text}</section>')
    if t == "twins":
        rows = "".join(
            f'<div class="trow in" {at(0.5 + i * 0.45)}><div class="tl">{esc(r[0])}</div>'
            f'<div class="tv one">{mark(r[1])}</div><div class="tv two"><span class="mk">{esc(r[2].replace("**", ""))}</span></div></div>'
            for i, r in enumerate((sc.get("rows") or [])[:3]))
        note = f'<div class="hand in" {at(0.8 + len(sc.get("rows") or []) * 0.45)}>{esc(sc["note"])}</div>' if sc.get("note") else ""
        return (f'<section class="scene twins" {a}><div class="eyebrow in" {at(0.05)}>쌍둥이 체크</div>'
                f'<div class="ptitle in" {at(0.15)}>{mark(sc.get("title") or "쌍둥이면")}</div>'
                f'<div class="card"><div class="thead in" {at(0.35)}><span></span><span>한 명</span><span>쌍둥이</span></div>{rows}</div>{note}</section>')
    if t == "checks":
        items = "".join(f'<div class="ck in pop" {at(0.45 + i * 0.5)}><div class="box">{CHECK}</div><div class="ct">{mark(x)}</div></div>'
                        for i, x in enumerate(L(sc.get("items"))[:4]))
        return (f'<section class="scene checks" {a}><div class="eyebrow in" {at(0.05)}>{esc(sc.get("eyebrow") or "체크리스트")}</div>'
                f'<div class="ptitle in" {at(0.15)}>{mark(sc.get("title"))}</div><div class="cks">{items}</div></section>')
    if t == "cta":
        lines = "".join(f'<div class="cline in pop" {at(0.2 + i * 0.2)}>{mark(ln, sc.get("highlight"))}</div>'
                        for i, ln in enumerate(L(sc.get("lines"))))
        note = sc.get("link_note") or sc.get("share")   # share: 누구에게 보내면 좋은지 한 줄
        link = f'<div class="hand in" {at(0.9)}>{esc(note)}</div>' if note else ""
        src = f'<div class="src in" {at(1.0)}>{esc(spec.get("source"))}</div>' if spec.get("source") else ""
        return (f'<section class="scene cta" {a}><div class="clines">{lines}</div>{link}'
                f'<div class="btns in" {at(0.7)}><span class="btn">저장</span><span class="btn">공유</span><span class="btn ghost">팔로우</span></div>{src}</section>')
    if t == "list":   # B형 루프 리스트: 항목이 step초마다 하나씩 쌓임
        step = float(sc.get("step", 0.9))
        items = ""
        for i, it in enumerate(L(sc.get("items"))[:5]):
            main_, sub = (it[0], it[1] if len(it) > 1 else "") if isinstance(it, list) else (it, "")
            items += (f'<div class="li in pop" {at(0.35 + i * step)}><span class="no">{i + 1}</span>'
                      f'<span class="lt">{mark(main_)}</span>{f"<span class=lv>{mark(sub)}</span>" if sub else ""}</div>')
        eb = f'<div class="eyebrow in" {at(0.05)}>{esc(sc["eyebrow"])}</div>' if sc.get("eyebrow") else ""
        return (f'<section class="scene list" {a}>{eb}<div class="ptitle in" {at(0.12)}>{mark(sc.get("title"))}</div>'
                f'<div class="lis">{items}</div></section>')
    if t == "ask":    # C형 체크 질문: 예/아니오 중 하나가 눌림
        pick = sc.get("a", "예")
        btn = lambda s: f'<span class="yn{" on" if s == pick else ""}" data-press="{start + float(sc.get("press", 1.3)):.2f}">{s}</span>'
        no = f'<div class="eyebrow in" {at(0.05)}>{esc(sc["n"])}</div>' if sc.get("n") else ""
        note = f'<div class="hand in" {at(float(sc.get("press", 1.3)) + 0.3)}>{esc(sc["note"])}</div>' if sc.get("note") else ""
        return (f'<section class="scene ask" {a}>{no}<div class="q in pop" {at(0.12)}>{mark(sc.get("q"))}</div>'
                f'<div class="yns in" {at(0.45)}>{btn("예")}{btn("아니오")}</div>{note}</section>')
    raise ValueError(f"알 수 없는 장면: {t}")


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{word-break:keep-all;width:1080px;height:1920px;overflow:hidden;font-family:'Noto Sans KR',sans-serif;color:#2B3040;
  background-color:#FBF7EF;background-image:radial-gradient(#E3DACA 3px,transparent 3.3px);background-size:60px 60px;background-position:30px 30px}
.rings{position:absolute;left:0;top:0;bottom:0;width:70px;background:#F6F0E4;border-right:4px solid #E6DFD1;display:flex;flex-direction:column;justify-content:space-around;align-items:center;padding:80px 0;z-index:1}
.rings i{display:block;width:30px;height:30px;border-radius:50%;border:4px solid #2B3040;background:#fff}
.brand{position:absolute;left:120px;top:150px;display:flex;align-items:center;gap:14px;font-weight:900;font-size:36px;z-index:5}
.bar{position:absolute;left:120px;right:70px;top:222px;height:10px;border-radius:5px;background:rgba(43,48,64,.1);z-index:5;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:#F5C84C}
.ad{position:absolute;left:120px;top:262px;z-index:6;font-size:34px;font-weight:900;color:#2B3040;background:#fff;border:4px solid #2B3040;border-radius:16px;padding:10px 24px;opacity:0}
.scene{position:absolute;inset:0;opacity:0;padding:320px 90px 740px 140px;display:flex;flex-direction:column;justify-content:center;overflow:hidden}
.mk{background:linear-gradient(transparent 56%,#F5C84C 56%,#F5C84C 92%,transparent 92%);padding:0 6px;margin:0 -6px}
.chips{display:flex;gap:18px;margin-bottom:44px}
.chip{font-size:44px;font-weight:900;padding:12px 32px;border-radius:999px;background:#2B3040;color:#F5C84C}
.chip.c2{background:transparent;color:#2B3040;border:4px solid #2B3040;padding:8px 28px}
.hlines{font-size:158px;font-weight:900;line-height:1.14;letter-spacing:-5px}
.hsub{margin-top:44px;font-size:52px;font-weight:600;line-height:1.4;color:#4A4D58}
.slines{font-size:128px;font-weight:900;line-height:1.18;letter-spacing:-4px}
.hand{font-family:'Hand';font-size:78px;color:#E8735F;margin-top:48px;transform-origin:left center}
.eyebrow{align-self:flex-start;font-size:42px;font-weight:900;background:#9DBB97;padding:10px 26px;border-radius:14px;margin-bottom:26px}
.ptitle{font-size:100px;font-weight:900;line-height:1.18;letter-spacing:-3px;margin-bottom:46px}
.card{position:relative;background:#fff;border:5px solid #2B3040;border-radius:40px;padding:22px 48px;box-shadow:14px 16px 0 #2B3040}
.row{display:flex;gap:30px;padding:34px 0;border-top:4px dashed #E6DFD1;align-items:flex-start}
.row:first-child{border-top:none}
.rl{flex:0 0 190px;font-size:42px;font-weight:700;color:#6B6A66;padding-top:6px}
.rv{font-size:56px;font-weight:900;line-height:1.3;letter-spacing:-1px}
.ptext{margin-top:40px;font-size:46px;font-weight:600;line-height:1.45}
.thead,.trow{display:grid;grid-template-columns:1.1fr 1fr 1fr;gap:16px;align-items:center}
.thead{font-size:38px;font-weight:900;color:#6B6A66;padding:18px 0 10px}
.thead span:last-child{color:#E8735F}
.trow{padding:30px 0;border-top:4px dashed #E6DFD1}
.tl{font-size:42px;font-weight:700;color:#4A4D58}
.tv{font-size:54px;font-weight:900;letter-spacing:-1px}
.tv.one{color:#6B6A66}
.twins .ptitle{margin-bottom:36px}.twins .trow{padding:24px 0}.twins .hand{margin-top:30px}
.cks{display:flex;flex-direction:column;gap:34px}
.ck{display:flex;gap:30px;align-items:center}
.box{width:96px;height:96px;flex-shrink:0;border:6px solid #2B3040;border-radius:20px;background:#fff;display:flex;align-items:center;justify-content:center}
.ct{font-size:60px;font-weight:900;letter-spacing:-1px;line-height:1.25}
.cta{align-items:flex-start}
.cta .hand{margin-top:30px;font-size:66px}.cta .btns{margin-top:40px}.cta .src{margin-top:30px}
.clines{font-size:116px;font-weight:900;line-height:1.18;letter-spacing:-4px}
.btns{display:flex;gap:20px;margin-top:56px}
.btn{font-size:46px;font-weight:900;padding:24px 46px;border-radius:999px;background:#2B3040;color:#FBF7EF}
.btn.ghost{background:#fff;color:#2B3040;border:5px solid #2B3040;padding:19px 41px}
.src{margin-top:44px;font-size:34px;color:#6B6A66;font-weight:500}
.narrator{position:absolute;right:60px;bottom:430px;width:540px;height:302px;z-index:6}
.bubble{position:absolute;right:360px;bottom:745px;z-index:6;display:flex;gap:12px;opacity:0}
.bubble i{width:18px;height:18px;border-radius:50%;background:#2B3040;display:block}
.lis{display:flex;flex-direction:column;gap:16px}
.li{display:flex;align-items:center;gap:26px;background:#fff;border:5px solid #2B3040;border-radius:26px;padding:14px 28px;box-shadow:7px 8px 0 #2B3040}
.no{flex:0 0 64px;height:64px;border-radius:50%;background:#2B3040;color:#F5C84C;font-size:44px;font-weight:900;display:flex;align-items:center;justify-content:center}
.lt{font-size:50px;font-weight:900;letter-spacing:-1px;line-height:1.2}
.lv{margin-left:auto;font-size:44px;font-weight:800;color:#E8735F;white-space:nowrap;padding-left:16px}
.list .ptitle{font-size:80px;margin-bottom:28px}.list .eyebrow{margin-bottom:18px}
.q{font-size:104px;font-weight:900;line-height:1.2;letter-spacing:-3px;margin-bottom:60px}
.yns{display:flex;gap:30px}
.yn{font-size:64px;font-weight:900;padding:26px 64px;border-radius:999px;border:6px solid #2B3040;background:#fff;color:#2B3040}
.yn.lit{background:#2B3040;color:#F5C84C}
.in{opacity:0}
"""

JS = """
const ease=x=>1-Math.pow(1-x,3);
const back=x=>{const c=1.70158,c3=c+1;return 1+c3*Math.pow(x-1,3)+c*Math.pow(x-1,2)};
const cl=x=>Math.max(0,Math.min(1,x));
const TOTAL=__TOTAL__, AD_END=__AD__, LOOP=__LOOP__;
function fmt(n){return Math.round(n).toLocaleString('ko-KR')}
window.renderAt=function(t){
  document.querySelectorAll('.scene').forEach(s=>{
    const a=+s.dataset.s,e=+s.dataset.e;
    const first=a<0.01;
    // 루프 모드: 마지막 0.4초에 첫 장면(훅)으로 돌아가 영상 끝 = 처음처럼 이어짐
    const back_=LOOP?cl((t-(TOTAL-0.45))/0.35):0;
    let o=(first?1:cl((t-a)/0.25))*(e>=TOTAL-0.01?1:cl((e-t)/0.25));
    if(LOOP){ if(first) o=Math.max(o,back_); else o=o*(1-back_); }
    s.style.opacity=o; s.style.visibility=o>0?'visible':'hidden';
    s.style.transform=first?'none':'translateX('+((1-ease(cl((t-a)/0.35)))*60)+'px)';
  });
  const F0=document.querySelector('.scene');
  document.querySelectorAll('.in').forEach(el=>{
    const p=(LOOP&&F0.contains(el))?1:cl((t-(+el.dataset.in))/0.4);   // 루프: 첫 장면은 처음부터 완성된 모습
    const k=el.classList.contains('pop')?back(p):ease(p);
    el.style.opacity=ease(p);
    el.style.transform=el.classList.contains('pop')?'translateY('+((1-k)*70)+'px) scale('+(0.9+0.1*k)+')':'translateY('+((1-k)*50)+'px)';
  });
  document.querySelectorAll('.mk').forEach(m=>{
    const host=m.closest('[data-in]'); const st=host?+host.dataset.in+0.35:0;
    const p=(LOOP&&F0.contains(m))?1:ease(cl((t-st)/0.5));
    m.style.backgroundSize=(p*100)+'% 100%'; m.style.backgroundRepeat='no-repeat';
  });
  document.querySelectorAll('[data-count]').forEach(el=>{
    const p=cl((t-(+el.dataset.cs))/(+el.dataset.cd));
    const f0=+(el.dataset.from||0); el.textContent=fmt((+el.dataset.count)*(f0+(1-f0)*ease(p)));
  });
  document.querySelectorAll('[data-press]').forEach(el=>{
    const p=cl((t-(+el.dataset.press))/0.18);
    if(el.classList.contains('on')){ el.classList.toggle('lit',p>0.5); el.style.transform='scale('+(1-0.08*Math.sin(Math.PI*p))+')'; }
  });
  document.querySelector('.bar').style.display=LOOP?'none':''; document.querySelector('.bar i').style.width=(100*cl(t/TOTAL))+'%';
  const ad=document.querySelector('.ad'); if(ad){ad.style.opacity=cl((AD_END-t)/0.3);}
  const v=MOUTH.length?(MOUTH[Math.min(MOUTH.length-1,Math.round(t*30))]||0):0;
  const n=document.querySelector('.narrator');
  n.style.transform='translateY('+(Math.sin(t*3)*6 - v*10)+'px)';
  const a1=document.querySelector('.acc1'),a2=document.querySelector('.acc2');
  const w1=Math.sin(t*9)*v, w2=Math.sin(t*9+1.6)*v;
  a1.setAttribute('transform','translate(0 '+(-Math.abs(w1)*7).toFixed(2)+')');
  a2.setAttribute('transform','translate(0 '+(-Math.abs(w2)*7).toFixed(2)+')');
  document.querySelector('.tw1').style.transform='rotate('+(Math.sin(t*2.2)*2+w1*4).toFixed(2)+'deg)';
  document.querySelector('.tw2').style.transform='rotate('+(Math.sin(t*2.2+1)*2+w2*4).toFixed(2)+'deg)';
  const b=document.querySelector('.bubble'); b.style.opacity=v>0.05?1:0;
  b.querySelectorAll('i').forEach((d,k)=>{d.style.transform='translateY('+(-Math.max(0,Math.sin(t*10-k*0.9))*12*v)+'px)'});
};
"""


BGM_DIR = HERE / "bgm"
BGM_DB = -13  # 배경음악 기본 크기 (목소리 대비). 목소리 나올 때는 덕킹으로 더 작아짐


def pick_bgm(spec):
    """원고 "bgm": "sunny"|"cozy"|"bounce" → 그 곡, false → 없음, 생략 → slug로 골고루 돌려씀."""
    b = spec.get("bgm", "auto")
    if b is False or b in ("", "none", "off"):
        return None
    files = sorted(BGM_DIR.glob("*.mp3"))
    if not files:
        return None
    if b != "auto":
        f = BGM_DIR / f"{b}.mp3"
        if not f.exists():
            raise SystemExit(f"배경음악 없음: {b} (있는 곡: {', '.join(x.stem for x in files)})")
        return f
    import zlib
    return files[zlib.crc32(spec["slug"].encode()) % len(files)]


def audio_len(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def voice_files(spec):
    """장면별 음성 파일. 앞뒤 무음을 잘라 장면 사이가 끊기지 않게 한다."""
    v = str(spec.get("voice") or "").split(" ")[0].strip()
    if not v:
        return [None] * len(spec["scenes"])
    d = ROOT / v
    speed = float(spec.get("voice_speed", 1.0))
    tmp = HERE / "reels" / spec["slug"] / "_voice"
    tmp.mkdir(parents=True, exist_ok=True)
    trim = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
    if abs(speed - 1.0) > 0.01:
        trim += f",atempo={speed}"
    out = []
    for i in range(len(spec["scenes"])):
        f = d / f"{i + 1:02d}.mp3"
        if not f.exists():
            out.append(None)
            continue
        g = tmp / f"{i + 1:02d}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(f), "-af", trim, "-ar", "44100", str(g)], check=True)
        out.append(g)
    return out


def timeline(spec):
    """음성이 있으면 장면 길이 = 음성 길이 + 짧은 여백 (원고 dur는 무시, 'min'이 있으면 최소 길이).
    음성이 없으면 원고 dur(기본 4초)."""
    vf = voice_files(spec)
    t, out = 0.0, []
    for i, (sc, f) in enumerate(zip(spec["scenes"], vf)):
        if f:
            d = max(float(sc.get("min", 1.8)), LEAD + audio_len(f) + TAIL)
        elif "dur" in sc:
            d = float(sc["dur"])
        elif sc.get("type") == "list":
            d = 0.35 + len(L(sc.get("items"))[:5]) * float(sc.get("step", 0.9)) + 1.3
        elif sc.get("type") == "ask":
            d = 2.8
        else:
            d = 4.0
        if i == len(vf) - 1:
            d += 0.45 if spec.get("loop") else END_HOLD
        out.append((t, d, f))
        t += d
    return out, t


def envelope(tl, total):
    import numpy as np
    n = int(round(total * FPS))
    env = np.zeros(n)
    sr, hop = 16000, 16000 // FPS
    for start, _, f in tl:
        if not f:
            continue
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
        k = len(a) // hop
        rms = np.sqrt((a[:k * hop].reshape(k, hop) ** 2).mean(axis=1))
        off = int(round((start + LEAD) * FPS))
        env[off:off + k] = rms[: max(0, min(k, n - off))]
    if env.max() > 0:
        env = env / (np.percentile(env[env > 0], 90) + 1e-6)
    env = np.clip(env, 0, 1)
    env[env < 0.12] = 0
    sm = env.copy()
    for i in range(1, n):
        sm[i] = max(env[i], sm[i - 1] * 0.6)
    return [round(float(x), 3) for x in sm]


def build(spec):
    tl, total = timeline(spec)
    voiced = any(f for _, _, f in tl)
    scenes = "".join(scene_html(sc, i, t, t + d, spec) for i, (sc, (t, d, f)) in enumerate(zip(spec["scenes"], tl)))
    mouth = envelope(tl, total) if voiced else []
    ad_end = min(total, max(3.5, tl[0][1])) if spec.get("ad") else -1
    ad = '<div class="ad">광고 · 링크 구매 시 수수료를 받아요</div>' if spec.get("ad") else ""
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_face()}{CSS}</style></head><body>
<div class="rings">{'<i></i>' * 16}</div>
<div class="brand">{heads_icon()}<span>두아이 살림노트</span></div>
<div class="bar"><i></i></div>{ad}
{scenes}
<div class="bubble"><i></i><i></i><i></i></div>
<div class="narrator">{twins_svg()}</div>
<script>const MOUTH={json.dumps(mouth)};{JS.replace('__TOTAL__', f'{total:.3f}').replace('__AD__', f'{ad_end:.3f}').replace('__LOOP__', 'true' if spec.get('loop') else 'false')}</script></body></html>"""
    return page, total, tl


FIT_JS = """
() => { const warn=[];
  document.querySelectorAll('.scene').forEach((s,i)=>{ s.style.opacity=1; s.style.visibility='visible';
    s.querySelectorAll('.in').forEach(e=>{e.style.opacity=1;e.style.transform='none'});
    // 훅·마무리 한 줄이 넘쳐 두 줄로 접히면 글자 크기를 줄여 원고 줄 수(2줄)를 지킨다
    s.querySelectorAll('.hlines,.clines').forEach(h=>{ const ls=[...h.querySelectorAll('.hline,.cline')]; ls.forEach(e=>e.style.whiteSpace='nowrap');
      const need=Math.max(...ls.map(e=>e.scrollWidth)), have=Math.min(h.clientWidth, s.clientWidth-230), k=have/need*0.96;
      if(need>have && k>=0.6){ const fs=parseFloat(getComputedStyle(h).fontSize); h.style.fontSize=Math.floor(fs*k)+'px'; }
      else if(need>have) ls.forEach(e=>e.style.whiteSpace=''); });
    const kids=[...s.children];
    const box=()=>{const r=kids.map(k=>k.getBoundingClientRect());return {top:Math.min(...r.map(x=>x.top)),bottom:Math.max(...r.map(x=>x.bottom))}};
    // 말하는 쌍둥이(말풍선 포함) 윗선 1140px 아래로 내려가면 글을 위로 올린다 (위 260px까지)
    let bx=box(); const over=bx.bottom-1140;
    if(over>0){ const up=Math.min(over, Math.max(0,bx.top-260)); s.style.paddingBottom=(740+2*up)+'px'; bx=box();
      if(bx.bottom>1140) warn.push('scene '+(i+1)+': 캐릭터와 겹침 ('+Math.round(bx.bottom)+'px) · 문구를 줄이세요'); }
    const right=Math.max(...kids.map(k=>k.getBoundingClientRect().right));
    const b2=bx.bottom;
    if(b2>1920-430) warn.push('scene '+(i+1)+': 아래 가림 영역 침범 ('+Math.round(b2)+'px)');
    if(right>1080-40) warn.push('scene '+(i+1)+': 오른쪽 넘침');
    s.querySelectorAll('.hline,.sline,.cline,.rv,.ct,.tv,.lt,.li').forEach(e=>{ if(e.scrollWidth>e.clientWidth+2) warn.push('scene '+(i+1)+': 줄 넘침 '+e.textContent.slice(0,10)); });
    s.style.opacity=0; s.style.visibility='hidden'; s.querySelectorAll('.in').forEach(e=>{e.style.opacity='';e.style.transform=''});
  }); return warn; }
"""


def main(path):
    spec = json.loads(Path(path).read_text())
    slug = spec["slug"]
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise SystemExit("slug는 영문 소문자·숫자·하이픈만")
    out = HERE / "reels" / slug
    frames = out / "_frames"
    shutil.rmtree(frames, ignore_errors=True)
    shutil.rmtree(out / "_voice", ignore_errors=True)
    frames.mkdir(parents=True)
    page, total, tl = build(spec)
    # 자리표시자·예시 문구가 남아 있으면 경고 (샘플 원고는 제외)
    holders = []
    if not slug.startswith("sample"):
        def strings(o):
            if isinstance(o, str):
                yield o
            elif isinstance(o, dict):
                for v in o.values():
                    yield from strings(v)
            elif isinstance(o, list):
                for v in o:
                    yield from strings(v)
        txt = "\n".join(strings(spec["scenes"]))
        for pat in [r"○○", r"OO", r"TBD", r"\[[^\]]*(?:N|가격|금액|날짜|링크)[^\]]*\]", r"예시", r"XX", r"\?\?"]:
            m = re.search(pat, txt)
            if m:
                holders.append(f"자리표시자 '{m.group(0)}' — 실제 값으로 바꾸거나 칸을 빼세요")

    from playwright.sync_api import sync_playwright
    n = int(round(total * FPS))
    stills, warns = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.set_content(page)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        warns = pg.evaluate(FIT_JS)
        for f in range(n):
            pg.evaluate(f"renderAt({f / FPS:.4f})")
            pg.screenshot(path=str(frames / f"{f:05d}.jpg"), type="jpeg", quality=92)
        for i, (t0, d, _) in enumerate(tl):
            sc = spec["scenes"][i]
            at_ = t0 + d - (0.75 if spec.get("loop") and i == len(tl) - 1 else 0.3) if sc.get("type") in ("list", "ask") else t0 + min(d - 0.3, 2.8)
            pg.evaluate(f"renderAt({at_:.3f})")
            fp = out / f"_still{i}.jpg"
            pg.screenshot(path=str(fp), type="jpeg", quality=90)
            stills.append(fp)
        b.close()

    mp4 = out / "reel.mp4"
    voices = [(t0, f) for t0, _, f in tl if f]
    bgm = pick_bgm(spec)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "%05d.jpg"),
           "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    if bgm:
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
    first = 3 if bgm else 2
    for _, f in voices:
        cmd += ["-i", str(f)]
    fl = "".join(f"[{k + first}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={int((t0 + LEAD) * 1000)}:all=1[v{k}];"
                 for k, (t0, _) in enumerate(voices))
    fl += "[1:a]" + "".join(f"[v{k}]" for k in range(len(voices))) + \
          f"amix=inputs={len(voices) + 1}:normalize=0:duration=first[vox];"
    if bgm:
        # 배경음악: 목소리보다 한참 작게, 목소리가 나올 때는 더 줄이고(덕킹) 끝에서 서서히 사라짐
        fd = 0.25 if spec.get("loop") else 1.6   # 루프 영상은 소리도 끊김 없이 이어지게 짧게
        fo = max(0.0, total - fd)
        vol = BGM_DB + (7 if not voices else 0)   # 음성 없는 영상은 배경음악이 주인공
        fl += (f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
               f"volume={vol}dB,afade=t=in:d={0.05 if spec.get('loop') else 0.4},afade=t=out:st={fo:.2f}:d={fd}[bg];")
        if voices:
            fl += ("[vox]asplit=2[vx][key];[bg][key]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=450:makeup=1[bgd];"
                   "[vx][bgd]amix=inputs=2:normalize=0:duration=first[mix];")
        else:
            fl += "[vox][bg]amix=inputs=2:normalize=0:duration=first[mix];"
    else:
        fl += "[vox]anull[mix];"
    fl += f"[mix]loudnorm=I=-15:TP=-1.5:LRA=11,aresample=44100,atrim=0:{total:.3f}[aout]"
    cmd += ["-filter_complex", fl, "-map", "0:v", "-map", "[aout]"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    shutil.rmtree(frames)
    shutil.rmtree(out / "_voice", ignore_errors=True)

    from PIL import Image
    shutil.copy(stills[0], out / "cover.jpg")
    ims = [Image.open(s) for s in stills]
    tw = 300
    th_ = int(H * tw / W)
    sheet = Image.new("RGB", (tw * len(ims) + 16 * (len(ims) + 1), th_ + 32), "#D9D4C8")
    for i, im in enumerate(ims):
        sheet.paste(im.resize((tw, th_), Image.LANCZOS), (16 + i * (tw + 16), 16))
    sheet.save(out / "preview.jpg", quality=88)
    for s in stills:
        s.unlink()

    base = f"{RAW_BASE}/2kids/reels/{slug}"
    manifest = {"slug": slug, "duration": round(total, 2), "voiced": bool(voices), "bgm": bgm.stem if bgm else None, "video": f"{base}/reel.mp4",
                "cover": f"{base}/cover.jpg", "size_mb": round(mp4.stat().st_size / 1e6, 2), "warnings": holders + warns}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
