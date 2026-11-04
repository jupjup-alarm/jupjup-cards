"""효도알람 장면 템플릿 → hyperframes HTML.

html(scene, times, dur, portrait) : times = 문장 시작 시각(초) 목록, dur = 장면 길이(초)
- data-at="k" 가 붙은 요소는 k번째 문장이 시작될 때 나타난다.
- 글자 크기는 시니어 기준: 롱폼 본문 52px 이상·제목 80px, 숏츠 본문 48px 이상·제목 76px, 숫자 강조 200px 이상.
- 화면 글자는 자막 자리(롱폼 y>820, 숏츠 y>1280) 위에서 끝나야 한다.
"""
import html as H
import json
import re


C = {"bg": "#FFF8EC", "card": "#FFFFFF", "ink": "#1F2A44", "sub": "#5B6473", "green": "#1F5C4B",
     "greenTint": "#E3F1EB", "orange": "#E8693A", "amber": "#F2B544", "amberTint": "#FDEFD2", "line": "#E9DFCC"}

BELL = ('<svg viewBox="0 0 24 24" width="1em" height="1em" style="vertical-align:-0.12em"><path fill="currentColor" '
        'd="M12 2a1.5 1.5 0 0 1 1.5 1.5v.6A6.5 6.5 0 0 1 18.5 10.5v4.2l1.8 2.4a.8.8 0 0 1-.6 1.3H4.3a.8.8 0 0 1-.6-1.3'
        'l1.8-2.4v-4.2A6.5 6.5 0 0 1 10.5 4.1v-.6A1.5 1.5 0 0 1 12 2zm-2.2 18h4.4a2.2 2.2 0 0 1-4.4 0z"/></svg>')


def e(s):
    return H.escape(str(s))


def css(portrait):
    W, Hh = (1080, 1920) if portrait else (1920, 1080)
    base = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{Hh}px;overflow:hidden;background:{C['bg']}}}
body{{font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;color:{C['ink']};word-break:keep-all}}
#root{{position:absolute;inset:0}}
.stage{{position:absolute;inset:0}}
.brand{{position:absolute;left:60px;top:44px;background:{C['green']};color:#fff;font-weight:900;font-size:40px;padding:10px 28px;border-radius:44px}}
.brand b{{color:{C['amber']};font-weight:900;margin-left:4px}}
.chapter{{position:absolute;right:64px;top:56px;font-size:38px;color:{C['sub']};font-weight:700}}
.title{{font-size:{76 if portrait else 80}px;font-weight:900;letter-spacing:-1px;line-height:1.2}}
.card{{background:{C['card']};border-radius:28px;box-shadow:0 6px 0 {C['line']}}}
.pill{{display:inline-block;border-radius:999px;font-weight:800}}
.muted{{color:{C['sub']}}}
.orange{{color:{C['orange']}}}
.green{{color:{C['green']}}}
.char{{position:absolute;object-fit:contain}}
"""
    return base


def chrome(chapter):
    return f'<div class="brand">{BELL} 효도<b>알람</b></div><div class="chapter">{e(chapter)}</div>'


# ---------- 장면별 본문 ----------

def body_hook(s, P):
    d = s["data"]
    if P:
        return f"""
<div style="position:absolute;left:70px;right:70px;top:230px;text-align:center">
 <div data-at="0" class="pill" style="font-size:56px;border:5px solid {C['orange']};color:{C['orange']};padding:12px 38px">{e(d['badge'])}</div>
 <div data-at="1" data-fit style="font-size:200px;font-weight:900;color:{C['orange']};letter-spacing:-6px;margin-top:40px;line-height:1;white-space:nowrap">{e(d['big'])}</div>
 <div data-at="2" data-fit style="font-size:86px;font-weight:900;margin-top:40px;line-height:1.25;white-space:nowrap">{e(d['line'])}</div>
</div>
<div data-at="0" style="position:absolute;left:310px;top:800px;width:460px;height:460px;border-radius:50%;background:{C['greenTint']};overflow:hidden">
 <img src="char_base.png" style="position:absolute;left:40px;top:56px;width:380px">
</div>"""
    return f"""
<div style="position:absolute;left:110px;top:190px;width:1180px">
 <div data-at="0" class="pill" style="font-size:58px;border:5px solid {C['orange']};color:{C['orange']};padding:12px 40px">{e(d['badge'])}</div>
 <div data-at="1" data-fit style="font-size:220px;font-weight:900;color:{C['orange']};letter-spacing:-8px;margin-top:40px;line-height:1;white-space:nowrap">{e(d['big'])}</div>
 <div data-at="2" data-fit style="font-size:90px;font-weight:900;margin-top:46px;white-space:nowrap">{e(d['line'])}</div>
</div>
<div data-at="0" style="position:absolute;left:1260px;top:170px;width:560px;height:560px;border-radius:50%;background:{C['greenTint']};overflow:hidden">
 <img src="char_base.png" style="position:absolute;left:50px;top:60px;width:460px">
</div>"""


def body_summary(s, P):
    rows = s["data"]["rows"]
    fs, lw = (52, 190) if P else (60, 230)
    items = "".join(
        f'<div data-at="{i + 1}" class="card" style="display:flex;align-items:center;gap:30px;padding:30px 40px;margin-top:26px">'
        f'<span class="pill" style="background:{C["green"]};color:#fff;font-size:{fs - 6}px;padding:10px 0;min-width:{lw}px;text-align:center">{e(a)}</span>'
        f'<span style="font-size:{fs}px;font-weight:700;line-height:1.35">{e(b)}</span></div>' for i, (a, b) in enumerate(rows))
    box = "left:70px;right:70px;top:230px" if P else "left:130px;right:130px;top:170px"
    return f'<div style="position:absolute;{box}"><div data-at="0" class="title">3줄 요약</div>{items}</div>'


def body_official(s, P):
    d = s["data"]
    if P:
        frame = "left:60px;right:60px;top:240px;height:900px"
    else:
        frame = "left:180px;right:180px;top:150px;height:640px"
    return f"""
<div class="card" style="position:absolute;{frame};overflow:hidden;border:4px solid {C['line']}">
 <img id="shot" src="official.png" style="width:100%;height:100%;object-fit:cover;object-position:center;transform-origin:47% 50%">
</div>
<div data-at="0" class="pill" style="position:absolute;{'left:60px;top:1170px' if P else 'left:180px;top:800px'};background:{C['ink']};color:#fff;font-size:42px;padding:10px 30px">출처: {e(d['label'])}</div>"""


def body_check(s, P):
    items = s["data"]["items"]
    fs = 50 if P else 58
    rows = "".join(
        f'<div data-at="{i + 1}" class="card" style="display:flex;align-items:center;gap:28px;padding:{24 if P else 20}px 34px;margin-top:{24 if P else 18}px">'
        f'<span style="flex:none;width:{86 if P else 92}px;height:{86 if P else 92}px;border-radius:18px;border:6px solid {C["green"]};position:relative">'
        f'<span data-check="{i + 1}" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;'
        f'background:{C["green"]};color:#fff;font-size:64px;font-weight:900">✓</span></span>'
        f'<span style="font-size:{fs}px;font-weight:700;line-height:1.35">{e(t)}</span></div>' for i, t in enumerate(items))
    if P:
        return f'<div style="position:absolute;left:60px;right:60px;top:230px"><div data-at="0" class="title">우리 자녀, 해당될까요?</div>{rows}</div>'
    return (f'<div style="position:absolute;left:110px;width:1400px;top:136px"><div data-at="0" class="title">우리 자녀, 해당될까요?</div>{rows}</div>'
            f'<img data-at="0" class="char" src="char_point.png" style="left:1520px;top:260px;height:540px">')


def body_table(s, P):
    d = s["data"]
    at = d.get("at", list(range(1, len(d["rows"]) + 1)))
    fs = 48 if P else 56
    rows = "".join(
        f'<div data-at="{at[i]}" style="display:flex;border-bottom:3px solid {C["line"]}">'
        f'<div style="flex:none;width:{320 if P else 470}px;background:{C["greenTint"]};padding:{18 if P else 13}px 30px;font-size:{fs - 4}px;font-weight:800;color:{C["green"]}">{e(a)}</div>'
        f'<div style="padding:{18 if P else 13}px 34px;font-size:{fs}px;font-weight:700;line-height:1.3;background:#fff;flex:1">{e(b)}</div></div>'
        for i, (a, b) in enumerate(d["rows"]))
    notes = ""
    if d.get("note2"):
        notes += f'<div data-at="{d.get("note2_at", 3)}" style="margin-top:18px;font-size:{fs - 10}px;font-weight:800;line-height:1.3;color:{C["orange"]}">※ {e(d["note2"])}</div>'
    if d.get("note"):
        notes += f'<div data-at="{d.get("note_at", len(d["rows"]) + 1)}" style="margin-top:14px;padding:14px 24px;background:{C["amberTint"]};border-radius:16px;font-size:{fs - 12}px;font-weight:800;line-height:1.3">예정: {e(d["note"])}</div>'
    box = "left:60px;right:60px;top:230px" if P else "left:110px;right:110px;top:130px"
    return (f'<div style="position:absolute;{box}"><div data-at="0" class="title">{e(d["title"])}</div>'
            f'<div class="card" style="margin-top:24px;overflow:hidden">{rows}</div>{notes}</div>')


def won(v):
    """원 → '1,800만 원' / '108만 원'."""
    man = v / 10000
    return (f"{man:,.0f}만 원" if man == int(man) else f"{man:,.1f}만 원")


def body_calc_sum(s, P):
    """받는 돈 계산: items[{label, monthly}] × months (적금형이 아닌 수당·연금용, 2026-11-04 S-0002)."""
    d = s["data"]
    m = d["months"]
    top = max(it["monthly"] for it in d["items"]) * m
    track = 760 if P else 1100
    at = d.get("at", list(range(1, len(d["items"]) + 1)))
    bars = ""
    for i, it in enumerate(d["items"]):
        tot = it["monthly"] * m
        per = (f'<span class="muted" style="font-weight:700">· 한 달 {it["monthly"]:,}원 × {m}달</span>' if m > 1 else '')
        bars += (f'<div data-at="{at[i]}" style="margin-top:{44 if P else 40}px">'
                 f'<div style="font-size:{48 if P else 54}px;font-weight:800;margin-bottom:14px">{e(it["label"])} {per}</div>'
                 f'<div style="display:flex;align-items:center;height:110px">'
                 f'<div data-grow="{at[i]}" style="width:{track * tot / top:.0f}px;height:110px;background:{C["orange"]};border-radius:18px;transform-origin:left center"></div>'
                 f'<div style="margin-left:22px;font-size:{60 if P else 72}px;font-weight:900;color:{C["orange"]};white-space:nowrap">{tot:,}원</div>'
                 f'</div></div>')
    box = "left:60px;right:60px;top:230px" if P else "left:130px;right:130px;top:170px"
    na = d.get("note_at", len(d["items"]) + 1)
    return (f'<div style="position:absolute;{box}"><div data-at="0" class="title">{e(d["title"])}</div>{bars}'
            f'<div data-at="{na}" class="muted" style="margin-top:40px;font-size:{44 if P else 48}px;font-weight:700">※ {e(d["note"])}</div></div>')


def body_calc(s, P):
    d = s["data"]
    if "items" in d:
        return body_calc_sum(s, P)
    paid = d["monthly"] * d["months"]
    top = max(paid * (1 + r["rate"]) for r in d["rates"])
    track = 700 if P else 1160
    bars = ""
    for r in d["rates"]:
        add = paid * r["rate"]
        bw, aw = track * paid / top, track * add / top
        bars += (f'<div style="margin-top:{44 if P else 40}px">'
                 f'<div data-at="1" style="font-size:{48 if P else 54}px;font-weight:800;margin-bottom:14px">{e(r["label"])} <span class="muted" style="font-weight:700">· 기여금 {int(r["rate"] * 100)}%</span></div>'
                 f'<div style="display:flex;align-items:center;height:110px">'
                 f'<div data-at="1" style="width:{bw:.0f}px;height:110px;background:{C["greenTint"]};border-radius:18px 0 0 18px;display:flex;align-items:center;padding-left:28px;font-size:{44 if P else 50}px;font-weight:800;color:{C["green"]}">낸 돈 {won(paid)}</div>'
                 f'<div data-grow="2" style="width:{aw:.0f}px;height:110px;background:{C["orange"]};border-radius:0 18px 18px 0;transform-origin:left center"></div>'
                 f'<div data-at="2" style="margin-left:22px;font-size:{60 if P else 72}px;font-weight:900;color:{C["orange"]};white-space:nowrap">+{won(add)}</div>'
                 f'</div></div>')
    box = "left:60px;right:60px;top:230px" if P else "left:130px;right:130px;top:170px"
    title = f'월 {won(d["monthly"])}씩 {d["months"] // 12}년 넣으면'
    return (f'<div style="position:absolute;{box}"><div data-at="0" class="title">{e(title)}</div>{bars}'
            f'<div data-at="3" class="muted" style="margin-top:40px;font-size:{44 if P else 48}px;font-weight:700">※ {e(d["note"])}</div></div>')


def body_apply(s, P):
    d = s["data"]
    at = d.get("at", [1, 2, 2])
    fs = 50 if P else 52
    # 단계 카드: 번호 + 글자를 한 줄로(세로·가로 공통)
    steps = "".join(
        f'<div data-at="{at[i]}" class="card" style="padding:{22 if P else 24}px 28px;display:flex;align-items:center;gap:24px;margin-top:{18 if i else 0}px">'
        f'<span style="flex:none;width:{84 if P else 88}px;height:{84 if P else 88}px;border-radius:50%;background:{C["orange"]};color:#fff;font-size:52px;font-weight:900;display:flex;align-items:center;justify-content:center">{i + 1}</span>'
        f'<span style="font-size:{fs}px;font-weight:800;line-height:1.3">{e(t)}</span></div>' for i, t in enumerate(d["steps"]))
    info = (f'<div data-at="{d.get("banks_at", 3)}" style="font-size:{42 if P else 44}px;font-weight:700;line-height:1.4"><span class="green" style="font-weight:900">취급기관 14곳</span>  {e(d["banks"])}</div>'
            f'<div data-at="{d.get("tip_at", 4)}" style="margin-top:18px;padding:16px 26px;background:{C["amberTint"]};border-radius:16px;font-size:{42 if P else 44}px;font-weight:800;line-height:1.35">{e(d["tip"])}</div>'
            f'<div data-at="{d.get("tel_at", 5)}" style="margin-top:16px;font-size:{48 if P else 50}px;font-weight:900;line-height:1.3;color:{C["green"]}">☎ {e(d["tel"])}</div>')
    title = f'<div data-at="0" class="title">{e(d.get("title", "계좌 만드는 순서"))}</div>'
    if P:
        return (f'<div style="position:absolute;left:60px;right:60px;top:230px">{title}'
                f'<div style="margin-top:28px">{steps}</div><div style="margin-top:26px">{info}</div></div>')
    # 롱폼: 왼쪽 단계, 오른쪽 취급기관·팁·전화
    return (f'<div style="position:absolute;left:110px;right:110px;top:140px">{title}'
            f'<div style="display:flex;gap:44px;margin-top:28px;align-items:flex-start">'
            f'<div style="flex:0 0 760px">{steps}</div><div style="flex:1">{info}</div></div></div>')


def body_kids(s, P):
    d = s["data"]
    if P:
        return (f'<div data-at="0" class="card" style="position:absolute;left:60px;right:60px;top:260px;padding:50px;background:{C["amberTint"]}">'
                f'<div class="title" style="font-size:66px">{e(d["title"])}</div>'
                f'<div data-at="1" style="font-size:54px;font-weight:800;margin-top:30px;line-height:1.35">{e(d["line"])}</div>'
                f'<div data-at="2" class="muted" style="font-size:48px;font-weight:700;margin-top:26px;line-height:1.35">{e(d["sub"])}</div></div>'
                f'<img data-at="0" class="char" src="char_base.png" style="left:320px;top:800px;height:440px">')
    return (f'<div data-at="0" class="card" style="position:absolute;left:110px;width:1260px;top:170px;padding:54px;background:{C["amberTint"]}">'
            f'<div class="pill" style="background:{C["ink"]};color:#fff;font-size:42px;padding:8px 28px">부모님도 확인하세요</div>'
            f'<div class="title" style="margin-top:26px">{e(d["title"])}</div>'
            f'<div data-at="1" style="font-size:62px;font-weight:800;margin-top:28px;line-height:1.3">{e(d["line"])}</div>'
            f'<div data-at="2" class="muted" style="font-size:52px;font-weight:700;margin-top:24px;line-height:1.3">{e(d["sub"])}</div></div>'
            f'<img data-at="0" class="char" src="char_base.png" style="left:1400px;top:220px;height:620px">')


def body_outro(s, P, sources):
    d = s["data"]
    src = " · ".join(e(x["name"]) for x in sources)
    box = "left:60px;right:60px;top:240px" if P else "left:110px;width:1280px;top:140px"
    out = (f'<div style="position:absolute;{box}">'
           f'<div data-at="0" class="card" style="padding:{36 if P else 34}px 44px;background:{C["green"]};color:#fff;font-size:{60 if P else 66}px;font-weight:900;line-height:1.3">{e(d["recap"])}</div>'
           f'<div data-at="2" class="card" style="margin-top:24px;padding:24px 40px;font-size:{50 if P else 52}px;font-weight:800;line-height:1.3">▶ {e(d["next"])}</div>'
           f'<div data-at="2" style="margin-top:20px;font-size:{56 if P else 60}px;font-weight:900;color:{C["orange"]}">자녀분께도 이 영상 보내주세요</div>'
           f'<div data-at="1" class="muted" style="margin-top:20px;font-size:{36 if P else 36}px;font-weight:700;line-height:1.4">확인일 {e(s.get("_checked", ""))} · 출처: {src}</div></div>')
    if not P:
        out += f'<img data-at="0" class="char" src="char_base.png" style="left:1430px;top:200px;height:600px">'
    return out


def body_short_end(s, P):
    return (f'<div style="position:absolute;left:60px;right:60px;top:420px;text-align:center">'
            f'<div data-at="0" style="font-size:76px;font-weight:900;line-height:1.3">{e(s["data"]["line"])}</div>'
            f'<div data-at="0" class="pill" style="margin-top:50px;background:{C["green"]};color:#fff;font-size:56px;padding:18px 50px">{BELL} 효도<b style="color:{C["amber"]}">알람</b></div></div>'
            f'<img data-at="0" class="char" src="char_phone.png" style="left:330px;top:820px;height:430px">')


BODY = {"hook": body_hook, "summary": body_summary, "official": body_official, "check": body_check, "table": body_table,
        "calc": body_calc, "apply": body_apply, "kids": body_kids, "short_end": body_short_end}


def html(scene, times, dur, portrait=False, sources=()):
    P = portrait
    W, Hh = (1080, 1920) if P else (1920, 1080)
    t = scene["type"]
    body = body_outro(scene, P, sources) if t == "outro" else BODY[t](scene, P)
    T = json.dumps([round(x, 3) for x in times])
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width={W}, height={Hh}">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
<style>{css(P)}</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="{W}" data-height="{Hh}">
 <div id="stage" class="stage clip" data-start="0" data-duration="{dur:.3f}" data-track-index="0">
  {chrome(scene.get("chapter", ""))}
  {body}
 </div>
</div>
<script>
// 글자 자동 맞춤: data-fit 한 줄 문구는 폭에 맞게 줄이고, 자막 자리(LIMIT)를 넘는 덩어리는 최소 0.8배까지 줄인다.
(function () {{
  const LIMIT = {1270 if P else 830};
  document.querySelectorAll('[data-fit]').forEach(el => {{
    let fs = parseFloat(getComputedStyle(el).fontSize);
    const box = el.parentElement.clientWidth;
    while (el.scrollWidth > box && fs > 40) {{ fs -= 2; el.style.fontSize = fs + 'px'; }}
  }});
  const fitted = [];
  document.querySelectorAll('#stage > *').forEach(el => {{
    if (el.classList.contains('brand') || el.classList.contains('chapter') || el.hasAttribute('data-at')) return;
    const r = el.getBoundingClientRect();
    if (r.bottom > LIMIT && r.height > 0) {{
      const z = Math.max(0.8, (LIMIT - r.top) / r.height);
      el.style.transformOrigin = 'top left'; el.style.transform = 'scale(' + z.toFixed(3) + ')';
      fitted.push(z.toFixed(2));
    }}
  }});
  document.body.dataset.fitted = fitted.join(',');
}})();
const T = {T};
const tl = gsap.timeline({{paused: true}});
document.querySelectorAll('[data-at]').forEach(el => {{
  const k = +el.dataset.at, at = (T[k] ?? 0) + 0.05;
  tl.fromTo(el, {{opacity: 0, y: 28}}, {{opacity: 1, y: 0, duration: 0.5, ease: 'power2.out'}}, at);
}});
document.querySelectorAll('[data-check]').forEach(el => {{
  const k = +el.dataset.check, at = (T[k] ?? 0) + 0.7;
  tl.fromTo(el, {{opacity: 0, scale: 0.4}}, {{opacity: 1, scale: 1, duration: 0.35, ease: 'back.out(2)'}}, at);
}});
document.querySelectorAll('[data-grow]').forEach(el => {{
  const k = +el.dataset.grow, at = (T[k] ?? 0) + 0.1;
  tl.fromTo(el, {{scaleX: 0}}, {{scaleX: 1, duration: 0.9, ease: 'power2.out'}}, at);
}});
const shot = document.getElementById('shot');
if (shot) tl.fromTo(shot, {{scale: 1.25}}, {{scale: 1.55, duration: {dur:.3f}, ease: 'none'}}, 0);
tl.to({{}}, {{duration: {dur:.3f}}}, 0);
window.__timelines["main"] = tl; tl.seek(0);
</script></body></html>"""
