"""(청약노트 저장소 note/site_assets.py 사본 — 2026-11-02 줍줍알람용으로 복사. 고칠 때는 양쪽 같이.)
분양 홈페이지 자료 수집기: 조감도·단지배치·동호배치·커뮤니티·타입별 평면도·입지 이미지와 E모델하우스 링크.

사용:
  python3 note/site_assets.py --url https://jije.forena.co.kr/ --out posts/P006-.../src/site
  python3 note/site_assets.py --house 2026000123 --out ...      # 청약홈 API의 HMPG_ADRES로 주소 찾기
옵션:
  --engine auto|browser|static   auto: 브라우저(Playwright)가 있으면 브라우저, 없으면 static
  --max-pages 40 --depth 2 --min-side 400

결과 (--out 폴더):
  <분류>/NN_<파일명>   받은 이미지
  manifest.json        이미지별 분류·원본 주소·페이지·alt·크기, 링크(E모델하우스·VR·PDF), 페이지별 주의 문구
  contact.jpg          조감도 후보·사업개요·단지배치·동호·평면·커뮤니티 미리보기(Read로 바로 확인)
  contact_more.jpg     나머지(입지·인테리어·청약안내 등) 미리보기

분류: birdseye(조감도) overview(사업개요·메인 비주얼) site_plan(단지배치·단지설계·조경) dongho(동호배치)
      unit_plan(세대정보·타입별 평면) community(커뮤니티) interior(인테리어·유니트) location(입지)
      modelhouse(견본주택 위치) guide(청약안내 이미지) etc(기타). 이벤트·팝업·페이지 상단 띠 이미지는 받지 않는다.
      birdseye_candidate: 조감도 분류이거나, 사진 같은(색 많고 흰 바탕 적은) 가로 이미지 → 썸네일 후보. 눈으로 확정.

규칙 (docs/원고_기준.md '썸네일·홈페이지 자료'):
- 같은 사이트만, robots.txt를 지키고, 페이지 사이 0.5초 쉰다. 403·406·429 등으로 막히면 그 사이트는 '차단'으로 기록하고
  끝낸다(다른 브라우저인 척하거나 우회하지 않는다).
- '재판매'·'DB 금지' 문구가 있는 페이지의 이미지는 manifest에 use_ok=false로 남긴다. 쓰지 않는다.
- 분류는 페이지 주소·제목·메뉴 글자·alt·파일명 키워드로 하는 추정이다. 글에 넣기 전에 contact.jpg와 원본을 눈으로 확인한다.
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))

CATS = [  # (분류, 키워드) 앞쪽이 우선
    ("skip", ["event", "이벤트", "당첨자 발표", "pop", "popup", "팝업", "유사 홈페이지", "top_img", "하루동안 보지", "오늘 하루", "sub_visual", "subvisual", "sub_top", "sub_bg"]),
    ("dongho", ["동호배치", "동호수", "동·호", "동,호", "dongho", "dong_ho", "dong-ho", "unitplan_dong"]),
    ("community", ["커뮤니티", "community", "부대시설", "피트니스", "fitness", "골프", "golf", "라운지", "lounge", "cmnt"]),
    ("unit_plan", ["평면", "세대정보", "세대안내", "타입", "주택형", "unit", "type", "plan_", "floor"]),
    ("interior", ["인테리어", "interior", "texture", "마감재", "마감", "유니트", "마감재", "옵션", "option", "gallery", "갤러리"]),
    ("birdseye", ["조감", "bird", "aerial", "투시", "perspective"]),
    ("site_plan", ["단지배치", "배치도", "단지설계", "단지안내", "단지계획", "조경", "landscape", "siteplan", "site_plan", "layout", "complex", "danji"]),
    ("overview", ["사업개요", "overview", "planning", "business", "개요", "main_visual", "mainvisual", "main_vis", "kv", "main"]),
    ("guide", ["청약안내", "청약 안내", "특별공급", "일반공급", "청약사항", "check point", "체크포인트", "cy0", "cy_", "gongo", "모집공고"]),
    ("modelhouse", ["견본주택", "모델하우스 위치", "오시는", "contact", "찾아오시는"]),
    ("location", ["입지", "location", "교통", "생활", "광역", "map", "지도", "premium", "프리미엄"]),
]
EMODEL = ["e-모델", "e모델", "사이버", "cyber", "vr", "360", "matterport", "emodel", "e_model", "e-model", "모델하우스", "유니트 영상", "youtube.com", "youtu.be"]
UNIT_RE = re.compile(r"(?<!\d)(39|49|59|69|74|76|84|99|101|102|114|115|135)\s*(㎡|m2|타입|type|[a-d](?![a-z]))", re.I)
SKIP_PAGE = re.compile(r"(/board|/bbs|news_list|notice_list|[?&]page=\d|event|/login|/member|privacy|agree)", re.I)
PAGE_FIRST = {"community", "interior", "dongho"}  # 이 페이지의 이미지는 alt에 '평면'·'84'가 있어도 페이지 분류를 따른다
SKIP_FILE = re.compile(r"(_m\.|_mo\.|_mobile|logo|icon|ico_|btn|button|arrow|close|top\.|go_top|sns|kakao|naver|blank|loading|spinner|bullet|dot|favicon|footer|qr)", re.I)
BAN_TXT = re.compile(r"(재\s*판매|DB\s*금지)")
IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.I)
BLOCK_CODES = {401, 403, 406, 429, 451}


def classify(*groups):
    """강한 신호(파일명·alt)부터 약한 신호(주변 제목·메뉴·페이지)까지 차례로 본다."""
    allb = " ".join(g or "" for g in groups).lower()
    if any(k.lower() in allb for k in CATS[0][1]):  # 팝업·이벤트는 어디에 적혀 있든 뺀다
        return "skip"
    for g in groups:
        blob = (g or "").lower()
        if not blob:
            continue
        for cat, kws in CATS[1:]:
            if any(k.lower() in blob for k in kws):
                return cat
            if cat == "unit_plan" and UNIT_RE.search(blob):
                return cat
    return "etc"


def photo_like(pim):
    """사진(조감도·투시도 후보)인지 대충: 색이 많고 흰 바탕이 적다. 표·안내문·지도는 거의 false."""
    im = pim.convert("RGB").resize((96, 96))
    px = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
    white = sum(1 for r, g, b in px if r > 235 and g > 235 and b > 235) / len(px)
    colors = len(set((r // 8, g // 8, b // 8) for r, g, b in px))
    return white < 0.25 and colors > 450


def house_url(no):
    try:
        from market import load_env, odcloud   # 청약노트 저장소(note/market.py)에서만 있음
    except ImportError:
        sys.exit("줍줍알람 저장소에서는 --house를 못 써요 → '청약홈API' 탭 홈페이지 열·'청약조사' AH열 주소를 --url로")
    env = load_env()
    u = ""
    for ep in ("getAPTLttotPblancDetail", "getRemndrLttotPblancDetail", "getOPTLttotPblancDetail"):  # APT, 무순위·잔여, 임의공급
        try:
            rows = odcloud(env, f"ApplyhomeInfoDetailSvc/v1/{ep}", **{"cond[HOUSE_MANAGE_NO::EQ]": str(no)})
        except Exception:  # noqa: BLE001
            continue
        if rows and (rows[0].get("HMPG_ADRES") or "").strip():
            u = rows[0]["HMPG_ADRES"].strip()
            break
    if not u:
        sys.exit(f"HMPG_ADRES 없음: {no} → 공고문·청약조사 AH열에서 주소를 찾아 --url로")
    return u if u.startswith("http") else "http://" + u


# ---------- 페이지 읽기 ----------
class Static:
    def __init__(self):
        self.s = requests.Session()

    def page(self, url):
        r = self.s.get(url, timeout=20)
        r.encoding = r.apparent_encoding or r.encoding
        if r.status_code >= 400:
            return r.status_code, None
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        imgs = []
        for im in soup.find_all(["img", "source"]):
            for attr in ("src", "data-src", "data-original", "data-lazy", "srcset", "data-srcset"):
                v = im.get(attr)
                if v:
                    for part in v.split(","):
                        u = part.strip().split(" ")[0]
                        if u:
                            imgs.append({"src": urljoin(url, u), "alt": im.get("alt", ""), "ctx": ctx_text(im)})
        css_texts = [st.get_text() for st in soup.find_all("style")] + [t.get("style", "") for t in soup.find_all(style=True)]
        for ln in soup.find_all("link", rel=lambda x: x and "stylesheet" in x):
            try:
                cu = urljoin(url, ln.get("href"))
                cr = self.s.get(cu, timeout=15)
                if cr.ok:
                    css_texts.append(("BASE:" + cu, cr.text))
            except requests.RequestException:
                pass
        for item in css_texts:
            base, txt = (item[0][5:], item[1]) if isinstance(item, tuple) else (url, item)
            for u in re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", txt):
                if IMG_EXT.search(u):
                    imgs.append({"src": urljoin(base, u), "alt": "", "ctx": "css"})
        links = [{"href": urljoin(url, a.get("href", "")), "text": a.get_text(" ", strip=True)} for a in soup.find_all("a")]
        for f in soup.find_all("iframe"):
            links.append({"href": urljoin(url, f.get("src", "")), "text": "iframe " + (f.get("title") or "")})
        for a in soup.find_all(onclick=True):
            for u in re.findall(r"['\"]((?:https?:)?//[^'\"]+|[^'\"]+\.html?)['\"]", a["onclick"]):
                links.append({"href": urljoin(url, u), "text": a.get_text(" ", strip=True)})
        title = soup.title.get_text(strip=True) if soup.title else ""
        return r.status_code, {"title": title, "text": soup.get_text(" ", strip=True), "imgs": imgs, "links": links}

    def close(self):
        pass


def ctx_text(tag):
    """이미지 주변 제목·탭 글자(분류용)."""
    out = []
    p = tag
    for _ in range(4):
        p = p.parent
        if p is None:
            break
        for h in p.find_all(["h1", "h2", "h3", "h4", "strong", "dt", "li"], limit=3):
            t = h.get_text(" ", strip=True)
            if t and len(t) < 40:
                out.append(t)
        if out:
            break
    return " ".join(out)


JS_COLLECT = r"""() => {
  const out = [];
  const near = (el) => { let p = el, t = '';
    for (let i = 0; i < 5 && p && !t; i++) { p = p.parentElement; if (!p) break;
      const h = p.querySelector('h1,h2,h3,h4,strong,.tit,.title,dt'); if (h) t = (h.innerText||'').trim().slice(0,40); }
    return t; };
  document.querySelectorAll('img,source').forEach(el => {
    const s = el.currentSrc || el.src || el.getAttribute('data-src') || el.getAttribute('srcset') || '';
    if (s) out.push({src: s.split(' ')[0], alt: el.alt || '', ctx: near(el)});
    ['data-src','data-original','data-lazy'].forEach(a => { const v = el.getAttribute(a); if (v) out.push({src: v, alt: el.alt||'', ctx: near(el)}); });
  });
  document.querySelectorAll('*').forEach(el => {
    const bg = getComputedStyle(el).backgroundImage;
    if (bg && bg !== 'none') (bg.match(/url\(["']?([^"')]+)["']?\)/g) || []).forEach(m => {
      const u = m.replace(/^url\(["']?/, '').replace(/["']?\)$/, '');
      out.push({src: u, alt: el.getAttribute('aria-label') || '', ctx: (el.className && typeof el.className === 'string' ? el.className + ' ' : '') + near(el)});
    });
  });
  const links = [];
  document.querySelectorAll('a').forEach(a => links.push({href: a.href, text: (a.innerText||a.title||'').trim().slice(0,60), onclick: a.getAttribute('onclick')||''}));
  document.querySelectorAll('iframe').forEach(f => links.push({href: f.src, text: 'iframe ' + (f.title||'')}));
  return {title: document.title, text: document.body ? document.body.innerText : '', imgs: out, links};
}"""


class Browser:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.b = self.pw.chromium.launch()
        self.ctx = self.b.new_context(viewport={"width": 1600, "height": 1000})  # 사용자 에이전트는 바꾸지 않는다

    def page(self, url):
        p = self.ctx.new_page()
        seen = []
        p.on("response", lambda r: seen.append(r.url) if r.request.resource_type == "image" else None)
        try:
            r = p.goto(url, wait_until="networkidle", timeout=40000)
        except Exception:  # noqa: BLE001  — 추적 스크립트 때문에 조용해지지 않는 사이트: 'load'까지만 기다림
            try:
                r = p.goto(url, wait_until="load", timeout=40000)
                p.wait_for_timeout(2500)
            except Exception as e:  # noqa: BLE001
                p.close()
                return 0, {"error": str(e)[:200]}
        code = r.status if r else 0
        if code >= 400:
            p.close()
            return code, None
        try:  # 지연 로딩 이미지를 위해 아래로 훑기
            for y in range(0, 20000, 900):
                p.evaluate(f"window.scrollTo(0,{y})")
                p.wait_for_timeout(120)
            p.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass
        d = p.evaluate(JS_COLLECT)
        for u in seen:
            d["imgs"].append({"src": u, "alt": "", "ctx": "network"})
        for l in d["links"]:
            for u in re.findall(r"['\"]((?:https?:)?//[^'\"]+|[^'\"]+\.html?)['\"]", l.get("onclick", "")):
                d["links"].append({"href": urljoin(url, u), "text": l["text"]})
        p.close()
        return code, d

    def close(self):
        self.b.close()
        self.pw.stop()


# ---------- 수집 ----------
def same_site(u, root):
    a, b = urlparse(u).netloc.lower(), urlparse(root).netloc.lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return strip(a) == strip(b)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url")
    g.add_argument("--house", help="청약홈 주택관리번호")
    ap.add_argument("--out", required=True)
    ap.add_argument("--engine", default="auto", choices=["auto", "browser", "static"])
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--min-side", type=int, default=400)
    a = ap.parse_args()

    root = a.url or house_url(a.house)
    if not root.startswith("http"):
        root = "http://" + root
    pr = urlparse(root)  # 한글 도메인은 퓨니코드로(헤더에 한글을 못 쓴다)
    root = pr._replace(netloc=pr.netloc.encode("idna").decode()).geturl()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    rp = urllib.robotparser.RobotFileParser()
    try:
        rr = requests.get(urljoin(root, "/robots.txt"), timeout=10)
        rp.parse(rr.text.splitlines() if rr.ok else [])
    except requests.RequestException:
        rp.parse([])

    eng = None
    if a.engine in ("auto", "browser"):
        try:
            eng = Browser()
        except Exception as e:  # noqa: BLE001
            if a.engine == "browser":
                sys.exit(f"브라우저 없음: {e}")
    eng = eng or Static()
    print(f"engine={type(eng).__name__} root={root}")

    queue, seen_pages, pages = [(root, 0, "")], set(), []
    images, links, blocked = {}, {}, None
    while queue and len(seen_pages) < a.max_pages:
        url, depth, menu = queue.pop(0)
        url = urldefrag(url)[0]
        if url in seen_pages or not rp.can_fetch("*", url):
            continue
        seen_pages.add(url)
        code, d = eng.page(url)
        time.sleep(0.5)
        if d is None or "error" in (d or {}):
            pages.append({"url": url, "status": code, "error": (d or {}).get("error")})
            if code in BLOCK_CODES:
                blocked = f"{code} {url}"
                print(f"차단됨 {blocked} → 이 사이트는 여기서 멈춰요(우회하지 않음)")
                break
            continue
        if re.search(r"(접근\s*차단|Access\s*Denied|접근이\s*제한|차단된\s*IP)", (d.get("title") or "") + " " + (d.get("text") or "")[:400], re.I):
            blocked = f"{code} 차단 안내 페이지 {url}"   # 200으로 '접근 차단' 화면을 주는 사이트 (2026-11-02 guri.ensvil.com)
            pages.append({"url": url, "status": code, "error": "blocked page"})
            print(f"차단됨 {blocked} → 이 사이트는 여기서 멈춰요(우회하지 않음)")
            break
        ban = bool(BAN_TXT.search(d["text"]))
        pages.append({"url": url, "status": code, "title": d["title"], "menu": menu, "resale_db_ban": ban})
        print(f"[{len(seen_pages):02d}] {code} {url} imgs={len(d['imgs'])} links={len(d['links'])}{' 재판매/DB금지 문구' if ban else ''}")
        for im in d["imgs"]:
            src = urldefrag(urljoin(url, im["src"]))[0]
            if not src.startswith("http") or src in images or re.search(r"(ytimg|youtube|google|kakao|naver|facebook|doubleclick)\.", urlparse(src).netloc) or SKIP_FILE.search(src.rsplit("/", 1)[-1]):
                continue
            images[src] = {"src": src, "page": url, "page_title": d["title"], "menu": menu, "alt": im.get("alt", ""),
                           "ctx": im.get("ctx", ""), "page_ban": ban}
        for l in d["links"]:
            h = urldefrag(l.get("href") or "")[0]
            if not h.startswith("http"):
                continue
            t = re.sub(r"\s+", " ", l.get("text") or "").strip()
            blob = (h + " " + t).lower()
            if any(k in blob for k in EMODEL):
                links.setdefault(h, {"href": h, "text": t, "kind": "emodel", "page": url})
            elif h.lower().split("?")[0].endswith(".pdf"):
                links.setdefault(h, {"href": h, "text": t, "kind": "pdf", "page": url})
            elif same_site(h, root) and depth < a.depth and not SKIP_PAGE.search(h) and re.search(r"\.(html?|php|asp|aspx|jsp|do)$|/[^./]*$", urlparse(h).path or "/"):
                queue.append((h, depth + 1, t[:30]))
    eng.close()

    # 이미지 받기·크기 확인·분류
    s = requests.Session()
    kept, counters = [], {}
    hashes = set()
    for im in images.values():
        try:
            r = s.get(im["src"], timeout=20, headers={"Referer": im["page"].encode("ascii", "ignore").decode()})
        except requests.RequestException:
            continue
        if not r.ok or "image" not in r.headers.get("content-type", "image"):
            continue
        h = hashlib.md5(r.content).hexdigest()
        if h in hashes:
            continue
        try:
            pim = Image.open(io.BytesIO(r.content))
            if pim.mode == "P":
                pim = pim.convert("RGBA")
            w, hgt = pim.size
        except Exception:  # noqa: BLE001
            continue
        if min(w, hgt) < a.min_side * 0.6 or max(w, hgt) < a.min_side:
            continue
        hashes.add(h)
        fname = im["src"].rsplit("/", 1)[-1].split("?")[0]
        page_cat = classify(urlparse(im["page"]).path + " " + im["menu"])
        cat = classify(fname + " " + im["alt"], im["ctx"], im["menu"] + " " + urlparse(im["page"]).path, im["page_title"])
        if page_cat in PAGE_FIRST and cat not in ("skip", "birdseye", "site_plan", "dongho"):
            cat = page_cat
        if cat == "skip":
            continue
        try:
            photo = photo_like(pim)
        except OSError:   # 잘린 파일 (2026-11-02 sujain-pm2)
            continue
        counters[cat] = counters.get(cat, 0) + 1
        dst = out / cat / f"{counters[cat]:02d}_{re.sub(r'[^0-9A-Za-z가-힣._-]', '_', fname)[:60]}"
        dst.parent.mkdir(exist_ok=True)
        dst.write_bytes(r.content)
        kept.append({**im, "category": cat, "file": str(dst.relative_to(out)), "w": w, "h": hgt,
                     "photo": photo, "birdseye_candidate": cat == "birdseye" or (photo and w >= hgt * 1.2 and cat in ("overview", "etc")),
                     "use_ok": not im["page_ban"]})
    order = ["birdseye", "overview", "site_plan", "dongho", "unit_plan", "community", "interior", "location", "modelhouse", "guide", "etc"]
    kept.sort(key=lambda x: (not x["birdseye_candidate"], order.index(x["category"]) if x["category"] in order else 99))

    man = {"root": root, "engine": type(eng).__name__, "collected": time.strftime("%Y-%m-%d %H:%M"),
           "blocked": blocked, "pages": pages, "images": kept, "links": list(links.values()),
           "counts": {c: sum(1 for k in kept if k["category"] == c) for c in order},
           "birdseye_candidates": [k["file"] for k in kept if k["birdseye_candidate"]]}
    (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))
    main_cats = ("birdseye", "overview", "site_plan", "dongho", "unit_plan", "community")
    contact([k for k in kept if k["category"] in main_cats or k["birdseye_candidate"]], out, "contact.jpg")
    contact([k for k in kept if not (k["category"] in main_cats or k["birdseye_candidate"])], out, "contact_more.jpg")
    print("조감도 후보:", man["birdseye_candidates"])
    print("분류별:", {k: v for k, v in man["counts"].items() if v}, "| 링크:", len(links), "| 페이지:", len(pages))
    for l in links.values():
        print(f"  {l['kind']}: {l['text'][:30]} {l['href']}")


def contact(kept, out, name, tw=300):
    if not kept:
        return
    font = ImageFont.load_default()
    for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
              "/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"):
        try:
            font = ImageFont.truetype(f, 14)
            break
        except OSError:
            pass
    cols = 5
    rows = (len(kept) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (tw + 34)), "white")
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(kept):
        try:
            im = Image.open(out / k["file"]).convert("RGB")
        except Exception:  # noqa: BLE001
            continue
        im.thumbnail((tw - 8, tw - 8))
        x, y = (i % cols) * tw, (i // cols) * (tw + 34)
        sheet.paste(im, (x + 4, y + 4))
        d.text((x + 4, y + tw), f"{k['file'][:34]}", fill="black", font=font)
        d.text((x + 4, y + tw + 16), f"{k['w']}x{k['h']}{' 사진·조감도?' if k['birdseye_candidate'] else ''}{'' if k['use_ok'] else ' 사용금지'}", fill="red" if not k["use_ok"] else "gray", font=font)
    sheet.save(out / name, quality=80)


if __name__ == "__main__":
    main()
