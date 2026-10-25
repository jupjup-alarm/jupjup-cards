#!/usr/bin/env python3
"""줍줍알람 숏츠(릴스) 렌더러 — 모션그래픽 세로 영상 1080×1920 MP4.

사용법:
    python3 reel.py reels/specs/<slug>.json

결과:
    reels/<slug>/reel.mp4        (인스타 릴스 게시용, H.264 + 무음 AAC)
    reels/<slug>/cover.jpg       (훅 장면 정지 화면)
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
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from render import THEMES, FACES, BELL, esc, hl  # noqa: E402

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
        for i, ln in enumerate(sc["lines"]):
            txt = esc(ln)
            if "{n}" in txt:
                txt = txt.replace("{n}", f'<span class="num pulse" data-p="{start + 0.35:.2f}" '
                                          f'style="display:inline-block;color:{th["hl"]}">{esc(sc["count"]["to"])}</span>')
                txt = f'<span style="color:{th["hl"]}">{txt}</span>'
            lines += f'<div class="hline punch" data-p="{start:.2f}">{txt}</div>'
        return f'''
<section class="scene hook" data-dark="1" {a} style="background:{th['bg']}">
  <div class="blob" style="background:{th['spark']}"></div>
  <div class="chips">{chips}</div>
  <div class="hlines" style="color:{th['ink'] if th.get('fg') is None else th['fg']}">{lines}</div>
  <div class="hsub in" data-in="{start + 0.25:.2f}" style="color:{th['sub']}">{esc(sc.get('sub'))}</div>
  <div class="char bounce in" data-in="{start + 0.15:.2f}">{char_svg(sc.get('face', '깜짝'))}</div>
</section>'''
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
  <div class="ptitle in" data-in="{start + 0.2:.2f}">{esc(sc.get('title'))}</div>
  <div class="rows">{rows}</div>
  {text}
</section>'''
    if t == "cta":
        lines = "".join(f'<div class="cline in pop" data-in="{start + 0.25 + i * 0.2:.2f}">{hl(ln, sc.get("highlight"), th["accent"])}</div>'
                        for i, ln in enumerate(sc["lines"]))
        return f'''
<section class="scene cta" {a} style="background:{th['soft']}">
  <div class="cchar bounce in" data-in="{start + 0.05:.2f}">{talk_svg() if sc.get('_voiced') else char_svg('closing')}</div>
  <div class="clines">{lines}</div>
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
.hsub{font-size:52px;font-weight:700;margin-top:44px;line-height:1.4;white-space:pre-line}
.char{position:absolute;right:170px;bottom:420px;width:320px;height:320px}
.points{justify-content:center}
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
.narrator{position:absolute;left:60px;bottom:380px;width:270px;height:270px;z-index:6;opacity:0}
.voiced .hook .char{display:none}
.voiced .hook{padding-bottom:640px}
.voiced .points{padding-bottom:660px}
.voiced .ptitle{font-size:108px;margin-bottom:36px}
.voiced .rows{gap:20px}
.voiced .row{padding:32px 40px}
.voiced .rv{font-size:52px}
.voiced .ptext{font-size:42px;margin-top:32px}
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
    el.style.opacity=ease(p);
    el.style.transform=el.classList.contains('pop')?'translateY('+((1-k)*80)+'px) scale('+(0.85+0.15*k)+')':'translateY('+((1-k)*60)+'px)';
  });
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
    nar.style.opacity=cl((t-0.4)/0.4)*cl((ctaS-t)/0.3);
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


LEAD, TAIL = 0.35, 0.5   # 장면 시작 후 말하기까지, 말 끝난 뒤 다음 장면까지 (초)
FIRST_LEAD = 0.05        # 첫 장면(훅)은 바로 말하기 시작 — 1초 안에 훅이 들리게


def lead(i):
    return FIRST_LEAD if i == 0 else LEAD


def audio_len(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def voice_files(spec):
    v = str(spec.get("voice") or "").split(" ")[0].strip()
    if not v:
        return [None] * len(spec["scenes"])
    d = ROOT / v
    speed = float(spec.get("voice_speed", 1.0))
    tmp = ROOT / "reels" / spec["slug"] / "_voice"
    out = []
    for i in range(len(spec["scenes"])):
        f = d / f"{i + 1:02d}.mp3"
        if f.exists() and abs(speed - 1.0) > 0.01:   # 말 빠르기 조정 (음높이 유지)
            tmp.mkdir(parents=True, exist_ok=True)
            g = tmp / f.name
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(f), "-filter:a", f"atempo={speed}", str(g)], check=True)
            f = g
        out.append(f if f.exists() else None)
    return out


def timeline(spec):
    """장면별 (시작, 길이, 음성파일). 음성이 있으면 음성 길이에 맞춰 장면을 늘린다."""
    vf = voice_files(spec)
    t, out = 0.0, []
    for i, (sc, f) in enumerate(zip(spec["scenes"], vf)):
        d = float(sc.get("dur", 5))
        if f:
            d = max(d, lead(i) + audio_len(f) + TAIL)
        out.append((t, d, f))
        t += d
    return out, t


def envelope(tl, total):
    """음성 크기 → 프레임별 입 벌림(0~1)."""
    import numpy as np
    n = int(round(total * FPS))
    env = np.zeros(n)
    sr, hop = 16000, 16000 // FPS
    for i, (start, _, f) in enumerate(tl):
        if not f:
            continue
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
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
    scenes = []
    for i, (sc, (t, d, f)) in enumerate(zip(spec["scenes"], tl)):
        sc = dict(sc, _voiced=voiced)
        scenes.append(scene_html(sc, th, i, t, t + d))
    mouth = envelope(tl, total) if voiced else []
    narrator = f'<div class="narrator">{talk_svg()}</div>' if voiced else ""
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_face()}{CSS}</style></head><body class="{'voiced' if voiced else ''}">
<div class="brand">{BELL.format(s=40, c=th['accent'])}<span>줍줍알람</span></div>
<div class="bar"><i style="background:{th['accent']}"></i></div>
{''.join(scenes)}
{narrator}
<script>const MOUTH={json.dumps(mouth)};{JS.replace('__TOTAL__', f'{total:.3f}')}</script></body></html>"""
    return page, total, tl


FIT_JS = """
() => {
  // 아래 말하는 캐릭터(왼쪽 아래, y≈1270~)·캡션 자리(아래 420px)와 겹치지 않게: 내용 맨 아래가 1250px을 넘으면 글자 크기를 6%씩 줄임 (최대 5번)
  const voiced = document.body.classList.contains('voiced');
  document.querySelectorAll('.scene').forEach(s => {
    const LIMIT = (voiced && !s.classList.contains('cta')) ? 1250 : 1480;  // 마무리 장면엔 말하는 캐릭터가 없음
    const vis = s.style.opacity, vv = s.style.visibility;
    s.style.opacity = 1; s.style.visibility = 'visible';
    s.querySelectorAll('.in').forEach(e => { e.dataset.o = e.style.opacity; e.style.opacity = 1; });
    const bottom = () => Math.max(...[...s.children].filter(k => !k.classList.contains('blob') && !k.classList.contains('char'))
                                       .map(k => k.getBoundingClientRect().bottom));
    let k = 0;
    while (bottom() > LIMIT && k < 5) {
      s.querySelectorAll('.ptitle,.rv,.rl,.ptext,.hlines,.hsub,.cline,.eyebrow').forEach(e => {
        e.style.fontSize = (parseFloat(getComputedStyle(e).fontSize) * 0.94) + 'px'; });
      s.querySelectorAll('.row').forEach(e => { const cs = getComputedStyle(e);
        e.style.paddingTop = e.style.paddingBottom = (parseFloat(cs.paddingTop) * 0.85) + 'px'; });
      k++;
    }
    s.querySelectorAll('.in').forEach(e => { e.style.opacity = e.dataset.o || ''; });
    s.style.opacity = vis; s.style.visibility = vv;
  });
}
"""


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
    voices = [(t0 + lead(i), f) for i, (t0, _, f) in enumerate(tl) if f]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "%05d.jpg"),
           "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    for _, f in voices:
        cmd += ["-i", str(f)]
    if voices:
        fl = "".join(f"[{k + 2}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={int(t0 * 1000)}:all=1[v{k}];"
                     for k, (t0, _) in enumerate(voices))
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

    base = f"{RAW_BASE}/reels/{slug}"
    manifest = {"slug": slug, "duration": round(total, 2), "voiced": bool(voices), "video": f"{base}/reel.mp4",
                "cover": f"{base}/cover.jpg", "size_mb": round(mp4.stat().st_size / 1e6, 2)}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
