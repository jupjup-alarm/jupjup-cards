"""LH청약플러스 공고 첨부파일 → 공고문 글자·팸플릿 이미지 후보 (2026-11-04 사용자 요청 "LH 공고 페이지에 항상 pdf가 있는데 못 가져와?").

LH 공고 상세 페이지(source_url)의 첨부파일 목록(fileDownLoad('id'))을 읽어, 공개 내려받기 주소
https://apply.lh.or.kr/lhapply/lhFile.do?fileid=<id> 로 PDF를 받는다. 차단·오류면 건너뛴다 (우회하지 않음).

사용:
  python3 tools/lh_files.py lh0000061199            # 한 공고
  python3 tools/lh_files.py --all                    # site/data/apt/lh*.json 전부
  python3 tools/lh_files.py --all --upcoming         # 접수 마감 전인 것만
  python3 tools/lh_files.py lh0000061199 --pamphlet  # 팸플릿 이미지 후보도 뽑기
  python3 tools/lh_files.py lh0000061205 --url "<LH 공고 상세 주소>"   # 사이트 json이 아직 없는 새 공고
  python3 tools/lh_files.py lh2015122300020958 --url "<주소>" --images  # 단지 그림 받기 (2026-11-10, 아래)
결과 (저장소에 올리는 것):
  site/data/notice_files/<key>.json   첨부 목록 {name, fileid, kind(notice|pamphlet|form|other), md5, pages, got}, changed(바뀌었으면 true)
  site/data/notice_text/<key>.txt     공고문 PDF 글자 (pdftotext -layout) — 사이트 발행 담당이 자격·납부조건·동호·옵션을 채울 때 읽는다
결과 (올리지 않는 것 — 작업 폴더):
  .cache/lh/<key>/*.pdf               받은 PDF
  .cache/lh/<key>/cand/*.jpg          --pamphlet: 팸플릿 큰 이미지 후보 + 쪽 렌더, contact.jpg (Read로 보고 골라 photos/site/<key>/에 넣기)

--images (2026-11-10 사용자 결정 "단지 자료를 더 받아 최대한 활용 — 이야기형 릴스가 사진 1장을 돌려씀"):
  LH 공고 상세의 '단지 관련 이미지 정보'(블록마다 단지조감도·전경사진·지구조감도·지역조감도·위치도·단지배치도·동호배치도)와
  평면도 탭(주택형 평면도 + 실내 투시도)을 같은 공개 내려받기 주소(lhFile.do?fileid=)로 받아
  photos/site/<key>/ + index.json(site_photos.py와 같은 형식, owner "LH") + contact.jpg 로 저장한다 (저장소에 올림).
  사업주체(LH) 공식 홍보 이미지 = CLAUDE.md 사진 출처 ③. 출처 문구 "이미지: LH 공고 단지정보 · 실제와 다를 수 있음".
  분류: 단지조감도·전경사진 → birdseye(전경사진은 kind "외관") · 지구/지역조감도·위치도 → location · 단지배치도 → siteplan ·
        동호배치도 → dongho · 평면도 → plan · 투시도 → interior.  평면도·투시도는 블록마다 주택형 3개까지.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
APT = ROOT / "site" / "data" / "apt"
OUT_F = ROOT / "site" / "data" / "notice_files"
OUT_T = ROOT / "site" / "data" / "notice_text"
CACHE = ROOT / ".cache" / "lh"
DL = "https://apply.lh.or.kr/lhapply/lhFile.do?fileid={}"


def kind_of(name):
    n = name.replace(" ", "")
    if not n.lower().endswith(".pdf"):
        return "other"
    if re.search(r"팜플렛|팸플렛|팸플릿|팜플릿|카탈로그|브로슈어", n):
        return "pamphlet"
    if re.search(r"서식|신청서|동의서|위임장|확인서|매뉴얼|안내문|체크리스트|양식", n):
        return "form"
    if re.search(r"모집|공고", n):
        return "notice"
    return "other"


def attachments(page):
    out, seen = [], set()
    for m in re.finditer(r"fileDownLoad\('(\d+)'\);?\"?>([^<]+)</a>", page):
        fid, name = m.group(1), html.unescape(m.group(2)).strip()
        if fid in seen:
            continue
        seen.add(fid)
        out.append({"fileid": fid, "name": name, "kind": kind_of(name)})
    return out


def pdf_pages(p):
    try:
        info = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=60).stdout
        m = re.search(r"Pages:\s+(\d+)", info)
        return int(m.group(1)) if m else 0
    except Exception:  # noqa: BLE001
        return 0


def pamphlet_cands(pdf, folder):
    """팸플릿에서 큰 이미지(긴 변 1000px+)와 쪽 렌더(110dpi)를 뽑아 contact.jpg로 모은다."""
    from PIL import Image, ImageDraw
    folder.mkdir(parents=True, exist_ok=True)
    stem = pdf.stem[:20]
    subprocess.run(["pdfimages", "-j", str(pdf), str(folder / f"{stem}-img")], capture_output=True, timeout=600)
    subprocess.run(["pdftoppm", "-r", "60", "-jpeg", str(pdf), str(folder / f"{stem}-page")], capture_output=True, timeout=600)
    keep = []
    for f in sorted(folder.glob(f"{stem}-img-*")):
        try:
            with Image.open(f) as im:
                ok = f.suffix == ".jpg" and max(im.size) >= 1000 and min(im.size) >= 400
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            keep.append(f)
        else:
            f.unlink(missing_ok=True)
    tiles = keep + sorted(folder.glob(f"{stem}-page-*.jpg"))
    tw, th, cols = 260, 200, 6
    rows = (len(tiles) + cols - 1) // cols
    if not tiles:
        return []
    sheet = Image.new("RGB", (cols * tw, rows * (th + 18)), "white")
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 18)
        with Image.open(f) as im:
            im = im.convert("RGB")
            im.thumbnail((tw - 6, th - 6))
            sheet.paste(im, (x + 3, y + 3))
        d.text((x + 4, y + th), f.name[-22:], fill="red")
    sheet.save(folder / f"contact-{stem}.jpg", quality=80)
    return [str(f.relative_to(ROOT)) for f in keep]


IMG_TABS = {"단지조감도": ("birdseye", "조감도"), "전경사진": ("birdseye", "외관"), "지구조감도": ("location", "입지"),
            "지역조감도": ("location", "입지"), "위치도": ("location", "입지"), "단지배치도": ("siteplan", "단지배치도"),
            "동호배치도": ("dongho", "동호배치도")}
PLANS_PER_BLOCK = 2   # 2026-11-10 저장소 크기 — 블록마다 주택형 2개(평면도+투시도)


def _blk_slug(name, i):
    m = re.search(r"([A-Za-z]{1,3}\d*(?:-\d+)?|지원\d+(?:-\d+)?|[가-힣]{1,4}\d+(?:-\d+)?)\s*(?:블록|BL|단지)", name)
    s = re.sub(r"[^0-9a-zA-Z]+", "-", (m.group(1) if m else "")).strip("-").lower()
    return s or f"b{i + 1}"


def gallery(page):
    """공고 상세 HTML → [{block, blk, tab, sn, desc}] (단지 관련 이미지 탭) + 평면도·투시도."""
    bl = {int(a): html.unescape(x).strip() for a, x in re.findall(r"changeTab\('(\d+)'\);\"\s+id=\"tagA\d+\"[^>]*>([^<]+)<", page)}
    blocks = [bl.get(i, f"블록{i + 1}") for i in range(max(bl) + 1)] if bl else []
    tabs = {(a, b): n.strip() for a, b, n in re.findall(r"onchangeImageTab\('(\d+)','(\d+)'\);\" id=\"tabPlanA\d+\">([^<]+)<", page)}
    out, k = [], {}
    i = page.find("function onchangeImageTab")
    j = page.find("tabSize = list.length", i)
    body = page[i:j] if i >= 0 and j > i else ""
    for no1, sn, desc in re.findall(r'if\((\d+) == no1\)\{\s*list\.push\(\{\s*cmnAhflSn\s*:\s*"(\d+)".*?imgAhflDesc\s*:\s*"([^"]*)"', body, re.S):
        n = k.get(no1, 0)
        k[no1] = n + 1
        b = int(no1)
        name = blocks[b] if b < len(blocks) else f"블록{b + 1}"
        out.append({"block": name, "blk": _blk_slug(name, b), "tab": tabs.get((no1, str(n)), ""), "sn": sn,
                    "desc": re.sub(r"<[^>]+>", " ", html.unescape(desc)).strip()})
    m = re.search(r"wrtancFloorplan\s*=\s*JSON\.parse\('(.*?)'\)\s*;", page, re.S)
    if m:
        try:
            fp = json.loads(m.group(1).replace("\\'", "'"))
        except Exception:  # noqa: BLE001
            fp = []
        for b, grp in enumerate(fp):
            name = blocks[b] if b < len(blocks) else f"블록{b + 1}"
            seen = []
            for it in grp or []:
                hty = (it.get("htyNna") or "").split("/")[0].strip()
                if hty in seen:
                    continue
                if len(seen) >= PLANS_PER_BLOCK:
                    break
                seen.append(hty)
                out.append({"block": name, "blk": _blk_slug(name, b), "tab": "평면도", "sn": str(it.get("cmnAhflSn") or ""), "hty": hty,
                            "desc": (it.get("imgAhflDesc") or "")[:200]})
                if it.get("perspective") == "Y" and it.get("persCmnAhflSn"):
                    out.append({"block": name, "blk": _blk_slug(name, b), "tab": "투시도", "sn": str(it["persCmnAhflSn"]), "hty": hty,
                                "desc": (it.get("imgAhflDesc") or "")[:200]})
    return out


def save_images(key, page, s):
    """--images: 공고 상세의 단지 그림을 photos/site/<key>/에 받는다 (이미 받은 fileid는 건너뜀)."""
    sys.path.insert(0, str(ROOT / "tools"))
    import site_photos as sp   # save·photo_like·contact·KINDS 재사용 (같은 index.json 형식)
    items = gallery(page)
    folder = ROOT / "photos" / "site" / key
    idx_path = folder / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else {"key": key, "images": [], "links": []}
    idx.setdefault("owner", "LH")
    idx.setdefault("source", "LH청약플러스 공고 상세 '단지 관련 이미지 정보'·평면도 탭")
    have = {im["src"] for im in idx["images"]}
    used = {Path(im["file"]).name for im in idx["images"]}
    new, warn, done = 0, [], set()
    for it in items:
        src = DL.format(it["sn"])
        if not it["sn"] or src in have or it["sn"] in done:
            continue
        done.add(it["sn"])
        if it["tab"] in IMG_TABS:
            cat, kind = IMG_TABS[it["tab"]]
        elif it["tab"] == "평면도":
            cat, kind = "plan", "평면도"
        elif it["tab"] == "투시도":
            cat, kind = "interior", "인테리어"
        else:
            continue
        maxside = sp.KINDS.get(kind, (cat, 2400))[1]
        label = f"{it['block']} {it['tab']}" + (f" {it['hty']}" if it.get("hty") else "")
        base = f"{cat}-{it['blk']}" + (f"-{sp.slug(it['hty'])}" if it.get("hty") and sp.slug(it["hty"]) else "")
        name, n = f"{base}.jpg", 2
        while name in used:
            name, n = f"{base}-{n}.jpg", n + 1
        try:
            r = s.get(src, timeout=60)
            if r.status_code != 200 or len(r.content) < 2000:
                warn.append(f"{label}: {r.status_code}")
                continue
            w, h = sp.save(r.content, folder / name, maxside)
        except Exception as e:  # noqa: BLE001
            warn.append(f"{label}: {str(e)[:80]}")
            continue
        used.add(name)
        rec = {"cat": cat, "kind": kind, "label": label, "file": f"photos/site/{key}/{name}", "src": src, "crop": "",
               "w": w, "h": h, "md5": hashlib.md5(r.content).hexdigest(), "block": it["block"], "lh_tab": it["tab"],
               "desc": it["desc"][:160]}
        rec["photo"] = sp.photo_like(folder / name) and cat in ("birdseye", "location", "interior", "community")
        idx["images"].append(rec)
        new += 1
        time.sleep(0.4)
    if new or not idx_path.exists():
        idx["updated"] = time.strftime("%Y-%m-%d %H:%M")
        order = list(dict.fromkeys(v[0] for v in sp.KINDS.values()))
        idx["images"].sort(key=lambda im: order.index(im["cat"]) if im["cat"] in order else 99)
        folder.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
        sp.contact(folder, idx["images"])
    cats = {}
    for im in idx["images"]:
        cats[im["cat"]] = cats.get(im["cat"], 0) + 1
    return {"folder": f"photos/site/{key}", "found": len(items), "new": new, "total": len(idx["images"]),
            "photos": sum(1 for im in idx["images"] if im.get("photo")), "by_cat": cats, "warnings": warn[:10]}


def run(key, s, pamphlet=False, url=None, images=False):
    if url is None:   # 사이트 공고 json의 source_url (아직 페이지가 없는 새 공고는 --url로 — ① 조사 API가 씀, 2026-11-05)
        f = APT / f"{key}.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        url = d.get("source_url") or ""
    if "apply.lh.or.kr" not in url:
        return {"key": key, "skip": "LH청약플러스 주소 없음"}
    r = s.get(url, timeout=30)
    if r.status_code != 200 or "fileDownLoad" not in r.text:
        return {"key": key, "skip": f"공고 페이지 {r.status_code} · 첨부 목록 없음 (우회하지 않음)"}
    imgs = save_images(key, r.text, s) if images else None
    atts = attachments(r.text)
    old_p = OUT_F / f"{key}.json"
    old = json.loads(old_p.read_text()) if old_p.exists() else {}
    old_md5 = {a["fileid"]: a.get("md5") for a in old.get("files", [])}
    folder = CACHE / key
    folder.mkdir(parents=True, exist_ok=True)
    texts, cands = [], []
    for a in atts:
        if a["kind"] not in ("notice", "pamphlet"):
            continue
        dst = folder / f"{a['fileid']}.pdf"
        if not dst.exists():
            rr = s.get(DL.format(a["fileid"]), timeout=120)
            if rr.status_code != 200 or not rr.content.startswith(b"%PDF"):
                a["got"] = f"실패 {rr.status_code}"
                continue
            dst.write_bytes(rr.content)
            time.sleep(0.5)
        a["got"] = "ok"
        a["md5"] = hashlib.md5(dst.read_bytes()).hexdigest()
        a["pages"] = pdf_pages(dst)
        a["bytes"] = dst.stat().st_size
        if a["kind"] == "notice":
            t = subprocess.run(["pdftotext", "-layout", str(dst), "-"], capture_output=True, text=True, timeout=300).stdout
            texts.append(f"===== {a['name']} ({a['pages']}쪽) =====\n{t}")
        elif pamphlet:
            cands += pamphlet_cands(dst, folder / "cand")
    changed = bool(old) and any(old_md5.get(a["fileid"]) != a.get("md5") for a in atts if a.get("md5")) or \
        bool(old) and {a["fileid"] for a in atts} != set(old_md5)
    rec = {"key": key, "source_url": url, "checked": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "files": atts, "changed": changed or not old}
    OUT_F.mkdir(parents=True, exist_ok=True)
    old_p.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if texts:
        OUT_T.mkdir(parents=True, exist_ok=True)
        (OUT_T / f"{key}.txt").write_text("\n\n".join(texts), encoding="utf-8")
    return {"key": key, "notice": sum(a["kind"] == "notice" and a.get("got") == "ok" for a in atts),
            "pamphlet": sum(a["kind"] == "pamphlet" and a.get("got") == "ok" for a in atts),
            "new_or_changed": rec["changed"], "cands": len(cands),
            "contact": [str(p.relative_to(ROOT)) for p in (folder / "cand").glob("contact-*.jpg")] if pamphlet else [],
            **({"images": imgs} if imgs is not None else {})}


def upcoming(d, today):
    r = d.get("rcpt") or d.get("receipt_override") or []
    end = r[-1] if isinstance(r, list) and r else ""
    return not end or end >= today


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--upcoming", action="store_true", help="--all과 함께: 접수 마감 전인 공고만")
    ap.add_argument("--pamphlet", action="store_true")
    ap.add_argument("--images", action="store_true", help="공고 상세의 단지 그림(조감도·전경·배치도·평면도·투시도) → photos/site/<key>/")
    ap.add_argument("--url", help="LH청약플러스 공고 상세 주소 (사이트 json이 없는 새 공고) — key 하나와 함께")
    a = ap.parse_args()
    keys = list(a.keys)
    if a.all:
        today = dt.date.today().isoformat()
        for f in sorted(APT.glob("lh*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            if not a.upcoming or upcoming(d, today):
                keys.append(d["key"])
    if not keys:
        sys.exit("공고 key를 주거나 --all")
    s = requests.Session()
    s.headers["User-Agent"] = "jupjup-alarm/1.0 (+https://jupjupalarm.com)"
    if a.url and len(keys) != 1:
        sys.exit("--url은 key 하나와 함께")
    for k in dict.fromkeys(keys):
        try:
            print(json.dumps(run(k, s, a.pamphlet, a.url, a.images), ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"key": k, "error": str(e)[:200]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
