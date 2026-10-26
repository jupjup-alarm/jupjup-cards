#!/usr/bin/env python3
"""Cloudflare Workers AI 무료 한도(하루 1만 뉴런)로 컷을 그린다.

  python3 ossak/cf.py episodes/<편> [--only s01a s02b] [--force] [--model klein|schnell]

- klein = @cf/black-forest-labs/flux-2-klein-4b (기본, 가로·세로 지정 가능, 참고 이미지 가능, Apache 2.0)
- schnell = @cf/black-forest-labs/flux-1-schnell (정사각형, 가장 저렴)
- 부기 컷(with_character)은 refs/boogi_sheet.png 를 참고 이미지로 넣는다.
- 키: 환경변수 CF_ACCOUNT_ID·CF_API_TOKEN 또는 cloudflare.env
"""
import argparse, base64, json, pathlib, sys, time, urllib.error, urllib.request, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ossak"))
from render import STYLE  # 같은 그림체 문구 공유

MODELS = {"klein": "@cf/black-forest-labs/flux-2-klein-4b", "schnell": "@cf/black-forest-labs/flux-1-schnell"}


def load_env():
    """환경변수 CF_ACCOUNT_ID·CF_API_TOKEN 우선, 없으면 cloudflare.env (Mac)."""
    import os
    if os.environ.get("CF_ACCOUNT_ID") and os.environ.get("CF_API_TOKEN"):
        return os.environ["CF_ACCOUNT_ID"], os.environ["CF_API_TOKEN"]
    d = {}
    for l in (ROOT / "cloudflare.env").read_text(encoding="utf-8").splitlines():
        if "=" in l:
            k, v = l.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d["CF_ACCOUNT_ID"], d["CF_API_TOKEN"]


def fit_size(w, h, long=1024):
    """패널 비율을 유지하며 긴 변 1024, 16의 배수로."""
    if w >= h:
        W, H = long, round(long * h / w / 16) * 16
    else:
        H, W = long, round(long * w / h / 16) * 16
    return max(W, 256), max(H, 256)


def multipart(fields, files):
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out += [f"--{b}".encode(), f'Content-Disposition: form-data; name="{k}"'.encode(), b"", str(v).encode()]
    for k, (name, data, mime) in files.items():
        out += [f"--{b}".encode(), f'Content-Disposition: form-data; name="{k}"; filename="{name}"'.encode(),
                f"Content-Type: {mime}".encode(), b"", data]
    out += [f"--{b}--".encode(), b""]
    return b"\r\n".join(out), f"multipart/form-data; boundary={b}"


def generate(acct, token, model, prompt, size, refs=(), seed=None):
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{MODELS[model]}"
    if model == "schnell":
        body = json.dumps({"prompt": prompt[:2048], "steps": 8, **({"seed": seed} if seed else {})}).encode()
        ctype = "application/json"
    else:
        W, H = fit_size(*size)
        fields = {"prompt": prompt, "width": W, "height": H}
        if seed:
            fields["seed"] = seed
        files = {f"input_image_{i}": (pathlib.Path(r).name, pathlib.Path(r).read_bytes(), "image/png") for i, r in enumerate(refs)}
        body, ctype = multipart(fields, files)
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=170) as r:
        data = json.loads(r.read())
    return base64.b64decode(data["result"]["image"])


def build_prompt(spec, p):
    prompt = p["prompt"]
    if p.get("with_character"):
        prompt += " The owl must look exactly like the owl character in the reference image: " + spec["character"]
    return prompt + " " + STYLE.format(accent=spec.get("accent_name", "amber"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("--only", nargs="*"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--model", default="klein", choices=list(MODELS)); ap.add_argument("--out", default="panels")
    a = ap.parse_args()
    ep = pathlib.Path(a.episode); spec = json.loads((ep / "episode.json").read_text())
    acct, token = load_env()
    out = ep / a.out; out.mkdir(exist_ok=True)
    for p in spec["panels"]:
        if p["id"] == "p00" or (a.only and p["id"] not in a.only):
            continue
        f = out / f'{p["id"]}.jpg'
        if f.exists() and not a.force:
            continue
        refs = [ROOT / "refs" / "boogi_sheet.png"] if p.get("with_character") and a.model == "klein" else []
        for tries in range(4):
            try:
                t = time.time()
                f.write_bytes(generate(acct, token, a.model, build_prompt(spec, p), p["size"], refs))
                print(p["id"], f"{time.time()-t:.1f}s"); break
            except urllib.error.HTTPError as e:
                msg = e.read()[:200]
                print(p["id"], "HTTP", e.code, msg)
                if e.code in (429, 500, 502, 503) and tries < 3:
                    time.sleep(10 * (tries + 1)); continue
                break


if __name__ == "__main__":
    main()
