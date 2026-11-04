"""LH청약플러스 공고 첨부파일 → 공고문 글자·팸플릿 이미지 후보 (2026-11-04 사용자 요청 "LH 공고 페이지에 항상 pdf가 있는데 못 가져와?").

LH 공고 상세 페이지(source_url)의 첨부파일 목록(fileDownLoad('id'))을 읽어, 공개 내려받기 주소
https://apply.lh.or.kr/lhapply/lhFile.do?fileid=<id> 로 PDF를 받는다. 차단·오류면 건너뛴다 (우회하지 않음).

사용:
  python3 tools/lh_files.py lh0000061199            # 한 공고
  python3 tools/lh_files.py --all                    # site/data/apt/lh*.json 전부
  python3 tools/lh_files.py --all --upcoming         # 접수 마감 전인 것만
  python3 tools/lh_files.py lh0000061199 --pamphlet  # 팸플릿 이미지 후보도 뽑기
  python3 tools/lh_files.py lh0000061205 --url "<LH 공고 상세 주소>"   # 사이트 json이 아직 없는 새 공고
결과 (저장소에 올리는 것):
  site/data/notice_files/<key>.json   첨부 목록 {name, fileid, kind(notice|pamphlet|form|other), md5, pages, got}, changed(바뀌었으면 true)
  site/data/notice_text/<key>.txt     공고문 PDF 글자 (pdftotext -layout) — 사이트 발행 담당이 자격·납부조건·동호·옵션을 채울 때 읽는다
결과 (올리지 않는 것 — 작업 폴더):
  .cache/lh/<key>/*.pdf               받은 PDF
  .cache/lh/<key>/cand/*.jpg          --pamphlet: 팸플릿 큰 이미지 후보 + 쪽 렌더, contact.jpg (Read로 보고 골라 photos/site/<key>/에 넣기)
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


def run(key, s, pamphlet=False, url=None):
    if url is None:   # 사이트 공고 json의 source_url (아직 페이지가 없는 새 공고는 --url로 — ① 조사 API가 씀, 2026-11-05)
        f = APT / f"{key}.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        url = d.get("source_url") or ""
    if "apply.lh.or.kr" not in url:
        return {"key": key, "skip": "LH청약플러스 주소 없음"}
    r = s.get(url, timeout=30)
    if r.status_code != 200 or "fileDownLoad" not in r.text:
        return {"key": key, "skip": f"공고 페이지 {r.status_code} · 첨부 목록 없음 (우회하지 않음)"}
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
            "contact": [str(p.relative_to(ROOT)) for p in (folder / "cand").glob("contact-*.jpg")] if pamphlet else []}


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
            print(json.dumps(run(k, s, a.pamphlet, a.url), ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"key": k, "error": str(e)[:200]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
