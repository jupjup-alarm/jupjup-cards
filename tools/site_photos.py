"""분양 홈페이지 자료 → 저장소 photos/site/<key>/ (2026-11-02, 사용자 요청 "홈페이지 사진을 SEO·릴스·카드뉴스에 활용").

① 조사 담당이 tools/site_assets.py로 홈페이지를 훑고 눈으로 고른 이미지 주소를 '청약조사' AI열(홈페이지 자료)에 적는다.
④ 디자인·⑦ SEO 담당은 그 칸 글을 이 도구에 넣어 저장소로 받는다 (이미 받은 주소는 건너뜀 — 여러 번 돌려도 같음).

AI열 형식 (줄마다):
  key: 2026000123                      ← 사이트 공고 key (청약홈 주택관리번호 / lh공고ID / pre-슬러그)
  홈페이지: https://…
  출처: 대우건설                        ← 사업주체(시공·시행) — 이미지 출처 표기용
  조감도 | 낮 전경 | https://….jpg
  단지배치도 | | https://…
  동호배치도 | 201~203동 | https://…
  평면도 | 84A | https://…
  커뮤니티 | 피트니스 | https://…
  인테리어 | 84A 거실 | https://…
  커뮤니티 | 라운지 사진 | https://…/community.jpg | crop=0,0.62,1,1
      ↑ 여러 그림이 한 장에 붙은 긴 이미지는 crop=왼,위,오른,아래 (0~1 비율 또는 원본 px)로 필요한 부분만. 같은 주소를 crop만 다르게 여러 줄 써도 됨
  평면도 | 59A | ~/줍줍알람/공고문/2026000123-site/plan-59a.png   ← ego lite가 직접 저장한 파일도 됨 (주소로 못 받을 때)
  E모델하우스 | 84A·103A | https://…   (링크만, 받지 않음)
  VR | 항공VR | https://…               (링크만)
  ※ "홈페이지 차단" / "자료 없음: …" 한 줄이면 아무것도 받지 않는다.

사용:
  python3 tools/site_photos.py --text "$(AI열 글)"      또는  --file ai.txt
결과:
  photos/site/<key>/<분류>-<이름>.jpg   (긴 변 1600px, 평면·배치·동호는 2000px, JPEG)
  photos/site/<key>/index.json          {key, homepage, owner, images:[{cat, kind, label, file, src, w, h, photo}], links:[…]}
  photos/site/<key>/contact.jpg         한 장짜리 미리보기 (Read로 확인)
"""
import argparse
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
KINDS = {  # 한글 분류 → (파일 접두어, 긴 변 px) — 2026-11-04 사용자 결정 "이미지는 최대한 큰 사이즈로, 원본을" → 2400·3000으로 키움
    "조감도": ("birdseye", 2400), "투시도": ("birdseye", 2400), "외관": ("birdseye", 2400), "단지배치도": ("siteplan", 3000), "배치도": ("siteplan", 3000),
    "동호배치도": ("dongho", 3000), "동호수배치도": ("dongho", 3000), "평면도": ("plan", 3000), "커뮤니티": ("community", 2400),
    "단지둘러보기": ("community", 2400), "단지 둘러보기": ("community", 2400), "조경": ("community", 2400), "인테리어": ("interior", 2400),
    "입지": ("location", 2400),
}
LINKS = {"E모델하우스": "emodel", "e모델하우스": "emodel", "VR": "vr", "사이버견본주택": "emodel", "모집공고": "pdf"}


def parse(text):
    meta, items, links, note = {}, [], [], ""
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("·-• ").strip()
        if not line:
            continue
        m = re.match(r"^(key|홈페이지|출처)\s*[:：]\s*(.+)$", line, re.I)
        if m:
            meta[{"홈페이지": "homepage", "출처": "owner"}.get(m.group(1), "key")] = m.group(2).strip()
            continue
        parts = [p.strip() for p in line.split("|")]
        ui = next((i for i, p in enumerate(parts) if p.startswith(("http", "file:", "/", "~/"))), None)
        if ui is not None and ui >= 1:
            kind, label, url = parts[0], (parts[1] if ui >= 2 else ""), parts[ui]
            crop = next((p.split("=", 1)[1].strip() for p in parts[ui + 1:] if p.startswith("crop=")), "")
            if kind in KINDS:
                items.append({"kind": kind, "label": label, "src": url, "crop": crop})
            elif kind in LINKS or kind.lower() in (k.lower() for k in LINKS):
                links.append({"kind": LINKS.get(kind, "emodel"), "label": label or kind, "name": kind, "url": url})
            continue
        if re.search(r"(차단|자료 없음|없음)", line):
            note = line
    return meta, items, links, note


def slug(s):
    s = re.sub(r"[^0-9a-zA-Z]+", "-", s.lower()).strip("-")
    return s[:24]


def cropbox(crop, w, h):
    v = [float(x) for x in re.split(r"[,\s]+", crop.strip()) if x]
    if len(v) != 4:
        raise ValueError(f"crop은 숫자 4개: {crop}")
    if all(0 <= x <= 1 for x in v):
        v = [v[0] * w, v[1] * h, v[2] * w, v[3] * h]
    x0, y0, x1, y1 = (int(round(x)) for x in v)
    if x1 - x0 < 50 or y1 - y0 < 50:
        raise ValueError(f"crop이 너무 작음: {crop}")
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def save(content, dst, maxside, crop=""):
    im = Image.open(io.BytesIO(content))
    if crop:
        im = im.crop(cropbox(crop, *im.size))
    if im.mode in ("P", "LA", "RGBA"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    if max(im.size) > maxside:
        im.thumbnail((maxside, maxside), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=85, optimize=True, progressive=True)
    return im.size


def photo_like(path):
    im = Image.open(path).convert("RGB").resize((96, 96))
    px = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
    white = sum(1 for r, g, b in px if r > 235 and g > 235 and b > 235) / len(px)
    colors = len(set((r // 32, g // 32, b // 32) for r, g, b in px))
    return white < 0.35 and colors > 40


def font(sz):
    for f in (ROOT / "fonts" / "NotoSansKR-VF.ttf", ROOT / "fonts" / "NotoSansKR-Regular.ttf"):
        if f.exists():
            try:
                return ImageFont.truetype(str(f), sz)
            except OSError:
                pass
    return ImageFont.load_default()


def contact(folder, images):
    if not images:
        return
    tw, th, cols = 300, 230, 4
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 34)), "white")
    d = ImageDraw.Draw(sheet)
    f = font(18)
    for i, it in enumerate(images):
        x, y = (i % cols) * tw, (i // cols) * (th + 34)
        try:
            im = Image.open(folder / Path(it["file"]).name).convert("RGB")
            im.thumbnail((tw - 8, th - 8))
            sheet.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        except OSError:
            pass
        d.text((x + 6, y + th + 4), f"{Path(it['file']).name}  {it['label']}"[:34], fill="#111", font=f)
    sheet.save(folder / "contact.jpg", quality=80)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--file")
    ap.add_argument("--key", help="AI열에 key: 줄이 없을 때")
    a = ap.parse_args()
    text = a.text if a.text is not None else Path(a.file).read_text(encoding="utf-8")
    meta, items, links, note = parse(text)
    key = (a.key or meta.get("key") or "").strip()
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z_-]{2,60}", key):
        sys.exit(f"key가 없거나 이상해요: {key!r} (AI열 첫 줄 'key: 주택관리번호')")
    folder = ROOT / "photos" / "site" / key
    idx_path = folder / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else {"key": key, "images": [], "links": []}
    idx.update({k: v for k, v in meta.items() if k in ("homepage", "owner")})
    if note and not items:
        idx["note"] = note
    have = {im["src"] + "#" + im.get("crop", ""): im for im in idx["images"]}
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; jupjup-alarm/1.0; +https://jupjupalarm.com)"
    ref = (meta.get("homepage") or "").encode("ascii", "ignore").decode()
    new, warn = 0, []
    used = {Path(im["file"]).name for im in idx["images"]}
    for it in items:
        if it["src"] + "#" + it["crop"] in have:
            have[it["src"] + "#" + it["crop"]].update(kind=it["kind"], label=it["label"])   # 분류·이름 고침은 반영
            continue
        cat, maxside = KINDS[it["kind"]]
        base = f"{cat}-{slug(it['label'])}" if slug(it["label"]) else cat
        name, n = f"{base}.jpg", 2
        while name in used:
            name, n = f"{base}-{n}.jpg", n + 1
        try:
            if not it["src"].startswith("http"):   # ego lite가 직접 저장한 파일 (2026-11-04)
                lp = Path(it["src"].removeprefix("file://")).expanduser()
                r = type("R", (), {"status_code": 200, "content": lp.read_bytes(), "raise_for_status": lambda self: None})()
            else:
                r = s.get(it["src"], timeout=30, headers={"Referer": ref} if ref else {})
            if r.status_code in (401, 403, 406, 429, 451):
                warn.append(f"차단 {r.status_code}: {it['src']} (우회하지 않음)")
                continue
            r.raise_for_status()
            w, h = save(r.content, folder / name, maxside, it["crop"])
        except Exception as e:  # noqa: BLE001
            warn.append(f"실패: {it['kind']} {it['label']} {it['src']} — {e}")
            continue
        used.add(name)
        rec = {"cat": cat, "kind": it["kind"], "label": it["label"], "file": f"photos/site/{key}/{name}",
               "src": it["src"], "crop": it["crop"], "w": w, "h": h, "md5": hashlib.md5(r.content).hexdigest()}
        rec["photo"] = photo_like(folder / name)
        idx["images"].append(rec)
        new += 1
        time.sleep(0.3)
    seen = {l["url"] for l in idx["links"]}
    idx["links"] += [l for l in links if l["url"] not in seen]
    idx["updated"] = time.strftime("%Y-%m-%d %H:%M")
    order = list(dict.fromkeys(v[0] for v in KINDS.values()))
    idx["images"].sort(key=lambda im: order.index(im["cat"]) if im["cat"] in order else 99)   # 같은 분류 안에서는 AI열 순서
    folder.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    contact(folder, idx["images"])
    print(json.dumps({"key": key, "folder": f"photos/site/{key}", "new": new, "total": len(idx["images"]),
                      "by_cat": {c: sum(1 for im in idx["images"] if im["cat"] == c) for c in order if any(im["cat"] == c for im in idx["images"])},
                      "links": [f"{l['name']}: {l['url']}" for l in idx["links"]], "note": idx.get("note", ""), "warnings": warn},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
