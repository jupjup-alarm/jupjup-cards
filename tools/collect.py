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
못 받는 경우 대비 (2026-11-11):
  - 첫 화면이 자바스크립트로 넘기기만 하면(location.href) 넘어간 페이지에서 시작, 한 페이지만 보이거나 그림이 3장 미만이면 브라우저로 다시
  - 'Ⅰ단지·Ⅱ단지 고르기' 안내 화면이면 거기서 연결한 비슷한 주소 중 단지명 번호가 맞는 곳으로
  - 홈페이지에 팸플릿·카탈로그 PDF가 있으면 그 안 큰 그림 → pamphlets/<key>/hp/ (공고문 그림은 notice_import.py가 pamphlets/<key>/notice/)
  - 0장이면 다음 날 다시 (최대 3번, 차단은 다시 안 함) · assets_map에 usable·why → '작업대상' 탭에 '그림 0장'으로 떠서 ① 조사가 손으로
  - --zero-only: 쓸 그림이 0장인 단지만 (⑦ SEO 직전 agent.yml이 한 번 더)
검수(분류·이름/로고·풀화면 가능 여부)는 jupjup-runner runner/qc.py(API Sonnet, 새 그림만 한 번)가 index.json에 적는다.

사용:
  python3 tools/collect.py                 # site/data/sheet/research.json(실행기 sheetdump.py가 내려 둔 '청약조사') 기준
  python3 tools/collect.py --only 43 52    # 그 행만
  python3 tools/collect.py --max-sites 6   # 홈페이지 새로 훑기는 한 번에 최대 N곳 (기본 6, 새 행부터)
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
    # notice_import.py는 pamphlets/<key>/<번호>/, 공고문 그림은 notice/, 홈페이지 PDF는 hp/ 아래에 둔다 (2026-11-11 — 예전엔 바로 아래만 봐서 하나도 안 들어감)
    files = sorted(folder.glob("cand-*.jpg")) + sorted(folder.glob("*/cand-*.jpg")) if folder.exists() else []
    for f in files:
        src = f"pamphlet:{f.relative_to(folder)}"
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
    out = CACHE / key
    man_p = out / "manifest.json"
    tries = (idx.get("auto_site") or {}).get("tries", 0) + 1
    r, weak = crawl_site(url, out)
    via = ""
    if weak:
        # 첫 화면이 'Ⅰ단지·Ⅱ단지 고르기' 같은 안내 화면이면 거기서 연결한 비슷한 주소 중 단지명이 맞는 곳으로 (2026-11-11 수원이목 detre-sw → detre-sw1)
        sib = sibling_site(url, idx.get("name", ""))
        if sib:
            r2, weak2 = crawl_site(sib, out)
            if man_p.exists():
                via, url, r, weak = url, sib, r2, weak2
    if not man_p.exists():
        idx["auto_site"] = {"date": today(), "url": url, "tries": tries, "result": f"실패 {(r.stderr or r.stdout)[-160:]}"}
        return 0
    man = json.loads(man_p.read_text())
    if man.get("blocked"):
        idx["auto_site"] = {"date": today(), "url": url, "tries": 9, "result": f"홈페이지 차단: {str(man['blocked'])[:120]}"}   # 차단은 다시 시도하지 않음
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
    n_pdf = homepage_pdf(key, man, idx)
    idx["auto_site"] = {"date": today(), "url": url, "tries": tries, **({"via": via} if via else {}),
                        "result": f"{n}장 ({', '.join(f'{k} {v}' for k, v in cnt.items())})" + (f" · 팸플릿 PDF 그림 {n_pdf}장" if n_pdf else "")}
    return n


def crawl_site(url, out):
    """static으로 훑고, 쓸 그림이 3장 미만이면 브라우저로 다시 (자바스크립트로 그리는 홈페이지 — 2026-11-11 해링턴 노원 static 3장 → browser 127장)."""
    import subprocess
    man_p = out / "manifest.json"

    def run(engine):
        man_p.unlink(missing_ok=True)
        return subprocess.run([sys.executable, str(ROOT / "tools" / "site_assets.py"), "--url", url, "--out", str(out), "--engine", engine,
                               "--max-pages", "25"], capture_output=True, text=True, timeout=600)

    def is_weak():
        try:
            m = json.loads(man_p.read_text())
            # 한 페이지만 봤으면(자바스크립트로 main.php로 넘기는 첫 화면 등) 메뉴를 못 따라간 것 — 브라우저로 다시
            return sum(1 for im in m.get("images", []) if AUTO.get(im.get("category"))) < 3 or len(m.get("pages", [])) <= 1
        except Exception:  # noqa: BLE001
            return True
    url = js_redirect(url)
    r = run("static")
    if is_weak():
        try:
            import playwright  # noqa: F401
            r = run("browser")
        except ImportError:
            pass
    return r, is_weak()


def js_redirect(url):
    """첫 화면이 자바스크립트로 다른 페이지로 넘기기만 하면(location.href="main.php") 그 페이지에서 시작 (모바일 주소 제외, 한 번만)."""
    from urllib.parse import urljoin
    try:
        h = requests.get(url, timeout=15, headers={"User-Agent": "jupjup-alarm/1.0 (+https://jupjupalarm.com)"})
        h.encoding = h.apparent_encoding or h.encoding
    except requests.RequestException:
        return url
    if h.status_code >= 400 or len(re.findall(r"<a\s", h.text, re.I)) > 8:   # 메뉴가 있는 진짜 페이지면 그대로
        return url
    for t in re.findall(r"""location(?:\.href)?\s*=\s*["']([^"']+)["']|location\.replace\(\s*["']([^"']+)["']""", h.text):
        t = t[0] or t[1]
        if t and not re.search(r"(^|/)m/?$|mobile|^/m[/?]|//m\.", t, re.I):
            u = urljoin(h.url, t)
            if u != h.url:
                # 넘어간 주소가 다시 리다이렉트되면(/web → /web/) 끝 주소로 — 끝 '/'가 없으면 메뉴의 상대 주소(planning.php)가 한 단계 위로 잘못 풀려 한 페이지만 보게 됨 (2026-11-12 고덕 아테라: 스톡사진 3장뿐)
                try:
                    f = requests.get(u, timeout=15, headers={"User-Agent": "jupjup-alarm/1.0 (+https://jupjupalarm.com)"})
                    if f.status_code < 400:
                        u = f.url
                except requests.RequestException:
                    pass
                log(f"  첫 화면이 넘김 → {u}")
                return u
    return url


ROMAN = {"Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅴ": 5, "Ⅵ": 6, "Ⅶ": 7, "Ⅷ": 8, "Ⅸ": 9, "Ⅹ": 10}


def _nums(t):
    """단지 번호 후보 — 'Ⅰ', '1단지', '1차', 'sw1' 같은 것."""
    t = t or ""
    out = {v for k, v in ROMAN.items() if k in t}
    out |= {int(x) for x in re.findall(r"(\d{1,2})\s*(?:단지|블록)", t)}
    return out


def sibling_site(url, name):
    """안내 화면이 연결한 '비슷한 이름' 주소(같은 도메인 줄기 + 숫자) 중 단지명 번호가 맞는 곳. 없으면 ""."""
    from urllib.parse import urljoin, urlparse
    try:
        h = requests.get(url, timeout=15, headers={"User-Agent": "jupjup-alarm/1.0 (+https://jupjupalarm.com)"})
        if h.status_code >= 400:
            return ""
        h.encoding = h.apparent_encoding or h.encoding
        html = h.text
    except requests.RequestException:
        return ""
    host = urlparse(h.url).hostname or ""
    stem = re.sub(r"^www\.", "", host).split(".")[0]
    stem = re.sub(r"\d+$", "", stem)
    if len(stem) < 3:
        return ""
    cands = []
    for href in re.findall(r"""(?:href|location(?:\.href)?\s*=|window\.open\()\s*=?\s*["']([^"']+)["']""", html):
        u = urljoin(h.url, href)
        hh = (urlparse(u).hostname or "").removeprefix("www.")
        if u.startswith("http") and hh and hh != host.removeprefix("www.") and hh.split(".")[0].startswith(stem) and u not in cands:
            cands.append(u)
    if not cands:
        return ""
    want = _nums(name)
    best, score = "", -1
    for u in cands[:6]:
        hh = (urlparse(u).hostname or "").split(".")[0]
        got = {int(x) for x in re.findall(r"(\d{1,2})$", hh)}
        try:
            t = requests.get(u, timeout=12, headers={"User-Agent": "jupjup-alarm/1.0"})
            t.encoding = t.apparent_encoding or t.encoding
            title = (re.search(r"<title[^>]*>(.*?)</title>", t.text, re.S | re.I) or [None, ""])[1]
            got |= _nums(title)
        except requests.RequestException:
            continue
        sc = 2 * len(want & got) - (1 if want and got and not want & got else 0)
        if sc > score:
            best, score = u, sc
    if want and score <= 0 and len(cands) > 1:
        return ""          # 번호가 갈리는데 맞는 곳을 못 찾으면 엉뚱한 단지를 받지 않음
    log(f"  안내 화면 → {best}")
    return best


PDF_WORDS = re.compile(r"팸플릿|팜플렛|카탈로그|브로슈어|리플렛|e-?book|catalog|brochure|leaflet|pamphlet|분양\s*안내", re.I)


def homepage_pdf(key, man, idx):
    """홈페이지에 올라 있는 팸플릿·카탈로그 PDF의 큰 그림 → pamphlets/<key>/hp/cand-NN.jpg (검수에서 분류). 공고문 PDF는 받지 않음."""
    if idx.get("hp_pdf"):
        return 0
    pdfs = [l for l in man.get("links", []) if l.get("kind") == "pdf" and "공고" not in (l.get("text", "") + l.get("href", ""))]
    pick = next((l for l in pdfs if PDF_WORDS.search(l.get("text", "") + " " + l.get("href", ""))), None)
    if not pick:
        return 0
    import tempfile
    try:
        import notice_import as ni
        resp = requests.get(pick["href"], timeout=90, stream=True, headers={"User-Agent": "jupjup-alarm/1.0 (+https://jupjupalarm.com)"})
        if resp.status_code >= 400:
            idx["hp_pdf"] = {"url": pick["href"], "result": f"HTTP {resp.status_code}"}
            return 0
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            size = 0
            for ch in resp.iter_content(1 << 16):
                size += len(ch)
                if size > 80 << 20:
                    raise ValueError("80MB 넘음")
                f.write(ch)
        head = Path(f.name).read_bytes()[:5]
        if head != b"%PDF-":
            idx["hp_pdf"] = {"url": pick["href"], "result": "PDF 아님"}
            return 0
        c = ni.pamphlet_images(Path(f.name), ROOT / "pamphlets" / key / "hp")
        Path(f.name).unlink(missing_ok=True)
        idx["hp_pdf"] = {"url": pick["href"], "date": today(), "result": f"{len(c)}장"}
        return len(c)
    except Exception as e:  # noqa: BLE001
        idx["hp_pdf"] = {"url": pick["href"], "result": f"실패 {str(e)[:80]}"}
        return 0


def usable(idx):
    """페이지·릴스에 쓸 수 있는 그림 수 (검수에서 못 쓴다고 한 것·팸플릿 미분류 제외)."""
    return sum(1 for im in idx.get("images", []) if (ROOT / im["file"]).exists() and im.get("ok", True) is not False and im.get("cat") != "pamphlet")


def need_site(idx, hp):
    """홈페이지를 (다시) 훑을지 — 처음이거나, 주소가 바뀌었거나, 0장이면 다음 날 다시 (최대 3번, 차단은 다시 안 함)."""
    a = idx.get("auto_site")
    if not a:
        return True
    if a.get("url") != hp and a.get("via") != hp:
        return True
    return usable(idx) == 0 and a.get("date") != today() and a.get("tries", 1) < 3


def add_satellite(r, idx):
    """'청약조사' AJ열 위성사진(시트 스크립트 prepareSatellite가 네이버 위성 지도로 받아 둔 photos/sat/…) → index에 'aerial'.
    2026-11-13 사용자 결정 "최대한 건물 실사": 이미 지어진 임대 단지처럼 홍보 사진이 없는 곳의 실제 모습."""
    v = (r.get("위성사진") or "").strip()
    if not v.startswith("photos/") or not (ROOT / v).exists():
        return 0
    if any(im.get("file") == v for im in idx["images"]):
        return 0
    from PIL import Image
    w, h = Image.open(ROOT / v).size
    idx["images"].append({"cat": "aerial", "kind": "위성사진", "label": "위성사진", "file": v, "src": "NAVER 위성 지도",
                          "w": w, "h": h, "photo": True, "full": True, "ok": True, "checked": True, "from": "satellite",
                          "credit": "위성사진 © NAVER Corp."})
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", type=int, help="'청약조사' 행 번호만")
    ap.add_argument("--max-sites", type=int, default=12)   # 2026-11-13 6→12 (사진 없는 공고 줄이기)
    ap.add_argument("--max-lh", type=int, default=12)
    ap.add_argument("--zero-only", action="store_true", help="쓸 그림이 0장인 단지만 (⑦ 직전 재수집, 2026-11-11)")
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
    # 새로 들어온 행(아래쪽)부터 — 홈페이지 수집 칸(max-sites)을 오래된 행이 먼저 다 쓰지 않게 (2026-11-11)
    for r in sorted(rows, key=lambda x: -x["_row"]):
        if a.only and r["_row"] not in a.only:
            continue
        if r.get("분류") in SKIP_TYPES or (r.get("접수 마감") and r["접수 마감"] < t0):
            continue
        key, lh_url = key_of(r, apply_rows)
        if not key:
            continue
        idx = load_idx(key)
        skip = a.zero_only and usable(idx) > 0     # --zero-only: 그림 있는 단지는 새로 받지 않고 지도(assets_map)만 갱신
        idx.setdefault("name", r.get("단지명", ""))
        idx["row"] = r["_row"]
        before = len(idx["images"])
        note = []
        if not skip and lh_url and lh < a.max_lh and idx.get("lh_checked") != t0:
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
        if not skip and re.search(r"^\s*key\s*[:：]", ai, re.M) and "|" in ai and idx.get("ai_hash") != hashlib.md5(ai.encode()).hexdigest():
            import subprocess
            p = subprocess.run([sys.executable, str(ROOT / "tools" / "site_photos.py"), "--text", ai], capture_output=True, text=True, timeout=600)
            idx = load_idx(key)
            idx.setdefault("name", r.get("단지명", ""))
            idx["row"] = r["_row"]
            idx["ai_hash"] = hashlib.md5(ai.encode()).hexdigest()
            note.append("AI열 " + ("받음" if p.returncode == 0 else f"실패 {p.stderr[-80:]}"))
            m2 = re.search(r"key\s*[:：]\s*([0-9A-Za-z_-]+)", ai)
            if m2 and m2.group(1) != key:   # LH 공고 + 분양 홈페이지(AI열 key가 다름) → 한 단지 index로 합침 (파일은 그 폴더에 둔 채 경로만)
                other = load_idx(m2.group(1))
                have = {im["file"] for im in idx["images"]}
                for im in other.get("images", []):
                    if im["file"] not in have:
                        idx["images"].append({**im, "from": im.get("from", "ai")})
                idx.setdefault("owner_site", other.get("owner", ""))
                idx.setdefault("links", []).extend(l for l in other.get("links", []) if l not in idx.get("links", []))
        else:
            hp = homepage_of(r, key, apply_rows)
            if not skip and hp and not lh_url and need_site(idx, hp) and sites < a.max_sites:
                note.append("홈페이지 " + str(auto_site(key, hp, idx)) + "장")
                sites += 1
        if add_satellite(r, idx):
            note.append("위성 1")
        n_sheet = add_sheet_files(r, key, idx)
        n_pam = add_pamphlet(key, idx)
        if n_sheet:
            note.append(f"시트 {n_sheet}")
        if n_pam:
            note.append(f"팸플릿 {n_pam}")
        if len(idx["images"]) != before or note:
            save_idx(key, idx)
        ims = idx["images"]
        why = ""
        if not usable(idx):   # ① 조사가 '작업대상'에서 보고 손으로 채우게 (2026-11-11)
            asite = idx.get("auto_site") or {}
            why = ("홈페이지 없음" if not homepage_of(r, key, apply_rows) and not lh_url else
                   asite.get("result", "") if asite else "LH 그림 없음" if lh_url else "아직 안 훑음")[:80]
        amap[r.get("단지명", "")] = {"key": key, "row": r["_row"], "count": len(ims), "usable": usable(idx), "photos": sum(1 for x in ims if x.get("photo")),
                                    "checked": sum(1 for x in ims if x.get("checked")), **({"why": why} if why else {})}
        if note:
            report.append(f"{r['_row']}행 {r.get('단지명', '')[:18]} → {key}: {' · '.join(note)} (총 {len(ims)})")
    MAP.write_text(json.dumps(amap, ensure_ascii=False, indent=1))
    print("\n".join(report) or "새로 받은 것 없음")
    print(json.dumps({"lh": lh, "sites": sites, "keys": len(amap)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
