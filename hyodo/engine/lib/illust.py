"""상황 그림(숏츠 배경·썸네일): Cloudflare Workers AI FLUX.2 klein. 같은 문구는 캐시를 쓴다.

2026-11-04 벤치마크 분석: 터진 숏츠는 0초부터 '사람의 상황'(걱정·놀람 표정의 어르신)이 화면을 채운다.
실존 인물처럼 보이지 않게 따뜻한 2D 일러스트로만 그린다(사진풍 금지).
"""
import base64, hashlib, json, pathlib, sys, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import env
from char import multipart
E = env.load()
URL = f"https://api.cloudflare.com/client/v4/accounts/{E['CF_ACCOUNT_ID']}/ai/run/@cf/black-forest-labs/flux-2-klein-4b"
STYLE = ("Warm soft 2D illustration in a gentle Korean webtoon picture-book style, soft pastel colors, clean shapes, "
         "cozy natural light, expressive faces, Korean people. Not a photograph. No text, no letters, no numbers, "
         "no logos, no watermark. ")


def gen(prompt, out, w=768, h=1152, seed=None):
    out = pathlib.Path(out)
    if out.exists() and out.stat().st_size > 10000:
        return out
    seed = seed if seed is not None else int(hashlib.sha1(prompt.encode()).hexdigest()[:6], 16) % 100000
    body, ct = multipart({"prompt": STYLE + prompt, "width": w, "height": h, "seed": seed})
    req = urllib.request.Request(URL, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {E['CF_API_TOKEN']}", "Content-Type": ct})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=170) as r:
                out.write_bytes(base64.b64decode(json.loads(r.read())["result"]["image"]))
            return out
        except Exception as e:
            if i == 2:
                raise
    return out


def cached(prompt, cache_dir, w=768, h=1152):
    cache_dir = pathlib.Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    k = hashlib.sha1(f"{prompt}|{w}x{h}".encode()).hexdigest()[:12]
    return gen(prompt, cache_dir / f"img_{k}.jpg", w, h)


if __name__ == "__main__":
    print(cached(sys.argv[1], sys.argv[2]))
