"""단지 자료 수집기 — 하나로 (2026-11-10 사용자 결정 "사진 수집이 중구난방 — 하나의 수집기로 릴스·SEO·블로그 모두").

'청약조사' 마감 전 단지마다 그림·공고문을 한 곳에 모은다. 모델 호출 없음 (비용 0).
  photos/site/<key>/            그림 (분류별 jpg)
  photos/site/<key>/index.json  {key, name, row, owner, images:[{cat, kind, label, file, src, w, h, photo, from, checked?, ok?, name_shown?, full?}]}
  site/data/notice_text/<key>.txt  공고문 글자 (LH는 여기서, 청약홈은 Mac ego lite → notice_import.py)
  site/data/assets_map.json     {단지명: {key, row, count, photos, checked}} — ④ 릴스·⑦ SEO·청약노트 블로그가 단지 이름으로 key를 찾는다

어디서 받나 (우선순위, 이미 받은 것은 건너뜀):
  1. LH 공고(청약조사 '출처 URL'이 apply.lh.or.kr …panId=) → tools/lh_files.py --images (단지조감도·전경·지구조감도·배치도·평면도·투시도 + 공고문)
  2. 분양 홈페이지 자료 — '홈페이지 자료'(AI열, 사람이 고른 주소)가 있으면 tools/site_photos.py,
     없고 '공식 홈페이지'/청약홈 '홈페이지' 주소가 있으면 tools/site_assets.py로 훑어 분류별 상위 몇 장을 자동으로 넣는다 (from "auto", 검수 전)
  3. 청약홈 팸플릿 그림 pamphlets/<key>/cand-*.jpg (Mac ego lite → notice_import.py) → cat "pamphlet" (검수에서 분류)
  4. 시트 스크립트가 받아 둔 파일 — 사진 파일(AA)·평면도 파일(AC)·배치도 파일(AE)·동호배치도 파일(AG): 복사하지 않고 index에 경로만 등록
검수(분류·이름/로고·풀화면 가능 여부)는 jupjup-runner runner/qc.py(API Sonnet, 새 그림만 한 번)가 index.json에 적는다.

사용:
  python3 tools/collect.py                 # site/data/sheet/research.json(실행기 sheetdump.py가 내려 둔 '청약조사') 기준
  python3 tools/collect.py --only 43 52    # 그 행만
  python3 tools/collect.py --max-sites 3   # 홈페이지 새로 훑기는 한 번에 최대 N곳 (기본 3 — 시간)
규칙: 차단(401·403·406·429)·robots 금지는 우회하지 않는다 (각 도구 규칙 그대로).
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import site_photos as sp  # noqa: E402

SHEET = ROOT / "site" / "data" / "sheet" / "research.json"
APPLY = ROOT / "site" / "data" / "applyhome.json"
MAP = ROOT / "site" / "data" / "assets_map.json"
SITE = ROOT / "photos" / "site"
CACHE = ROOT / ".cache" / "site_assets"
SKIP_TYPES = ("부동산뉴스", "청약상식")
# 홈페이지 자동 수집 → index 분류 (site_assets.py 분류 → 우리 분류, 분류마다 최대 장수)
AUTO = {"birdseye": ("birdseye", 6), "overview": ("overview", 3), "site_plan": ("siteplan", 2), "dongho": ("dongho", 2),
        "unit_plan": ("plan", 6), "community": ("community", 8), "interior": ("interior", 6), "location": ("location", 3)}
SHEET_COLS = [("사진 파일", "birdseye", "조감도"), ("평면도 파일", "plan", "평면도"), ("배치도 파일", "siteplan", "단지배치도"),
              ("동호배치도 파일", "dongho", "동호배치도")]


def log(*a):
    print(*a, flush=True)


def today():
    return dt.date.today().isoformat()


def load_idx(key):
    p = SITE / key / "index.json"
    return json.loads(p.read_text()) if p.exists() else {"key": key, "images": [], "links": []}


def save_idx(key, idx):
    (SITE / key).mkdir(parents=True, exist_ok=True)
    order = ["birdseye", "overview", "location", "community", "interior", "siteplan", "dongho", "plan", "pamphlet"]
    idx["images"].sort(key=lambda im: order.index(im["cat"]) if im["cat"] in order else 99)
    idx["updated"] = time.strftime("%Y-%m-%d %H:%M")
    (SITE / key / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    try:
        sp.contact(SITE / key, [im for im in idx["images"] if str(im["file"]).startswith(f"photos/site/{key}/")])
    except Exception as e:  # noqa: BLE001
        log("  contact 실패:", e)


def key_of(r, apply_rows):
    """단지 key: LH 공고 lh<panId> / 청약홈 주택관리번호 / AI열 key / 청약홈API 이름 매칭."""
    url = r.get("출처 URL", "") + " " + r.get("공식 홈페이지", "")
    m = re.search(r"apply\.lh\.or\.kr\S*panId=(\d+)", url)
    if m:
        lh_url = re.search(r"https?://apply\.lh\.or\.kr\S*panId=\d+\S*", url).group(0)
        return "lh" + m.group(1), lh_url
    m = re.search(r"key\s*[:：]\s*([0-9A-Za-z_-]+)", r.get("홈페이지 자료", ""))
    if m:
        return m.group(1), ""
    m = re.search(r"houseManageNo=(\d+)", url)
    if m:
        return m.group(1), ""
    name = re.sub(r"\(.*?\)|\s", "", r.get("단지명", ""))[:8]
    for a in apply_rows:
        if name and name in re.sub(r"\s", "", a.get("주택명", "")):
            return str(a.get("주택관리번호", "")), ""
    return "", ""


def homepage_of(r, key, apply_rows):
    for u in (r.get("공식 홈페이지", ""), *(a.get("홈페이지", "") for a in apply_rows if str(a.get("주택관리번호")) == key)):
        u = (u or "").strip()
        if u.startswith("http") and "apply.lh.or.kr" not in u and "applyhome" not in u:
            return u
    return ""


def add_sheet_files(r, key, idx):
    have = {im["file"] for im in idx["images"]}
    n = 0
    for col, cat, kind in SHEET_COLS:
        for ln in (r.get(col) or "").splitlines():
            parts = [p.strip() for p in ln.split("|")]
            f = next((p for p in parts if p.startswith("photos/")), "")
            if not f or f in have or not (ROOT / f).exists():
                continue
            label = parts[0] if parts[0] and not parts[0].startswith("photos/") else kind
            try:
                from PIL import Image
                with Image.open(ROOT / f) as im:
                    w, h = im.size
                photo = sp.photo_like(ROOT / f)
            except Exception:  # noqa: BLE001
                continue
            idx["images"].append({"cat": cat, "kind": kind, "label": label, "file": f, "src": f"sheet:{col}", "w": w, "h": h,
                                  "photo": photo and cat == "birdseye", "from": "sheet"})
            have.add(f)
            n += 1
    return n


def add_pamphlet(key, idx):
    folder = ROOT / "pamphlets" / key
    have = {im["src"] for im in idx["images"]}
    n = 0
    for f in sorted(folder.glob("cand-*.jpg")) if folder.exists() else []:
        src = f"pamphlet:{f.name}"
        if src in have:
            continue
        try:
            from PIL import Image
            with Image.open(f) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001
            continue
        idx["images"].append({"cat": "pamphlet", "kind": "팸플릿", "label": f"팸플릿 {f.stem}", "file": str(f.relative_to(ROOT)),
                              "src": src, "w": w, "h": h, "photo": sp.photo_like(f), "from": "pamphlet"})
        n += 1
    return n


def auto_site(key, url, idx):
    """분양 홈페이지를 site_assets.py로 훑어 분류별 상위 몇 장을 photos/site/<key>/에 넣는다 (검수 전 표시)."""
    import subprocess
    out = CACHE / key
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "site_assets.py"), "--url", url, "--out", str(out), "--engine", "static",
                        "--max-pages", "25"], capture_output=True, text=True, timeout=600)
    man_p = out / "manifest.json"
    if not man_p.exists():
        idx["auto_site"] = {"date": today(), "url": url, "result": f"실패 {(r.stderr or r.stdout)[-160:]}"}
        return 0
    man = json.loads(man_p.read_text())
    if man.get("blocked"):
        idx["auto_site"] = {"date": today(), "url": url, "result": f"홈페이지 차단: {str(man['blocked'])[:120]}"}
        return 0
    have = {im["src"] for im in idx["images"]}
    used = {Path(im["file"]).name for im in idx["images"]}
    cnt, n = {}, 0
    for im in man.get("images", []):
        c = AUTO.get(im.get("category"))
        if not c or not im.get("use_ok", True):
            continue
        cat, cap = c
        src = im.get("src") or im.get("url") or im["file"]
        if src in have or cnt.get(cat, 0) >= cap or min(im.get("w", 0), im.get("h", 0)) < 400:
            continue
        name, k = f"{cat}-auto-{cnt.get(cat, 0) + 1}.jpg", 2
        while name in used:
            name, k = f"{cat}-auto-{cnt.get(cat, 0) + 1}-{k}.jpg", k + 1
        try:
            w, h = sp.save((out / im["file"]).read_bytes(), SITE / key / name, sp.KINDS.get("조감도")[1])
        except Exception as e:  # noqa: BLE001
            log("  저장 실패:", e)
            continue
        idx["images"].append({"cat": cat, "kind": cat, "label": (im.get("alt") or "")[:40] or cat, "file": f"photos/site/{key}/{name}",
                              "src": src, "w": w, "h": h, "photo": bool(im.get("photo")), "from": "auto"})
        used.add(name)
        cnt[cat] = cnt.get(cat, 0) + 1
        n += 1
    seen = {l.get("url") for l in idx.get("links", [])}
    for l in man.get("links", []):
        if l.get("url") and l["url"] not in seen and l.get("kind") in ("emodel", "vr"):
            idx.setdefault("links", []).append({"kind": l["kind"], "label": l.get("label", ""), "name": l.get("kind"), "url": l["url"]})
    idx.setdefault("homepage", url)
    idx["auto_site"] = {"date": today(), "url": url, "result": f"{n}장 ({', '.join(f'{k} {v}' for k, v in cnt.items())})"}
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", type=int, help="'청약조사' 행 번호만")
    ap.add_argument("--max-sites", type=int, default=3)
    ap.add_argument("--max-lh", type=int, default=12)
    a = ap.parse_args()
    rows = json.loads(SHEET.read_text())["rows"]
    apply_rows = json.loads(APPLY.read_text()).get("rows", []) if APPLY.exists() else []
    amap = json.loads(MAP.read_text()) if MAP.exists() else {}
    t0 = today()
    s = requests.Session()
    s.headers["User-Agent"] = "jupjup-alarm/1.0 (+https://jupjupalarm.com)"
    import lh_files
    sites = lh = 0
    report = []
    for r in rows:
        if a.only and r["_row"] not in a.only:
            continue
        if r.get("분류") in SKIP_TYPES or (r.get("접수 마감") and r["접수 마감"] < t0):
            continue
        key, lh_url = key_of(r, apply_rows)
        if not key:
            continue
        idx = load_idx(key)
        idx.setdefault("name", r.get("단지명", ""))
        idx["row"] = r["_row"]
        before = len(idx["images"])
        note = []
        if lh_url and lh < a.max_lh and idx.get("lh_checked") != t0:
            try:
                res = lh_files.run(key, s, url=lh_url, images=True)
                idx = load_idx(key)          # lh_files가 index를 썼음
                idx.setdefault("name", r.get("단지명", ""))
                idx["row"] = r["_row"]
                idx["lh_checked"] = t0
                note.append(f"LH {res.get('images', {}).get('new', 0)}장" if "images" in res else f"LH {res.get('skip', '')}")
            except Exception as e:  # noqa: BLE001
                note.append(f"LH 실패 {str(e)[:60]}")
            lh += 1
        ai = r.get("홈페이지 자료", "")
        if re.search(r"^\s*key\s*[:：]", ai, re.M) and "|" in ai and idx.get("ai_hash") != hashlib.md5(ai.encode()).hexdigest():
            import subprocess
            p = subprocess.run([sys.executable, str(ROOT / "tools" / "site_photos.py"), "--text", ai], capture_output=True, text=True, timeout=600)
            idx = load_idx(key)
            idx.setdefault("name", r.get("단지명", ""))
            idx["row"] = r["_row"]
            idx["ai_hash"] = hashlib.md5(ai.encode()).hexdigest()
            note.append("AI열 " + ("받음" if p.returncode == 0 else f"실패 {p.stderr[-80:]}"))
        else:
            hp = homepage_of(r, key, apply_rows)
            if hp and not lh_url and "auto_site" not in idx and sites < a.max_sites:
                note.append("홈페이지 " + str(auto_site(key, hp, idx)) + "장")
                sites += 1
        n_sheet = add_sheet_files(r, key, idx)
        n_pam = add_pamphlet(key, idx)
        if n_sheet:
            note.append(f"시트 {n_sheet}")
        if n_pam:
            note.append(f"팸플릿 {n_pam}")
        if len(idx["images"]) != before or note:
            save_idx(key, idx)
        ims = idx["images"]
        amap[r.get("단지명", "")] = {"key": key, "row": r["_row"], "count": len(ims), "photos": sum(1 for x in ims if x.get("photo")),
                                    "checked": sum(1 for x in ims if x.get("checked"))}
        if note:
            report.append(f"{r['_row']}행 {r.get('단지명', '')[:18]} → {key}: {' · '.join(note)} (총 {len(ims)})")
    MAP.write_text(json.dumps(amap, ensure_ascii=False, indent=1))
    print("\n".join(report) or "새로 받은 것 없음")
    print(json.dumps({"lh": lh, "sites": sites, "keys": len(amap)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
