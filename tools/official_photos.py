"""공식·공개 라이선스 단지 실사 찾기 (2026-11-13 사용자 결정 "최대한 건물 실사 — 2번만").

사진이 없는 단지만, 위키미디어 커먼즈에서 단지 이름으로 찾아
상업적 이용·변경이 허용된 것(CC0·퍼블릭 도메인·CC BY·CC BY-SA, 공공누리 1유형)만 받는다.
NC(비영리)·ND(변경금지)·라이선스 불명은 받지 않는다. 파일 제목이나 설명에 단지 이름의 핵심 낱말이 있어야 한다.

→ photos/site/<key>/commons-N.jpg + index.json {cat: "commons", photo: true, credit: "사진: <작가> · <라이선스> (위키미디어 커먼즈)"}

사용: python3 tools/official_photos.py <key> "<단지명>" [--max 4]   (collect.py가 사진 0장 단지에 자동으로 부름)
"""
import argparse
import hashlib
import html
import io
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "jupjup-alarm/1.0 (+https://jupjupalarm.com; contact@jupjupalarm.com)"}
OK_LIC = re.compile(r"^(cc0|public domain|pd|cc[- ]by(-sa)?[- ]?\d|cc[- ]by(-sa)?$|kogl type 1|공공누리 ?제?1유형)", re.I)
BAD_LIC = re.compile(r"\bnc\b|\bnd\b|non-?commercial|no ?deriv", re.I)
DROP = r"\(.*?\)|임의공급|무순위|잔여세대|예비입주자|입주자|모집|공공분양주택?|공공분양|민간참여|분양 예정|신혼희망타운|계약취소분|재공급|취소분|신도시|국제신도시|행복주택|국민임대|영구임대|매입임대|공공임대|10년|주택|블록|\b[A-Z]{1,2}-?\d+[A-Z]?(BL)?\b|\d+차|\d+호|\d+세대|[·,]"


def core_words(name):
    s = re.sub(DROP, " ", name)
    return [w for w in re.split(r"\s+", s) if len(w) >= 2][:4]


def search(q, s):
    r = s.get(API, params={"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:bitmap",
                           "gsrnamespace": 6, "gsrlimit": 12, "prop": "imageinfo", "iiprop": "url|size|extmetadata",
                           "iiurlwidth": 1600}, headers=UA, timeout=30)
    try:
        return (r.json().get("query") or {}).get("pages", {}).values()
    except ValueError:      # 위키 쪽 일시 오류·제한 — 이번엔 건너뜀
        return []


def text(md, k):
    return html.unescape(re.sub(r"<[^>]+>", "", (md.get(k) or {}).get("value", ""))).strip()


def run(key, name, maxn=4):
    words = core_words(name)
    if not words:
        return {"key": key, "skip": "검색어 없음"}
    s = requests.Session()
    folder = ROOT / "photos" / "site" / key
    idx_p = folder / "index.json"
    idx = json.loads(idx_p.read_text()) if idx_p.exists() else {"key": key, "name": name, "images": [], "links": []}
    if idx.get("commons_checked") == name:
        return {"key": key, "skip": "이미 찾아봄"}
    have = {im.get("src") for im in idx["images"]}
    got = []
    queries = [" ".join(words), words[0]] if len(words) > 1 else [words[0]]
    for q in queries:
        for pg in search(q, s):
            ii = (pg.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata") or {}
            lic = text(md, "LicenseShortName")
            if not lic or BAD_LIC.search(lic) or not OK_LIC.search(lic):
                continue
            hay = (pg.get("title", "") + " " + text(md, "ImageDescription") + " " + text(md, "ObjectName"))
            if not all(w in hay for w in words[:2] if len(w) >= 3) and not (len(words) == 1 and words[0] in hay):
                continue                       # 단지 이름 핵심 낱말이 없으면 다른 곳 사진
            if ii.get("width", 0) < 900 or ii.get("descriptionurl") in have:
                continue
            try:
                b = s.get(ii.get("thumburl") or ii["url"], headers=UA, timeout=60).content
                from PIL import Image
                im = Image.open(io.BytesIO(b)).convert("RGB")
            except Exception:  # noqa: BLE001
                continue
            folder.mkdir(parents=True, exist_ok=True)
            n = sum(1 for x in idx["images"] if x["cat"] == "commons") + 1
            dst = folder / f"commons-{n}.jpg"
            im.save(dst, "JPEG", quality=88)
            artist = re.sub(r"\s+", " ", text(md, "Artist"))[:40] or "작성자 미상"
            idx["images"].append({"cat": "commons", "kind": "실사", "label": pg.get("title", "")[5:80], "file": str(dst.relative_to(ROOT)),
                                  "src": ii.get("descriptionurl"), "w": im.width, "h": im.height, "photo": True,
                                  "full": im.width >= 1000, "from": "commons", "license": lic,
                                  "credit": f"사진: {artist} · {lic} (위키미디어 커먼즈)",
                                  "md5": hashlib.md5(dst.read_bytes()).hexdigest()})
            have.add(ii.get("descriptionurl"))
            got.append(dst.name)
            if len(got) >= maxn:
                break
        if len(got) >= maxn:
            break
    idx["commons_checked"] = name
    idx_p.parent.mkdir(parents=True, exist_ok=True)
    idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    return {"key": key, "words": words, "commons": got}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("name")
    ap.add_argument("--max", type=int, default=4)
    a = ap.parse_args()
    print(json.dumps(run(a.key, a.name, a.max), ensure_ascii=False))
