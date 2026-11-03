"""막내 캐릭터 그림: Cloudflare Workers AI FLUX.2 klein (오싹알람 cf.py와 같은 호출)."""
import base64, json, sys, uuid, urllib.request, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import env
E = env.load()
URL = f"https://api.cloudflare.com/client/v4/accounts/{E['CF_ACCOUNT_ID']}/ai/run/@cf/black-forest-labs/flux-2-klein-4b"
BASE = ("2D flat vector illustration of a friendly Korean woman in her early 30s, shoulder-length dark bob hair, "
        "soft mint green cardigan over a white t-shirt, warm natural smile, simple clean shapes, thick soft outlines, "
        "pastel palette, plain pure white background, centered upper body, no text, no letters, no logo, no watermark. ")
def multipart(fields, files=()):
    b = uuid.uuid4().hex; out = []
    for k, v in fields.items():
        out += [f"--{b}".encode(), f'Content-Disposition: form-data; name="{k}"'.encode(), b"", str(v).encode()]
    for k, (name, data) in files:
        out += [f"--{b}".encode(), f'Content-Disposition: form-data; name="{k}"; filename="{name}"'.encode(), b"Content-Type: image/png", b"", data]
    out += [f"--{b}--".encode(), b""]
    return b"\r\n".join(out), f"multipart/form-data; boundary={b}"
def gen(pose, out, ref=None, seed=7, w=768, h=1024):
    fields = {"prompt": BASE + pose + (" The woman must look exactly like the character in the reference image." if ref else ""), "width": w, "height": h, "seed": seed}
    files = [("input_image_0", (pathlib.Path(ref).name, pathlib.Path(ref).read_bytes()))] if ref else []
    body, ct = multipart(fields, files)
    req = urllib.request.Request(URL, data=body, method="POST", headers={"Authorization": f"Bearer {E['CF_API_TOKEN']}", "Content-Type": ct})
    with urllib.request.urlopen(req, timeout=170) as r:
        pathlib.Path(out).write_bytes(base64.b64decode(json.loads(r.read())["result"]["image"]))
if __name__ == "__main__":
    d = pathlib.Path(sys.argv[1]); d.mkdir(parents=True, exist_ok=True)
    gen("She is waving hello with one hand.", d / "base.png", seed=11)
    print("base ok")
