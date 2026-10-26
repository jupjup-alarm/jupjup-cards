#!/usr/bin/env python3
"""오싹알람 컷 렌더러: episodes/<id>/episode.json 의 panels 를 Gemini 이미지 모델로 생성한다.

사용: python3 ossak/render.py episodes/W-0001-dyatlov [--only p01 p02] [--force] [--model 모델명]
- 이미 있는 컷은 건너뛴다(--force 로 다시 생성).
- ref_panels 에 적힌 컷(예: 부기 캐릭터 시트 p00)을 레퍼런스 이미지로 함께 보낸다.
"""
import argparse, base64, json, math, os, pathlib, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = os.environ.get("OSSAK_MODEL", "gemini-nano-banana-2.1")
STYLE = ("Rendered as a moody Korean webtoon panel: clean comic line art with soft painterly shading, "
         "muted deep navy and slate blue palette with a single warm {accent} accent light, cinematic framing. Full-bleed artwork filling the entire frame edge to edge, no borders, no frames, no letterboxing, no black bars. "
         "Any human figures are faceless silhouettes with no facial features. "
         "No text, no letters, no numbers, no speech bubbles, no watermark, no blood, no gore, no dead bodies.")
ASPECTS = {"1:1": 1.0, "2:3": 2 / 3, "3:2": 1.5, "3:4": 0.75, "4:3": 4 / 3, "4:5": 0.8,
           "5:4": 1.25, "9:16": 9 / 16, "16:9": 16 / 9, "21:9": 21 / 9}


def load_key():
    env = ROOT / "gemini.env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("gemini.env 에 GEMINI_API_KEY 가 없습니다")


def nearest_aspect(w, h):
    r = w / h
    return min(ASPECTS, key=lambda k: abs(math.log(ASPECTS[k] / r)))


def panel_refs(ep, p):
    """레퍼런스 이미지 목록: ref_panels(같은 편 컷) + 부기 등장 컷이면 refs/boogi_sheet.png"""
    refs = [ep / "panels" / f"{r}.png" for r in p.get("ref_panels", []) if r != "p00"]
    if p.get("with_character"):
        refs.append(ROOT / "refs" / "boogi_sheet.png")
    return refs


def build_request(spec, p, refs):
    """generateContent 요청 본문(standard·batch 공용)과 비율을 만든다."""
    prompt = p["prompt"]
    if p.get("with_character"):
        prompt += " The owl in this scene must be exactly the same character as in the reference image: " + spec["character"]
    prompt += " " + STYLE.format(accent=spec.get("accent_name", "amber"))
    aspect = nearest_aspect(*p["size"])
    parts = [{"text": prompt}]
    for r in refs:
        mime = "image/png" if str(r).lower().endswith(".png") else "image/jpeg"
        parts.append({"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(pathlib.Path(r).read_bytes()).decode()}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}}
    return body, aspect


def image_from_response(data):
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            d = part.get("inlineData") or part.get("inline_data")
            if d:
                return base64.b64decode(d["data"])
    return None


def generate(key, model, body):
    req = urllib.request.Request(API.format(model=model), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=170) as res:
        data = json.load(res)
    img = image_from_response(data)
    if img is None:
        raise RuntimeError("응답에 이미지가 없습니다: " + json.dumps(data, ensure_ascii=False)[:400])
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    ep = pathlib.Path(a.episode)
    spec = json.loads((ep / "episode.json").read_text(encoding="utf-8"))
    out = ep / "panels"
    out.mkdir(exist_ok=True)
    key = load_key()
    logp = ep / "render_log.json"
    log = json.loads(logp.read_text(encoding="utf-8")) if logp.exists() else []
    for p in spec["panels"]:
        if a.only and p["id"] not in a.only:
            continue
        dst = out / f'{p["id"]}.png'
        if dst.exists() and not a.force:
            print("skip", p["id"])
            continue
        refs = panel_refs(ep, p)
        missing = [str(r) for r in refs if not r.exists()]
        if missing:
            print("레퍼런스 없음, 먼저 준비하세요:", missing)
            continue
        body, aspect = build_request(spec, p, refs)
        for attempt in range(4):
            try:
                t = time.time()
                dst.write_bytes(generate(key, a.model, body))
                sec = round(time.time() - t, 1)
                print(f'ok {p["id"]} {aspect} {sec}s')
                log.append({"panel": p["id"], "model": a.model, "aspect": aspect, "sec": sec, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
                break
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300]
                print("HTTP", e.code, p["id"], msg)
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(10 * (attempt + 1))
                    continue
                sys.exit(1)
            except Exception as e:  # 네트워크 끊김 등
                print("error", p["id"], e)
                time.sleep(5)
        logp.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
