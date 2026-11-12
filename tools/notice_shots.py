"""공고문 화면 컷 (2026-11-12 사용자 결정 "공고문을 화면에 사용할 수 있으면 사용").

터진 릴스(@zip__kok·@yang_zipsa)는 진짜 공고문 화면에 형광펜을 그어 '증거'로 보여준다.
공고문 PDF에서 공급금액(임대조건)·신청일정·신청자격 부분을 찾아 그 쪽을 그림으로 자르고,
--mark 로 준 글자(예: "4억7,552", "54,660")가 있는 줄에 노란 형광펜을 칠한다.

→ photos/site/<key>/notice-<kind>.jpg + index.json에 {cat: "notice", kind: "공고문", photo: false}
   (이야기형 릴스에서 proof {"kind":"image"} 카드로 — 풀화면 배경으로는 쓰지 않음)

사용:
  python3 tools/notice_shots.py <key> <공고문.pdf> [--mark "4억7,552"] [--mark "11/13"] [--owner LH]
  lh_files.py --images 와 notice_import.py 가 공고문을 받을 때 자동으로 부른다 (형광펜 없이).
  ④ 디자인은 그날 대본 숫자로 --mark 를 주고 다시 부르면 된다 (같은 파일을 덮어씀) →
     notice-mark.jpg = 그 숫자가 처음 나오는 줄을 가운데쯤 두고 자른 컷 (형광펜이 꼭 보이는 컷).
필요: pdftotext·pdftoppm (poppler-utils). 없으면 아무것도 안 함.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (파일 이름, 화면 이름, 찾을 제목 글자) — 위에서부터 먼저 찾은 쪽
KINDS = [
    ("price", "공급금액", r"공급\s*금액|분양\s*가격|공급\s*가격|임대\s*조건|임대\s*보증금|주택형별\s*공급"),
    ("schedule", "신청일정", r"신청\s*일정|청약\s*일정|접수\s*일정|공급\s*일정|모집\s*일정|신청\s*접수\s*일정"),
    ("qual", "신청자격", r"신청\s*자격|입주\s*자격|청약\s*자격|자격\s*요건"),
]
DPI = 150
WIN = 0.40          # 잘라낼 높이 = 쪽 높이의 40% (세로 카드에 맞게)


def norm(s):
    return re.sub(r"[\s,·]", "", s or "")


def page_lines(pdf, pno):
    """pdftotext -bbox-layout → [(yMin, yMax, xMin, xMax, 글자)], 쪽 (가로, 세로) pt."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "b.html"
        subprocess.run(["pdftotext", "-f", str(pno), "-l", str(pno), "-bbox-layout", str(pdf), str(out)],
                       capture_output=True, timeout=120)
        if not out.exists():
            return [], (0, 0)
        t = out.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', t)
    size = (float(m.group(1)), float(m.group(2))) if m else (0, 0)
    lines = []
    for lm in re.finditer(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', t, re.S):
        words = re.findall(r">([^<]*)</word>", lm.group(5))
        lines.append((float(lm.group(2)), float(lm.group(4)), float(lm.group(1)), float(lm.group(3)),
                      html.unescape(" ".join(words))))
    return lines, size


def n_pages(pdf):
    r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=60)
    m = re.search(r"Pages:\s+(\d+)", r.stdout)
    return int(m.group(1)) if m else 0


def find(pdf, pattern, maxpage=40):
    """제목 글자가 처음 나오는 (쪽, 줄 y). 목차·표지(글자가 아주 적은 쪽)는 건너뜀."""
    for p in range(1, min(n_pages(pdf), maxpage) + 1):
        lines, size = page_lines(pdf, p)
        if len(lines) < 12 or not size[1]:
            continue
        for y0, y1, x0, x1, tx in lines:
            if re.search(pattern, tx) and len(tx) < 60 and not re.search(r"\.{4,}|…{2,}", tx):   # 목차 점선 제외
                return p, y0, lines, size
    return None


def find_mark(pdf, marks, maxpage=40):
    """형광펜 글자가 처음 나오는 (쪽, 줄 y) — 숫자가 표 아래쪽에 있어도 그 줄이 화면 가운데쯤 오게."""
    ms = [norm(m) for m in marks if norm(m)]
    for p in range(1, min(n_pages(pdf), maxpage) + 1):
        lines, size = page_lines(pdf, p)
        for y0, y1, x0, x1, tx in lines:
            if any(m in norm(tx) for m in ms):
                return p, y0, lines, size
    return None


def shot(pdf, key, kind, label, pattern, marks, folder):
    hit = find_mark(pdf, marks) if kind == "mark" else find(pdf, pattern)
    if not hit:
        return None
    p, y, lines, (W, H) = hit
    top = max(0.0, y - H * (0.14 if kind == "mark" else 0.015))
    bot = min(H, top + H * WIN)
    if bot - top < H * WIN:          # 쪽 끝이면 위로 올림
        top = max(0.0, bot - H * WIN)
    # 좌우는 글자가 있는 범위만 (여백 줄이기)
    xs = [(x0, x1) for y0, y1, x0, x1, _ in lines if y0 >= top and y1 <= bot]
    left = max(0.0, min((a for a, _ in xs), default=0) - 8)
    right = min(W, max((b for _, b in xs), default=W) + 8)
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", str(DPI), "-f", str(p), "-l", str(p), "-jpeg", str(pdf), f"{td}/p"],
                       capture_output=True, timeout=300)
        fs = sorted(Path(td).glob("p*.jpg"))
        if not fs:
            return None
        im = Image.open(fs[0]).convert("RGB")
    k = im.width / W
    crop = im.crop((int(left * k), int(top * k), int(right * k), int(bot * k)))
    marked = []
    if marks:
        ov = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for y0, y1, x0, x1, tx in lines:
            if y0 < top or y1 > bot:
                continue
            if any(norm(m_) and norm(m_) in norm(tx) for m_ in marks):
                d.rectangle([int((x0 - left) * k) - 6, int((y0 - top) * k) - 4,
                             int((x1 - left) * k) + 6, int((y1 - top) * k) + 4], fill=(255, 226, 0, 110))
                marked.append(tx[:40])
        crop = Image.alpha_composite(crop.convert("RGBA"), ov).convert("RGB")
    crop.thumbnail((1400, 1400))
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / f"notice-{kind}.jpg"
    crop.save(dst, "JPEG", quality=86)
    return {"cat": "notice", "kind": "공고문", "label": f"공고문 {label} (p.{p})", "file": str(dst.relative_to(ROOT)),
            "src": f"{pdf.name}#p{p}", "crop": "", "w": crop.width, "h": crop.height,
            "md5": hashlib.md5(dst.read_bytes()).hexdigest(), "photo": False, "full": False,
            "page": p, "marked": marked}


def make(key, pdf, marks=(), owner=""):
    pdf = Path(pdf)
    if not (shutil.which("pdftotext") and shutil.which("pdftoppm")) or not pdf.exists():
        return {"key": key, "skip": "pdftotext·pdftoppm 없음 또는 PDF 없음"}
    folder = ROOT / "photos" / "site" / key
    idx_p = folder / "index.json"
    idx = json.loads(idx_p.read_text()) if idx_p.exists() else {"key": key, "images": [], "links": []}
    if owner:
        idx.setdefault("owner", owner)
    made = []
    for kind, label, pat in KINDS + ([("mark", "형광펜", "")] if marks else []):
        try:
            rec = shot(pdf, key, kind, label, pat, list(marks), folder)
        except Exception as e:  # noqa: BLE001
            print(f"notice_shots {key} {kind}: {e}", file=sys.stderr)
            rec = None
        if rec:
            idx["images"] = [im for im in idx["images"] if im.get("file") != rec["file"]] + [rec]
            made.append({"file": rec["file"], "page": rec["page"], "marked": rec["marked"]})
    if made:
        idx["updated"] = time.strftime("%Y-%m-%d %H:%M")
        idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    return {"key": key, "notice_shots": made}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("pdf")
    ap.add_argument("--mark", action="append", default=[], help="형광펜 칠할 글자 (여러 번)")
    ap.add_argument("--owner", default="")
    a = ap.parse_args()
    print(json.dumps(make(a.key, a.pdf, a.mark, a.owner), ensure_ascii=False))


if __name__ == "__main__":
    main()
