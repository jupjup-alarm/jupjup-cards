"""저해상도 이미지 → Real-ESRGAN x4plus 4배 확대 (2026-11-20 사용자 결정 "릴스 이미지 해상도가 낮으면 Real-ESRGAN(x4plus)로 확대 후 영상").

reel.py가 영상을 만들기 전에 자동으로 부른다: 풀화면에 쓰는 그림(story shots·pool·hook photo·beat bg) 중
짧은 변이 MIN_SIDE(기본 1080px) 미만이면 4배 확대한 사본 `<이름>-x4.jpg`를 같은 폴더에 만들어 그걸 쓴다
(이미 있으면 다시 만들지 않음 — 사본도 커밋해서 다음 렌더링·다른 편에서 재사용).
지도(maps/)·위성사진(photos/sat/)·증거 카드(proof)는 확대하지 않는다.

단독 실행:
  python3 tools/upscale.py photos/site/2026940257/birdseye.jpg …    # 짧은 변 1080 미만만
  python3 tools/upscale.py --force <파일>                              # 크기와 상관없이
필요: torch(CPU 가능 — pip install --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu),
      가중치 RealESRGAN_x4plus.pth (없으면 GitHub 릴리스에서 ~/.cache/realesrgan/ 로 자동으로 받음, 64MB).
모델: Real-ESRGAN (BSD-3-Clause, xinntao/Real-ESRGAN) RRDBNet 23블록. basicsr 없이 구조만 여기 옮김.
CPU에서 500px 그림 한 장에 약 10~40초. 결과는 긴 변 최대 MAX_LONG(기본 2400px)으로 줄여 저장.
"""
import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MIN_SIDE = int(os.environ.get("UPSCALE_MIN_SIDE", "1080"))
MAX_LONG = int(os.environ.get("UPSCALE_MAX_LONG", "2400"))
WEIGHTS_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
WEIGHTS_SHA = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
WEIGHTS = Path(os.environ.get("REALESRGAN_WEIGHTS", Path.home() / ".cache/realesrgan/RealESRGAN_x4plus.pth"))
SKIP_PREFIX = ("maps/", "photos/sat/")
SUFFIX = "-x4"

_model = None


def _build():
    import torch
    from torch import nn
    from torch.nn import functional as F

    class RDB5(nn.Module):
        def __init__(s, nf=64, gc=32):
            super().__init__()
            s.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
            s.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            s.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
            s.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            s.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
            s.lrelu = nn.LeakyReLU(0.2, True)

        def forward(s, x):
            x1 = s.lrelu(s.conv1(x))
            x2 = s.lrelu(s.conv2(torch.cat((x, x1), 1)))
            x3 = s.lrelu(s.conv3(torch.cat((x, x1, x2), 1)))
            x4 = s.lrelu(s.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = s.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        def __init__(s, nf=64, gc=32):
            super().__init__()
            s.rdb1, s.rdb2, s.rdb3 = RDB5(nf, gc), RDB5(nf, gc), RDB5(nf, gc)

        def forward(s, x):
            return s.rdb3(s.rdb2(s.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(s, nf=64, nb=23, gc=32):
            super().__init__()
            s.conv_first = nn.Conv2d(3, nf, 3, 1, 1)
            s.body = nn.Sequential(*[RRDB(nf, gc) for _ in range(nb)])
            s.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1)
            s.conv_last = nn.Conv2d(nf, 3, 3, 1, 1)
            s.lrelu = nn.LeakyReLU(0.2, True)

        def forward(s, x):
            f = s.conv_first(x)
            f = f + s.conv_body(s.body(f))
            f = s.lrelu(s.conv_up1(F.interpolate(f, scale_factor=2, mode="nearest")))
            f = s.lrelu(s.conv_up2(F.interpolate(f, scale_factor=2, mode="nearest")))
            return s.conv_last(s.lrelu(s.conv_hr(f)))

    return RRDBNet()


def _weights():
    if not WEIGHTS.exists():
        WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
        tmp = WEIGHTS.with_suffix(".part")
        print(f"[upscale] 가중치 받는 중: {WEIGHTS_URL}", file=sys.stderr)
        urllib.request.urlretrieve(WEIGHTS_URL, tmp)
        tmp.rename(WEIGHTS)
    h = hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()
    if h != WEIGHTS_SHA:
        raise RuntimeError(f"가중치 해시가 다름 ({WEIGHTS}) — 지우고 다시 받기")
    return WEIGHTS


def model():
    global _model
    if _model is None:
        import torch
        torch.set_num_threads(max(1, os.cpu_count() or 1))
        m = _build()
        sd = torch.load(_weights(), map_location="cpu", weights_only=True)
        sd = sd.get("params_ema") or sd.get("params") or sd
        m.load_state_dict(sd, strict=True)
        m.eval()
        _model = m
    return _model


def sr(img, tile=256, pad=12):
    """PIL RGB → 4배 PIL RGB (타일로 나눠 메모리 절약)."""
    import numpy as np
    import torch
    m = model()
    a = torch.from_numpy(np.asarray(img, dtype=np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
    _, _, h, w = a.shape
    out = torch.zeros(1, 3, h * 4, w * 4)
    with torch.inference_mode():
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y0, x0 = max(y - pad, 0), max(x - pad, 0)
                y1, x1 = min(y + tile + pad, h), min(x + tile + pad, w)
                o = m(a[:, :, y0:y1, x0:x1]).clamp_(0, 1)
                ty, tx = (y - y0) * 4, (x - x0) * 4
                th, tw = (min(y + tile, h) - y) * 4, (min(x + tile, w) - x) * 4
                out[:, :, y * 4:y * 4 + th, x * 4:x * 4 + tw] = o[:, :, ty:ty + th, tx:tx + tw]
    arr = (out.squeeze(0).permute(1, 2, 0).numpy() * 255.0).round().astype("uint8")
    return Image.fromarray(arr)


def out_path(src):
    p = Path(src)
    return p.with_name(p.stem + SUFFIX + ".jpg")


def needs(rel, min_side=MIN_SIDE):
    """확대 대상인가: 저장소 상대 경로 문자열, 래스터 그림, 짧은 변 < min_side, 이미 -x4 사본이 아님."""
    if not rel or not isinstance(rel, str) or rel.startswith(SKIP_PREFIX) or Path(rel).stem.endswith(SUFFIX):
        return False
    p = ROOT / rel
    if not p.exists() or p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        return False
    with Image.open(p) as im:
        return min(im.size) < min_side


def upscale(rel, force=False):
    """rel(저장소 상대 경로) → 확대본 상대 경로. 대상이 아니면 rel 그대로. 실패하면 예외."""
    if not force and not needs(rel):
        return rel
    src = ROOT / rel
    dst = out_path(src)
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return str(dst.relative_to(ROOT))
    im = Image.open(src).convert("RGB")
    big = sr(im)
    if max(big.size) > MAX_LONG:
        r = MAX_LONG / max(big.size)
        big = big.resize((round(big.width * r), round(big.height * r)), Image.LANCZOS)
    big.save(dst, quality=93)
    return str(dst.relative_to(ROOT))


def available():
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for f in a.files:
        rel = str(Path(f).resolve().relative_to(ROOT))
        with Image.open(ROOT / rel) as im:
            s0 = im.size
        r = upscale(rel, force=a.force)
        if r == rel:
            print(f"{rel} {s0[0]}x{s0[1]} — 건너뜀 (짧은 변 {MIN_SIDE}px 이상)")
        else:
            with Image.open(ROOT / r) as im:
                print(f"{rel} {s0[0]}x{s0[1]} → {r} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
