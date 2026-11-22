"""투키즈노트 숙소 사이트 (kids.jupjupalarm.com) 빌드.

python3 2kids/site/build.py  →  2kids/site/public/  (Cloudflare Pages 출력 폴더)

입력
- data/sheet/숙소후보.json : 시트 '키즈노트(여행)' › 숙소후보 탭을 내려받은 것 (rows = 머리글 → 값)
- data/stays/T###.json     : 숙소별 정리 (사실 + 캐릭터 판정 문장). 형식은 README.md
출력
- index.html, stay/<slug>/index.html, map/index.html, about/index.html, sitemap.xml, robots.txt, build-report.json
색인 조건을 못 채운 숙소 페이지는 만들되 noindex + 사이트맵 제외.
"""
import datetime as dt
import html
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))
import mapgen  # noqa: E402  (통계청 SGIS 2018 경계, 공공누리 1유형)

SITE = "https://kids.jupjupalarm.com"
GO = "https://autodm.jupjupalarm.com/2kids/go/{n}"
OUT = HERE / "public"
TODAY = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
FRESH_DAYS = 60

PERSONA = {
    "home": ("서울", "강동구"),
    "family": 4,  # 어른 2 + 만 5세 딸 쌍둥이
}
CHECK_LABELS = [("first", "첫째 (공주·노래·춤)"), ("second", "둘째 (자동차·블록·공)"),
                ("pool", "수영장 (둘 다 좋아함)"), ("move", "강동구에서 거리"), ("money", "우리 4인 가족 1박")]

e = html.escape


def won(n):
    return f"{n:,}원"


def man(n):
    """135,000 → '13만원대'"""
    return f"{n // 10000}만원대"


# ---------- 위치·거리 ----------
def place_of(region):
    """'경기 가평군' → ('경기', '가평군'), 해외는 None"""
    parts = region.split()
    if not parts or parts[0] not in mapgen.SIDO_CODE.values():
        return None
    return parts[0], parts[1] if len(parts) > 1 else ""


def centroid(sido, sigungu):
    f = mapgen._find_sgg(sigungu, sido)
    return mapgen._centroid(f["polys"]) if f else None


def km(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    p = math.pi / 180
    h = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


HOME = centroid(*PERSONA["home"])


def move_check(st):
    if st["sido"] == "해외":
        return f"해외({st['region']}) — 비행기 여행이라 2박 이상이 맞아요."
    if st["sido"] == "제주":
        return "제주 — 김포에서 비행기, 2박 이상이 맞아요."
    d = st["km"]
    if d < 70:
        band = "가까워서 금요일 저녁 출발도 괜찮은 거리"
    elif d < 150:
        band = "아이 둘 데리고 1박으로 다녀오기 좋은 거리"
    else:
        band = "멀어서 1박이면 빠듯하고 2박이 편한 거리"
    return f"강동구에서 직선 약 {d:.0f}km — {band}예요."


# ---------- 가격 ----------
def family_total(st):
    """우리 4인 가족(어른 2 + 아이 2) 실제 1박 총액과 계산 줄. 계산 못 하면 (None, 이유)."""
    n = PERSONA["family"]
    room, req = st["room_price"], st.get("required", [])
    mx, base, fee = st.get("max"), st.get("base"), st.get("extra_fee")
    if mx is not None and mx < n:
        if st.get("price4"):
            return st["price4"] + sum(a for _, a in req), [("넷이 묵는 객실", won(st["price4"]))] + [(l, won(a)) for l, a in req]
        return None, f"이 가격 객실은 최대 {mx}인이에요. {st.get('note4', '넷이면 더 큰 객실을 골라야 해요.')}"
    lines = [("객실", won(room))] + [(l, won(a)) for l, a in req]
    total = room + sum(a for _, a in req)
    if base is not None and base < n:
        if st.get("kids_free"):
            lines.append(("아이 추가", st["kids_free"]))
        elif fee:
            extra = (n - base) * fee
            lines.append((f"추가 {n - base}명 × {won(fee)}", won(extra)))
            total += extra
        else:
            return None, f"기준 {base}인이라 넷이면 추가 요금이 붙을 수 있어요. {st.get('note4', '예약 전에 확인해 주세요.')}"
    elif base is None and st.get("note4"):
        return None, st["note4"]
    return total, lines


def money_check(st):
    t, lines = st["total4"], st["total4_lines"]
    if t is None:
        return f"객실 {man(st['room_price'])}부터 — {lines}"
    band = "부담 적은 1박" if t < 150000 else "주말 특별 1박" if t < 250000 else "기념일급 1박"
    return f"넷이서 약 {won(t)} — {band}이에요."


# ---------- 데이터 ----------
def load():
    sheet = json.loads((HERE / "data/sheet/숙소후보.json").read_text())
    rows = {r["숙소ID"]: r for r in sheet["rows"]}
    stays, errors = [], []
    for f in sorted((HERE / "data/stays").glob("T*.json")):
        st = json.loads(f.read_text())
        r = rows.get(st["id"])
        if not r:
            errors.append(f"{st['id']}: 시트에 없음")
            continue
        if r["상태"] != "발행완료":
            continue
        st["name"] = r["숙소명"]
        st["region"] = r["지역"]
        st["type"] = r["유형"]
        st["theme"] = r["테마"]
        st["homepage"] = r["공식 홈페이지"]
        st["price_date"] = r["가격 확인일"]
        st["n"] = int(st["id"][1:])
        st["has_link"] = bool(r["파트너스 링크"].strip())
        p = place_of(st["region"])
        if p:
            st["sido"], st["sigungu"] = p
            c = centroid(*p)
            st["lonlat"] = c
            st["km"] = km(HOME, c) if c else None
        else:
            st["sido"], st["sigungu"], st["lonlat"], st["km"] = "해외", "", None, None
        st["total4"], st["total4_lines"] = family_total(st)
        k = st.get("kids", {})
        st["checks"] = {"first": k.get("first"), "second": k.get("second"), "pool": k.get("pool"),
                        "move": move_check(st), "money": money_check(st)}
        st["index"], st["why_noindex"] = index_ok(st)
        stays.append(st)
    return stays, errors


def index_ok(st):
    why = []
    facts = len(st.get("costs", [])) + len(st.get("info", [])) + len(st.get("rooms", []))
    if facts < 6:
        why.append(f"확인한 사실 {facts}줄 (6줄 이상 필요)")
    filled = sum(1 for v in st["checks"].values() if v)
    if filled < 4:
        why.append(f"캐릭터 판정 {filled}/5칸 (4칸 이상 필요)")
    if len(st.get("faq", [])) < 2:
        why.append("자주 묻는 질문 2개 미만")
    try:
        age = (TODAY - dt.date.fromisoformat(st["price_date"])).days
        if age > FRESH_DAYS:
            why.append(f"가격 확인 {age}일 전 ({FRESH_DAYS}일 이내 필요)")
    except ValueError:
        why.append("가격 확인일 없음")
    if not st["has_link"]:
        why.append("예약 링크 없음")
    return not why, why


# ---------- 경험 표현 검사 (방문 기록이 없으므로) ----------
BANNED = re.compile(r"(가 ?봤|다녀왔|묵어 ?봤|써 ?봤|직접 가|우리 애들이 좋아했|좋아했어요|실사용)")


def lint(st):
    text = json.dumps({k: st.get(k) for k in ("one", "kids", "fit", "faq")}, ensure_ascii=False)
    return [m.group(0) for m in BANNED.finditer(text)]


# ---------- 화면 ----------
CSS = """
:root{--paper:#FBF7EF;--ink:#2B3040;--sub:#5D6273;--line:#E7E0D2;--card:#FFFFFF;--hl:#F5C84C;--sage:#9DBB97;--coral:#E8735F;--chip:#F1ECE1}
@media (prefers-color-scheme:dark){:root{--paper:#1C1E25;--ink:#EEEAE2;--sub:#ABA79F;--line:#34363F;--card:#24262E;--chip:#2E3039}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif;word-break:keep-all}
a{color:inherit}.wrap{max-width:760px;margin:0 auto;padding:0 16px}
.ad{font-size:12px;color:var(--sub);background:var(--chip);padding:6px 16px;text-align:center}
header.top{display:flex;justify-content:space-between;align-items:center;padding:14px 0}
header.top a{text-decoration:none;font-weight:800}header.top nav a{font-weight:600;margin-left:14px;font-size:14px;color:var(--sub)}
.crumb{font-size:13px;color:var(--sub);margin:4px 0 8px}.crumb a{text-decoration:none}
h1{font-size:26px;line-height:1.35;margin:6px 0 8px}h2{font-size:20px;margin:34px 0 10px}
.lead{color:var(--sub);margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:14px 0}
.kv{display:grid;grid-template-columns:7.5em 1fr;gap:6px 12px;margin:0}.kv dt{color:var(--sub)}.kv dd{margin:0}
.big{font-size:22px;font-weight:800}.hl{background:linear-gradient(transparent 60%,var(--hl) 60%)}
.btn{display:block;text-align:center;background:var(--coral);color:#fff;text-decoration:none;font-weight:800;padding:14px;border-radius:12px;margin:14px 0}
.btn small{display:block;font-weight:500;opacity:.9;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--sub);font-weight:600;width:34%}
.checks{list-style:none;padding:0;margin:0}.checks li{display:grid;grid-template-columns:9.5em 1fr;gap:10px;padding:10px 0;border-bottom:1px solid var(--line)}
.checks b{font-size:14px;color:var(--sub)}.checks .no{color:var(--sub)}
.fit{display:grid;grid-template-columns:1fr 1fr;gap:10px}.fit div{border-radius:12px;padding:12px;background:var(--chip)}
.fit b{display:block;font-size:13px;margin-bottom:4px}
@media (max-width:560px){.fit{grid-template-columns:1fr}.checks li{grid-template-columns:1fr;gap:2px}.kv{grid-template-columns:6.5em 1fr}}
details{border-bottom:1px solid var(--line);padding:10px 0}summary{font-weight:700;cursor:pointer}
.note{font-size:13px;color:var(--sub)}
.list{list-style:none;padding:0;margin:0;display:grid;gap:10px}
.list a{display:block;text-decoration:none;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.list .r{font-size:13px;color:var(--sub)}.list .t{font-weight:800;margin:2px 0}.list .p{font-size:14px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.chips a,.chips span{font-size:13px;padding:4px 10px;border-radius:99px;background:var(--chip);text-decoration:none}
.mapbox svg{width:100%;height:auto;border-radius:14px;display:block}
footer{margin:48px 0 32px;font-size:13px;color:var(--sub)}
"""


def page(title, desc, path, body, index=True, jsonld=None):
    robots = "index,follow" if index else "noindex,follow"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<meta name="robots" content="{robots}"><link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="website"><meta property="og:site_name" content="투키즈노트">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{SITE}{path}">
<style>{CSS}</style>{ld}</head><body>
<div class="ad">네이버 여행 커넥트·쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</div>
<div class="wrap"><header class="top"><a href="/">투키즈노트</a><nav><a href="/map/">지도</a><a href="/about/">기준</a></nav></header>
{body}
<footer>투키즈노트 · 쌍둥이 엄마의 아이랑 숙소 노트<br>가격·운영은 날짜·상품에 따라 바뀔 수 있어요. 예약 전 예약 페이지에서 꼭 확인해 주세요.<br>
지역 경계: 통계청 SGIS 2018 행정구역 경계 (공공누리 제1유형)</footer></div></body></html>"""


def book_btn(st, where):
    return (f'<a class="btn" rel="sponsored nofollow" href="{GO.format(n=st["n"])}?src=kids-{where}">'
            f'예약 가능한 객실·실시간 요금 보기<small>쿠팡 트래블로 이동 · 링크 구매 시 수수료를 받아요</small></a>')


def table(rows, head=None):
    if not rows:
        return ""
    return "<table>" + "".join(f"<tr><th>{e(a)}</th><td>{e(b)}</td></tr>" for a, b in rows) + "</table>"


def stay_page(st, all_stays):
    title = f"{st['name']} | {st['one']}"
    if len(title) > 60:
        title = f"{st['name']} | {st['sigungu'] or st['region']} 아이랑 숙소 정리"
    money = st["checks"]["money"]
    desc = f"{st['one']}. {money} 객실 차이·추가 요금·아이 기준 체크를 정리했어요."
    path = f"/stay/{st['slug']}/"
    crumb = f'<div class="crumb"><a href="/">홈</a> › {e(st["sido"])}{" › " + e(st["sigungu"]) if st["sigungu"] else ""}</div>'
    total = ""
    if st["total4"] is not None:
        total = (f'<div class="card"><div class="note">우리 4인 가족(어른 2 + 아이 2) 실제 1박</div>'
                 f'<div class="big"><span class="hl">약 {won(st["total4"])}</span></div>{table(st["total4_lines"])}'
                 f'<div class="note">기준: {e(st["price_basis"])} · {e(st["price_date"])} 확인</div></div>')
    else:
        total = (f'<div class="card"><div class="note">객실 1박</div><div class="big">{man(st["room_price"])}부터</div>'
                 f'<p>{e(st["total4_lines"])}</p><div class="note">기준: {e(st["price_basis"])} · {e(st["price_date"])} 확인</div></div>')
    checks = "".join(
        f'<li><b>{e(lbl)}</b><span{"" if st["checks"][k] else " class=no"}>{e(st["checks"][k] or "해당 시설 안내 없음")}</span></li>'
        for k, lbl in CHECK_LABELS)
    fit = (f'<div class="fit"><div><b>이런 집에 맞아요</b>{e(st["fit"]["good"])}</div>'
           f'<div><b>이런 집은 다시 생각해요</b>{e(st["fit"]["bad"])}</div></div>')
    rooms = f'<h2>객실별 차이</h2>{table(st["rooms"])}' if st.get("rooms") else ""
    costs = f'<h2>따로 드는 비용</h2>{table(st["costs"])}' if st.get("costs") else ""
    info = f'<h2>이용 정보</h2>{table(st["info"])}' if st.get("info") else ""
    faq = ""
    if st.get("faq"):
        faq = "<h2>자주 묻는 질문</h2>" + "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in st["faq"])
    mp = ""
    if st["sido"] not in ("해외",) and st["sigungu"]:
        svg, _ = mapgen.make_map(st["sigungu"], sido=st["sido"], width=920, height=520)
        if svg:
            mp = f'<h2>어디에 있냐면요</h2><div class="mapbox">{svg}</div><p class="note">{e(st["region"])} · 시·군 위치(대략)</p>'
    same = [s for s in all_stays if s is not st and s["index"] and (s["sido"] == st["sido"] or s["theme"] == st["theme"])][:3]
    rel = ""
    if same:
        rel = "<h2>비슷한 숙소</h2>" + stay_list(same)
    body = f"""{crumb}<h1>{e(st['name'])}</h1><p class="lead">{e(st['one'])}</p>
{total}{book_btn(st, 'top')}
<h2>우리 쌍둥이 기준 체크</h2><p class="note">만 5세 딸 쌍둥이(첫째는 공주·노래·춤, 둘째는 자동차·블록·공, 둘 다 수영장)와 강동구에서 출발하는 4인 가족 기준이에요.</p>
<ul class="checks">{checks}</ul>
<h2>한 줄 판단</h2>{fit}
{rooms}{costs}{info}{faq}{mp}
{book_btn(st, 'bottom')}
<p class="note">직접 다녀온 후기가 아니라 공식 홈페이지·예약 페이지 안내를 모아 정리했어요. 정리 {e(st['checked'])} · 가격 {e(st['price_date'])} 확인.
{f'공식 홈페이지: <a href="{e(st["homepage"])}" rel="nofollow">{e(st["homepage"])}</a>' if st.get('homepage') else ''}</p>
{rel}"""
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "투키즈노트", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": st["name"], "item": SITE + path}]},
        {"@context": "https://schema.org", "@type": "Article", "headline": title[:110], "dateModified": st["checked"],
         "author": {"@type": "Organization", "name": "투키즈노트"},
         "about": {"@type": "LodgingBusiness", "name": st["name"],
                   "address": {"@type": "PostalAddress", "addressRegion": st["sido"], "addressLocality": st["sigungu"],
                               "addressCountry": "JP" if st["sido"] == "해외" and "일본" in st["region"] else "KR"}}}]
    return path, page(title, desc, path, body, st["index"], ld)


def stay_list(stays):
    out = []
    for s in stays:
        price = f"넷이서 약 {man(s['total4'])}" if s["total4"] is not None else f"객실 {man(s['room_price'])}부터"
        out.append(f'<li><a href="/stay/{s["slug"]}/"><div class="r">{e(s["region"])}</div><div class="t">{e(s["name"])}</div>'
                   f'<div class="p">{e(s["one"])} · {price}</div></a></li>')
    return f'<ul class="list">{"".join(out)}</ul>'


def national_map(stays, width=700, height=900):
    provs = mapgen._load("skorea-provinces-2018-topo-simple.json")
    x0, y0, x1, y1 = 124.6, 33.0, 130.0, 38.7
    k = math.cos(math.radians(36))

    def P(lon, lat):
        sx = width / ((x1 - x0) * k)
        sy = height / (y1 - y0)
        s = min(sx, sy)
        return ((lon - x0) * k * s, (y1 - lat) * s)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="투키즈노트 숙소 지도">',
             f'<rect width="{width}" height="{height}" fill="#EEF3F6"/>']
    for f in provs:
        d = "".join("M" + "L".join(f"{P(*p)[0]:.1f},{P(*p)[1]:.1f}" for p in r) + "Z" for poly in f["polys"] for r in poly)
        parts.append(f'<path d="{d}" fill="#FFFFFF" stroke="#C9D2DA" stroke-width="1.2"/>')
    hx, hy = P(*HOME)
    parts.append(f'<g><circle cx="{hx:.0f}" cy="{hy:.0f}" r="9" fill="#2B3040"/>'
                 f'<text x="{hx + 12:.0f}" y="{hy - 10:.0f}" font-size="18" font-weight="800" fill="#2B3040">우리 집(강동구)</text></g>')
    for s in stays:
        if not s.get("lonlat"):
            continue
        x, y = P(*s["lonlat"])
        parts.append(f'<a href="/stay/{s["slug"]}/"><title>{e(s["name"])} ({e(s["region"])})</title>'
                     f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" fill="#E8735F" stroke="#fff" stroke-width="3"/></a>')
    parts.append("</svg>")
    return "".join(parts)


def main():
    stays, errors = load()
    warns = []
    for st in stays:
        bad = lint(st)
        if bad:
            errors.append(f"{st['id']}: 방문·체험 표현 금지 {bad}")
    slugs = [s["slug"] for s in stays]
    if len(set(slugs)) != len(slugs):
        errors.append("slug 중복")
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=1))
        sys.exit(1)

    if OUT.exists():
        for p in sorted(OUT.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
    OUT.mkdir(parents=True, exist_ok=True)

    def write(path, text):
        f = OUT / path.strip("/") / "index.html" if path.endswith("/") else OUT / path.strip("/")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    stays.sort(key=lambda s: (s["km"] is None, s["km"] or 0))
    indexed = [s for s in stays if s["index"]]
    for st in stays:
        path, html_ = stay_page(st, stays)
        write(path, html_)

    # 홈
    groups = {}
    for s in indexed:
        groups.setdefault(s["sido"], []).append(s)
    near = [s for s in indexed if s["km"] is not None and s["km"] < 150]
    cheap = sorted([s for s in indexed if s["total4"] is not None], key=lambda s: s["total4"])[:5]
    pool = [s for s in indexed if s["checks"]["pool"] and "없" not in s["checks"]["pool"] and "대신" not in s["checks"]["pool"]]
    sections = [("강동구에서 1박으로 다녀오기 좋은 곳", "직선 150km 안쪽", near),
                ("넷이서 실제 1박 총액이 낮은 순", "추가 요금·필수 현장결제까지 더한 값", cheap),
                ("겨울에도 아이 둘이 물에 들어갈 수 있는 곳", "실내·온수풀·온천", pool)]
    body = ['<h1>쌍둥이 엄마가 찜해 둔 아이랑 숙소</h1>'
            '<p class="lead">만 5세 딸 쌍둥이와 강동구에서 출발하는 4인 가족 기준으로, 객실 차이·따로 드는 비용·실제 1박 총액을 정리해요.</p>',
            f'<div class="mapbox">{national_map(indexed)}</div><p class="note"><a href="/map/">지도 크게 보기</a> · 점을 누르면 숙소로 가요.</p>']
    for h, sub, lst in sections:
        if lst:
            body.append(f'<h2>{e(h)}</h2><p class="note">{e(sub)}</p>{stay_list(lst[:4])}')
    order = sorted(groups.items(), key=lambda kv: (kv[0] == "해외", -len(kv[1])))
    body.append('<h2>지역별 전체</h2>' + "".join(
        f'<p><b>{e(k)}</b> · ' + " · ".join(f'<a href="/stay/{x["slug"]}/">{e(x["name"])}</a>' for x in v) + '</p>' for k, v in order))
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "투키즈노트", "url": SITE + "/"}]
    write("/", page("투키즈노트 | 쌍둥이 엄마가 정리한 아이랑 숙소", "만 5세 쌍둥이 4인 가족 기준으로 정리한 아이랑 숙소. 실제 1박 총액·객실 차이·따로 드는 비용.",
                    "/", "".join(body), True, ld))

    # 지도
    write("/map/", page("아이랑 숙소 지도 | 투키즈노트", "투키즈노트가 정리한 아이랑 숙소를 지도에서 한눈에.", "/map/",
                        f'<h1>아이랑 숙소 지도</h1><p class="lead">강동구 우리 집에서 얼마나 먼지 한눈에 보여요. 위치는 시·군 단위(대략)예요.</p>'
                        f'<div class="mapbox">{national_map(indexed)}</div><h2>목록</h2>{stay_list(indexed)}'
                        + (f'<h2>해외</h2>{stay_list([s for s in indexed if s["sido"] == "해외"])}' if any(s["sido"] == "해외" for s in indexed) else "")))

    # 기준
    write("/about/", page("투키즈노트가 숙소를 고르고 정리하는 기준", "누가 어떤 기준으로 숙소를 고르고 가격을 확인하는지.", "/about/",
                          """<h1>숙소를 고르고 정리하는 기준</h1>
<p>투키즈노트는 만 5세 딸 쌍둥이를 키우는 엄마의 눈으로 아이랑 갈 숙소를 고르는 노트예요. 서울 강동구에서 출발하는 평범한 4인 가족 기준으로 봐요.</p>
<h2>우리 집 기준</h2><ul>
<li>첫째는 공주 스타일에 노래·춤을 좋아하고, 둘째는 자동차·블록·공놀이를 좋아해요. 둘 다 수영장을 좋아해요.</li>
<li>가격은 객실값만이 아니라 필수 현장결제·추가 인원 요금까지 더한 '넷이서 실제 1박'으로 봐요.</li>
<li>거리는 강동구에서의 직선거리로 1박이 편한지 따져요.</li></ul>
<h2>정보는 어디서 오나요</h2>
<p>공식 홈페이지와 예약 페이지(쿠팡 트래블) 안내를 모아 정리해요. 페이지마다 가격 확인일을 적고, 오래된 정보는 검색에 내보내지 않아요. 직접 다녀온 후기가 아니고, 다녀온 곳은 따로 표시할 예정이에요.</p>
<h2>수익</h2><p>예약 버튼은 제휴 링크예요. 이 링크로 예약하면 투키즈노트가 수수료를 받지만, 가격은 똑같아요. 수수료 때문에 단점을 빼지 않아요.</p>"""))

    # robots · sitemap
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    urls = [("/", TODAY.isoformat()), ("/map/", TODAY.isoformat()), ("/about/", TODAY.isoformat())] + \
           [(f"/stay/{s['slug']}/", s["price_date"]) for s in indexed]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{SITE}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n")
    (OUT / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n")
    report = {"built": TODAY.isoformat(), "stays": len(stays), "indexed": len(indexed),
              "noindex": {s["id"]: s["why_noindex"] for s in stays if not s["index"]}, "warnings": warns}
    (HERE / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
