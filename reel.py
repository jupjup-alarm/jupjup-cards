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
- 인스타 화면 가림 영역(위 250px, 아래 400px)에는 핵심 글자를 두지 않는다.
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


def scene_html(sc, th, idx, start, end):
    t = sc["type"]
    a = f'data-s="{start:.3f}" data-e="{end:.3f}"'
    if t == "hook":
        chips = "".join(
            f'<span class="chip in" data-in="{start + 0.05 + i * 0.12:.2f}" '
            f'style="background:{th["chip_bg"] if i == 0 else "transparent"};color:{th["chip_fg"] if i == 0 else th["ink"]};'
            f'border:3px solid {th["outline"]}">{esc(c)}</span>'
            for i, c in enumerate(sc.get("chips", [])))
        lines = ""
        for i, ln in enumerate(sc["lines"]):
            txt = esc(ln)
            if "{n}" in txt:
                txt = txt.replace("{n}", f'<span class="num" data-count="{sc["count"]["to"]}" '
                                          f'data-cs="{start + 0.5:.2f}" data-cd="1.1" style="color:{th["hl"]}">0</span>')
                txt = f'<span style="color:{th["hl"]}">{txt}</span>'
            lines += f'<div class="hline in pop" data-in="{start + 0.2 + i * 0.22:.2f}">{txt}</div>'
        return f'''
<section class="scene hook" data-dark="1" {a} style="background:{th['bg']}">
  <div class="blob" style="background:{th['spark']}"></div>
  <div class="chips">{chips}</div>
  <div class="hlines" style="color:{th['ink'] if th.get('fg') is None else th['fg']}">{lines}</div>
  <div class="hsub in" data-in="{start + 1.5:.2f}" style="color:{th['sub']}">{esc(sc.get('sub'))}</div>
  <div class="char bounce in" data-in="{start + 0.6:.2f}">{char_svg(sc.get('face', '깜짝'))}</div>
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
  <div class="cchar bounce in" data-in="{start + 0.05:.2f}">{char_svg('closing')}</div>
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
.scene{position:absolute;inset:0;opacity:0;padding:300px 84px 420px;display:flex;flex-direction:column;overflow:hidden}
.brand{position:absolute;left:84px;top:180px;display:flex;align-items:center;gap:12px;font-weight:900;font-size:34px;z-index:5}
.bar{position:absolute;left:84px;right:84px;top:250px;height:8px;border-radius:4px;background:rgba(15,30,61,.12);z-index:5;overflow:hidden}
.bar i{display:block;height:100%;width:0}
.hook{justify-content:center;padding-bottom:520px}
.blob{position:absolute;width:900px;height:900px;border-radius:50%;right:-380px;top:180px;opacity:.13}
.chips{display:flex;gap:16px;margin-bottom:40px}
.chip{font-weight:900;font-size:40px;padding:10px 26px;border-radius:14px}
.hlines{font-family:'Black Han Sans';font-size:190px;line-height:1.08;letter-spacing:-2px}
.hsub{font-size:52px;font-weight:700;margin-top:44px;line-height:1.4;white-space:pre-line}
.char{position:absolute;right:70px;bottom:440px;width:380px;height:380px}
.points{justify-content:center;padding-top:300px}
.eyebrow{font-size:50px;font-weight:900;margin-bottom:18px}
.ptitle{white-space:pre-line;font-family:'Black Han Sans';font-size:124px;line-height:1.12;margin-bottom:56px;letter-spacing:-1px}
.rows{display:flex;flex-direction:column;gap:26px}
.row{border-radius:32px;padding:44px 46px;display:flex;align-items:center;gap:30px}
.rl{flex:0 0 230px;font-size:44px;font-weight:900}
.rv{font-size:58px;font-weight:800;line-height:1.3;white-space:pre-line}
.ptext{white-space:pre-line;margin-top:48px;font-size:46px;font-weight:600;color:#5B6472;line-height:1.45}
.cta{align-items:center;justify-content:center;text-align:center;padding-bottom:460px}
.cchar{width:380px;height:380px;margin-bottom:30px}
.cline{font-family:'Black Han Sans';font-size:112px;line-height:1.15}
.btns{margin-top:56px}
.btn{display:inline-block;color:#fff;font-weight:900;font-size:46px;padding:26px 54px;border-radius:999px}
.disc{margin-top:48px;font-size:30px;color:#5B6472;line-height:1.5}
.in{opacity:0}
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
    const o=cl((t-a)/0.3)*(e>=TOTAL-0.01?1:cl((e-t)/0.3));
    s.style.opacity=o; s.style.visibility=o>0?'visible':'hidden';
    const z=1+0.03*cl((t-a)/(e-a)); s.style.transform='scale('+z+')';
  });
  document.querySelectorAll('.in').forEach(el=>{
    const p=cl((t-(+el.dataset.in))/0.45);
    const k=el.classList.contains('pop')?back(p):ease(p);
    el.style.opacity=ease(p);
    el.style.transform=el.classList.contains('pop')?'translateY('+((1-k)*80)+'px) scale('+(0.85+0.15*k)+')':'translateY('+((1-k)*60)+'px)';
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
};
"""


def build(spec):
    th = dict(THEMES.get(spec.get("series", "줍줍알람"), THEMES["줍줍알람"]))
    t = 0.0
    scenes = []
    for i, sc in enumerate(spec["scenes"]):
        d = float(sc.get("dur", 5))
        scenes.append(scene_html(sc, th, i, t, t + d))
        t += d
    total = t
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_face()}{CSS}</style></head><body>
<div class="brand">{BELL.format(s=40, c=th['accent'])}<span>줍줍알람</span></div>
<div class="bar"><i style="background:{th['accent']}"></i></div>
{''.join(scenes)}
<script>{JS.replace('__TOTAL__', f'{total:.3f}')}</script></body></html>"""
    return page, total


def main(path):
    spec = json.loads(Path(path).read_text())
    slug = spec["slug"]
    out = ROOT / "reels" / slug
    frames = out / "_frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    page, total = build(spec)
    (out / "reel.html").write_text(page)

    from playwright.sync_api import sync_playwright
    n = int(round(total * FPS))
    stills = []
    starts = []
    acc = 0.0
    for sc in spec["scenes"]:
        starts.append(acc + min(float(sc.get("dur", 5)) - 0.3, 2.6))
        acc += float(sc.get("dur", 5))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.set_content(page)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "%05d.jpg"),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)], check=True)
    shutil.rmtree(frames)

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
    manifest = {"slug": slug, "duration": round(total, 2), "video": f"{base}/reel.mp4",
                "cover": f"{base}/cover.jpg", "size_mb": round(mp4.stat().st_size / 1e6, 2)}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
