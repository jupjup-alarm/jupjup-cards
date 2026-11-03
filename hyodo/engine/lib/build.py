#!/usr/bin/env python3
"""효도알람 제작: video.json → 롱폼·숏츠 mp4 + 썸네일 + 업로드 정보.

  python3 lib/build.py episodes/<편> [--step tts|scenes|render|mix|final|thumb|all] [--only hook check] [--fmt long|short|both]

단계: tts(문장별 음성·시간표) → scenes(장면 HTML) → render(hyperframes) → mix(내레이션·배경음·효과음)
     → final(자막 굽기·인코딩) → thumb(썸네일) → meta(설명·챕터)
"""
import argparse, json, pathlib, shutil, subprocess, sys, wave, array
from concurrent.futures import ThreadPoolExecutor

LIB = pathlib.Path(__file__).resolve().parent
ROOT = LIB.parent
sys.path.insert(0, str(LIB))
import tts, scenes, subs as subsmod

LEAD, GAP, TAIL = 0.5, 0.55, 0.8  # 줄 사이 쉼 0.55초(구절·문장 쉼은 tts.py)
SR = 24000
HF = str(ROOT / "node_modules" / ".bin" / "hyperframes")
FONTDIR = "/usr/share/fonts/opentype/noto"


def sh(cmd, cwd=None, quiet=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))[:200]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


# ---------- 1. 음성과 시간표 ----------

def timeline(ep, spec):
    """장면마다 문장 wav·시작 시각·장면 길이. timeline.json 저장."""
    cache = ep / "out" / "tts"
    tl = {}
    for s in spec["scenes"]:
        t = LEAD; lines = []
        for text in s["say"]:
            p, d, segs = tts.line(text, spec["voice"], cache)
            lines.append({"text": tts.shown(text).replace(" / ", " ").replace("/", ""), "wav": str(p), "start": round(t, 3), "dur": round(d, 3), "segs": segs})
            t += d + GAP
        tl[s["id"]] = {"lines": lines, "dur": round(t - GAP + TAIL, 3)}
    (ep / "out" / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1))
    return tl


def seq_for(spec, fmt, short=None):
    """포맷별 장면 순서. 숏츠는 지정 장면 + 끝 카드."""
    if fmt == "long":
        return [s["id"] for s in spec["scenes"]]
    return short["scenes"] + ["short_end"]


def short_end_scene(short):
    return {"id": "short_end", "type": "short_end", "chapter": "", "say": [],
            "data": {"line": "자세한 신청 방법은\n효도알람 전체 영상에서"}}


# ---------- 2. 장면 HTML ----------

def scene_dirs(ep, spec, tl, fmt, short=None):
    portrait = fmt != "long"
    tag = "long" if fmt == "long" else short["id"]
    S = {s["id"]: s for s in spec["scenes"]}
    out = []
    for sid in seq_for(spec, fmt, short):
        if sid == "short_end":
            s, times, dur = short_end_scene(short), [0.2], 2.8
        else:
            s, times, dur = S[sid], [x["start"] for x in tl[sid]["lines"]], tl[sid]["dur"]
        s = dict(s); s["_checked"] = spec.get("checked", "")
        d = ep / "out" / "render" / tag / sid
        d.mkdir(parents=True, exist_ok=True)
        page = scenes.html(s, times, dur, portrait, spec.get("sources", []))
        if sid == "short_end":
            page = page.replace("자세한 신청 방법은\n효도알람 전체 영상에서", "자세한 신청 방법은<br>효도알람 전체 영상에서")
        ip = d / "index.html"
        if not ip.exists() or ip.read_text() != page:
            ip.write_text(page)
        (d / "hyperframes.json").write_text('{"paths":{"blocks":"compositions","components":"compositions/components","assets":"assets"}}')
        (d / "meta.json").write_text(json.dumps({"id": f"{tag}-{sid}", "name": sid}))
        for n in ["base", "point", "phone"]:
            shutil.copy(ROOT / "assets" / "char" / f"{n}_cut.png", d / f"char_{n}.png")
        for cand in (ep / "official.png", ep / "out" / "official.png"):  # 편 폴더(커밋됨) 우선
            if cand.exists():
                shutil.copy(cand, d / "official.png"); break
        out.append((sid, d, dur))
    return tag, out


# ---------- 3. 렌더 ----------

def render_one(d):
    mp4 = d / "scene.mp4"
    if mp4.exists() and mp4.stat().st_mtime > (d / "index.html").stat().st_mtime:
        return mp4
    sh([HF, "render", "-o", "scene.mp4"], cwd=d)
    return mp4


def render(dirs, jobs=2):
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(lambda x: render_one(x[1]), dirs))


# ---------- 4. 오디오 ----------

def write_track(path, events, total):
    """events: [(시작초, wav경로)] → 24kHz mono wav."""
    buf = array.array("h", [0]) * int(total * SR + SR)
    for start, wp in events:
        with wave.open(str(wp)) as w:
            assert w.getframerate() == SR and w.getnchannels() == 1
            data = array.array("h", w.readframes(w.getnframes()))
        o = int(start * SR)
        for i, v in enumerate(data):
            if o + i < len(buf):
                buf[o + i] = max(-32768, min(32767, buf[o + i] + v))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(buf.tobytes())


def mix(ep, spec, tl, tag, dirs):
    o = ep / "out" / tag
    o.mkdir(parents=True, exist_ok=True)
    S = {s["id"]: s for s in spec["scenes"]}
    ev, sfx_whoosh, sfx_ding, t0, starts = [], [], [], 0.0, []
    for i, (sid, d, dur) in enumerate(dirs):
        starts.append((sid, t0))
        if sid in tl:
            for ln in tl[sid]["lines"]:
                ev.append((t0 + ln["start"], ln["wav"]))
            if S[sid]["type"] == "check":
                for k in range(1, len(S[sid]["data"]["items"]) + 1):
                    sfx_ding.append(t0 + tl[sid]["lines"][k]["start"] + 0.7)
        if i > 0:
            sfx_whoosh.append(t0)
        t0 += dur
    total = t0
    write_track(o / "voice.wav", ev, total)
    A = ROOT / "assets" / "music"
    inputs = ["-i", str(o / "voice.wav"), "-stream_loop", "-1", "-i", str(A / "bgm_175.mp3")]
    filt = ["[1:a]aresample=48000,volume=0.16,atrim=0:%.3f,afade=t=in:d=1.5,afade=t=out:st=%.3f:d=2[bgm]" % (total, max(total - 2.5, 0))]
    filt.append("[0:a]aresample=48000,asplit=2[v1][vk]")
    filt.append("[bgm][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck]")
    mixes = ["[v1]", "[duck]"]
    n = 2
    for kind, times, vol in (("whoosh_3005.mp3", sfx_whoosh, 0.35), ("ding_933.mp3", sfx_ding, 0.25)):
        for t in times:
            inputs += ["-i", str(A / kind)]
            filt.append(f"[{n}:a]aresample=48000,atrim=0:1.2,volume={vol},adelay={int(t * 1000)}:all=1[s{n}]")
            mixes.append(f"[s{n}]"); n += 1
    filt.append("".join(mixes) + f"amix=inputs={len(mixes)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]", "-t", f"{total:.3f}",
        "-ar", "48000", "-ac", "2", str(o / "mix.wav")])
    (o / "starts.json").write_text(json.dumps(starts))
    return total, starts


# ---------- 5. 자막 ----------

def ass_time(t):
    h, r = divmod(max(t, 0), 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def subtitles(ep, spec, tl, tag, starts, portrait):
    """넷플릭스 한국어 자막 규칙(lib/subs.py). 자막 단위는 내레이션 구절에 맞춘다."""
    subsmod.setup(portrait)
    ev, ends = [], []
    o = ep / "out" / tag
    for i, (sid, t0) in enumerate(starts):
        nxt = starts[i + 1][1] if i + 1 < len(starts) else 1e9
        if sid not in tl:
            continue
        for ln in tl[sid]["lines"]:
            for e in subsmod.events_for_line(t0 + ln["start"], ln["segs"]):
                ev.append(e); ends.append(nxt)
    ev = subsmod.timing(ev, ends)
    bad = subsmod.report(ev)
    (o / "subs_check.json").write_text(json.dumps(bad, ensure_ascii=False, indent=1))
    path = o / "subs.ass"
    path.write_text(subsmod.ass(ev, portrait))
    return path


# ---------- 6. 최종 인코딩 ----------

def final(ep, tag, dirs, total, subs, outname):
    o = ep / "out" / tag
    lst = o / "concat.txt"
    lst.write_text("".join(f"file '{d / 'scene.mp4'}'\n" for _, d, _ in dirs))
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(o / "mix.wav"),
        "-vf", f"ass={subs}:fontsdir={FONTDIR}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-r", "30", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(ep / "out" / outname)])
    return ep / "out" / outname


def probe(p):
    return json.loads(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height", "-of", "json", str(p)]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("--fmt", default="both", choices=["long", "short", "both"])
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    ep = pathlib.Path(a.episode).resolve()
    spec = json.loads((ep / "video.json").read_text())
    tl = timeline(ep, spec)
    print("timeline", {k: v["dur"] for k, v in tl.items()}, "total", round(sum(v["dur"] for v in tl.values()), 1))
    jobs = []
    if a.fmt in ("long", "both"):
        jobs.append(("long", None))
    if a.fmt in ("short", "both"):
        jobs += [("short", sh_) for sh_ in spec.get("shorts", [])]
    for fmt, short in jobs:
        tag, dirs = scene_dirs(ep, spec, tl, fmt, short)
        render(dirs, a.jobs)
        total, starts = mix(ep, spec, tl, tag, dirs)
        subs = subtitles(ep, spec, tl, tag, starts, fmt != "long")
        name = f"{spec['id']}.mp4" if fmt == "long" else f"{short['id']}.mp4"
        p = final(ep, tag, dirs, total, subs, name)
        print(tag, p.name, probe(p)["format"])


if __name__ == "__main__":
    main()
