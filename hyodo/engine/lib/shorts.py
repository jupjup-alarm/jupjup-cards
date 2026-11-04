"""숏츠 전용 빠른 컷 형식 (2026-11-04 운영자 결정 — 벤치마크 분석: 터진 숏츠는 1.1~1.4초마다 화면이 바뀌고,
0초부터 사람의 상황 그림 + 3색 큰 글자 5줄, 10~14초에 좋아요 다리, 끝은 질문으로 첫 장면에 이어진다).

video.json shorts[] 항목에 beats가 있으면 이 형식으로 만든다(없으면 예전처럼 롱폼 장면을 세로로 다시 그림).
  {"id": "S-0006a", "title": "...", "topic": "국민연금 유족연금",
   "beats": [
     {"say": "국민연금 받던 가족이 떠나셨다면, / 남은 가족이 받는 돈이 있어요.",
      "lines": [["y", "국민연금 받던 가족"], ["w", "떠나셨다면"], ["r", "남은 가족이 받는 돈"]],
      "img": "A Korean woman in her late 60s ... worried expression"},
     {"say": "...", "lines": [...], "big": "60%", "img": "..."},
     {"say": "좋아요 눌러 주시면 / 얼마인지 바로 보여 드릴게요.", "lines": [...], "char": "ok"},
     ...
     {"say": "우리 집은 몇 퍼센트일까요?", "lines": [["r", "우리 집은 몇 %일까?"]], "img": "<첫 beat와 같은 문구>"}]}
  - lines 색: y 노랑(주제) · g 초록(조건) · r 빨강(손해·금액) · w 흰색. 한 화면 5줄, 한 줄 10자 안팎.
  - img: 상황 그림 문구(영어, lib/illust.py가 그림). 비우면 앞 beat 그림을 이어 쓴다. char: 막내 표정(base·point·phone·worried·surprised·happy·thinking·ok).
  - big: 화면 가운데 큰 숫자 하나(선택), 나올 때 '딩'.
  - 마지막 beat의 img를 첫 beat와 같게 두면 끝 화면이 첫 화면과 이어진다(루프). 끝에 무음 꼬리를 두지 않는다.

python3 lib/shorts.py episodes/<편> [숏츠ID]
"""
import html as H, json, pathlib, shutil, subprocess, sys
LIB = pathlib.Path(__file__).resolve().parent
ROOT = LIB.parent
sys.path.insert(0, str(LIB))
import tts, illust
from scenes import BELL

W, Hh = 1080, 1920
COL = {"y": "#FFD54A", "g": "#7BE3A0", "r": "#FF6B5B", "w": "#FFFFFF"}
GAP = 0.12        # beat 사이 숨
CUT = 1.5         # 이보다 긴 beat는 중간에 화면을 끊어 바꾼다
HF = str(ROOT / "node_modules" / ".bin" / "hyperframes")
SR = 24000


def e(s):
    return H.escape(str(s))


def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))[:200]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


def plan(ep, spec, short):
    """음성 합성 + beat 시각표 + 그림 파일."""
    cache = ep / "out" / "tts"
    icache = ep / "out" / "illust"
    beats, t, last_img = [], 0.0, None
    for i, b in enumerate(short["beats"]):
        wav, d, segs = tts.line(b["say"], spec["voice"], cache, short.get("rate", spec.get("rate", tts.RATE)))
        img = b.get("img")
        path = illust.cached(img, icache) if img else last_img
        if path is None:
            raise SystemExit(f"{short['id']} beat {i}: 첫 beat에는 img가 있어야 해요")
        last_img = path
        dur = d + (GAP if i < len(short["beats"]) - 1 else 0.05)
        beats.append({**b, "wav": str(wav), "start": round(t, 3), "speech": round(d, 3), "dur": round(dur, 3), "imgpath": str(path)})
        t += dur
    return beats, round(t, 3)


def page(short, beats, total):
    imgs = []  # 그림 파일 → id
    for b in beats:
        if b["imgpath"] not in imgs:
            imgs.append(b["imgpath"])
    img_tags = "".join(f'<img id="im{k}" class="bg" src="img{k}.jpg">' for k in range(len(imgs)))
    beat_html, js = [], []
    for i, b in enumerate(beats):
        k = imgs.index(b["imgpath"])
        lines = b.get("lines", [])
        ls = "".join(f'<div class="ln" data-b="{i}" data-j="{j}" style="color:{COL.get(c, "#fff")}">{e(x)}</div>' for j, (c, x) in enumerate(lines))
        big = f'<div class="big" id="big{i}">{e(b["big"])}</div>' if b.get("big") else ""
        ch = f'<img class="mn" id="mn{i}" src="char_{b["char"]}.png">' if b.get("char") else ""
        beat_html.append(f'<div class="beat" id="b{i}">{big}<div class="lines">{ls}</div>{ch}</div>')
        js.append({"i": i, "img": k, "start": b["start"], "dur": b["dur"], "speech": b["speech"], "n": len(lines),
                   "big": bool(b.get("big")), "char": bool(b.get("char"))})
    topic = short.get("topic", "")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width={W}, height={Hh}">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{Hh}px;overflow:hidden;background:#111}}
body{{font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;word-break:keep-all}}
#root{{position:absolute;inset:0}} .stage{{position:absolute;inset:0;overflow:hidden}}
.bg{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transform-origin:50% 35%}}
.shade{{position:absolute;left:0;right:0;bottom:0;height:62%;background:linear-gradient(transparent,rgba(0,0,0,.78) 45%,rgba(0,0,0,.86))}}
.top{{position:absolute;left:50px;top:120px;display:flex;gap:16px;align-items:center}}
.brand{{background:#1F5C4B;color:#fff;font-weight:900;font-size:40px;padding:10px 26px;border-radius:40px}}
.brand b{{color:#F2B544}}
.topic{{background:rgba(0,0,0,.55);color:#fff;font-weight:800;font-size:40px;padding:10px 26px;border-radius:40px}}
.beat{{position:absolute;inset:0;opacity:0}}
.lines{{position:absolute;left:36px;right:120px;bottom:460px;text-align:center}}
.ln{{font-size:122px;font-weight:900;line-height:1.16;letter-spacing:-2px;white-space:nowrap;opacity:0;
     -webkit-text-stroke:12px #000;paint-order:stroke fill;text-shadow:0 6px 18px rgba(0,0,0,.6)}}
.big{{position:absolute;left:0;right:0;top:560px;text-align:center;font-size:300px;font-weight:900;color:#FFD54A;
      letter-spacing:-8px;-webkit-text-stroke:16px #000;paint-order:stroke fill;opacity:0}}
.mn{{position:absolute;left:300px;top:330px;height:720px;opacity:0}}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{W}" data-height="{Hh}">
 <div id="stage" class="stage clip" data-start="0" data-duration="{total:.3f}" data-track-index="0">
  {img_tags}
  <div class="shade"></div>
  <div class="top"><div class="brand">{BELL} 효도<b>알람</b></div>{f'<div class="topic">{e(topic)}</div>' if topic else ''}</div>
  {''.join(beat_html)}
 </div>
</div>
<script>
// 한 줄 글자는 폭에 맞게 줄인다
document.querySelectorAll('.ln').forEach(el => {{
  let fs = 122; const box = el.parentElement.clientWidth;
  while (el.scrollWidth > box && fs > 60) {{ fs -= 3; el.style.fontSize = fs + 'px'; }}
}});
const B = {json.dumps(js)};
const tl = gsap.timeline({{paused: true}});
// 화면 구도 두 가지(가까이·멀리)를 번갈아 끊어 쓴다
const SHOTS = [{{scale: 1.08, x: 0, y: 0}}, {{scale: 1.32, x: -40, y: 60}}, {{scale: 1.2, x: 50, y: -30}}, {{scale: 1.42, x: 20, y: 120}}];
let shot = 0;
B.forEach(b => {{
  const im = '#im' + b.img, el = '#b' + b.i, end = b.start + b.dur;
  tl.set('.bg', {{opacity: 0}}, b.start); tl.set(im, {{opacity: 1}}, b.start);
  tl.set('.beat', {{opacity: 0}}, b.start); tl.set(el, {{opacity: 1}}, b.start);
  const cuts = b.dur > {CUT} ? [b.start, b.start + b.dur / 2] : [b.start];
  cuts.forEach((c, ci) => {{
    const s0 = (b.i === 0 && ci === 0) ? SHOTS[0] : SHOTS[(++shot) % SHOTS.length];
    const s1 = {{...s0, scale: s0.scale + 0.05}};
    const ce = ci + 1 < cuts.length ? cuts[ci + 1] : end;
    tl.fromTo(im, s0, {{...s1, duration: Math.max(ce - c, 0.1), ease: 'none'}}, c);
  }});
  for (let j = 0; j < b.n; j++) {{
    const at = b.start + (b.i === 0 && j === 0 ? 0 : b.speech * 0.8 * j / Math.max(b.n, 1));
    tl.fromTo(`.ln[data-b="${{b.i}}"][data-j="${{j}}"]`, {{opacity: (b.i === 0 && j === 0) ? 1 : 0, scale: 1.12}},
              {{opacity: 1, scale: 1, duration: 0.22, ease: 'back.out(2)'}}, at);
  }}
  if (b.big) tl.fromTo('#big' + b.i, {{opacity: 0, scale: 0.5}}, {{opacity: 1, scale: 1, duration: 0.3, ease: 'back.out(2.4)'}}, b.start + 0.15);
  if (b.char) tl.fromTo('#mn' + b.i, {{opacity: 0, y: 40}}, {{opacity: 1, y: 0, duration: 0.3, ease: 'back.out(1.6)'}}, b.start + 0.05);
}});
tl.to({{}}, {{duration: {total:.3f}}}, 0);
window.__timelines["main"] = tl; tl.seek(0);
</script></body></html>""", imgs


def build(ep, spec, short):
    import build as B
    beats, total = plan(ep, spec, short)
    d = ep / "out" / "render" / short["id"] / "fast"
    d.mkdir(parents=True, exist_ok=True)
    html, imgs = page(short, beats, total)
    for k, p in enumerate(imgs):
        shutil.copy(p, d / f"img{k}.jpg")
    for n in ["base", "point", "phone", "worried", "surprised", "happy", "thinking", "ok"]:
        f = ROOT / "assets" / "char" / f"{n}_cut.png"
        if f.exists():
            shutil.copy(f, d / f"char_{n}.png")
    ip = d / "index.html"
    if not ip.exists() or ip.read_text() != html:
        ip.write_text(html)
    (d / "hyperframes.json").write_text('{"paths":{"blocks":"compositions","components":"compositions/components","assets":"assets"}}')
    (d / "meta.json").write_text(json.dumps({"id": short["id"], "name": "fast"}))
    B.render_one(d)
    # 소리: 내레이션 + 배경음(말할 때 줄임) + beat 바뀔 때 '휙' + 큰 숫자 '딩'
    o = ep / "out" / short["id"]; o.mkdir(parents=True, exist_ok=True)
    B.write_track(o / "voice.wav", [(b["start"], b["wav"]) for b in beats], total)
    A = ROOT / "assets" / "music"
    whoosh = [b["start"] for b in beats[1:]]
    ding = [b["start"] + 0.15 for b in beats if b.get("big")]
    inputs = ["-i", str(o / "voice.wav"), "-stream_loop", "-1", "-i", str(A / "bgm_175.mp3")]
    filt = ["[1:a]aresample=48000,volume=0.14,atrim=0:%.3f[bgm]" % total,
            "[0:a]aresample=48000,asplit=2[v1][vk]",
            "[bgm][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[duck]"]
    mixes, n = ["[v1]", "[duck]"], 2
    for kind, times, vol in (("whoosh_3005.mp3", whoosh, 0.22), ("ding_933.mp3", ding, 0.25)):
        for t in times:
            inputs += ["-i", str(A / kind)]
            filt.append(f"[{n}:a]aresample=48000,atrim=0:1.0,volume={vol},adelay={int(t * 1000)}:all=1[s{n}]")
            mixes.append(f"[s{n}]"); n += 1
    filt.append("".join(mixes) + f"amix=inputs={len(mixes)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]", "-t", f"{total:.3f}",
        "-ar", "48000", "-ac", "2", str(o / "mix.wav")])
    out = ep / "out" / f"{short['id']}.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(d / "scene.mp4"), "-i", str(o / "mix.wav"), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}",
        "-movflags", "+faststart", str(out)])
    (o / "beats.json").write_text(json.dumps(beats, ensure_ascii=False, indent=1))
    (o / "subs_check.json").write_text("[]")  # 큰 글자가 자막 역할 — 넷플릭스 자막 검사 대상 아님
    return out, total


if __name__ == "__main__":
    ep = pathlib.Path(sys.argv[1]).resolve()
    spec = json.loads((ep / "video.json").read_text())
    for s in spec.get("shorts", []):
        if s.get("beats") and (len(sys.argv) < 3 or s["id"] in sys.argv[2:]):
            print(build(ep, spec, s))
