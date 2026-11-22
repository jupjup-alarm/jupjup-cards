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



# ---------- 사진·영상 (media.py가 만든 것) ----------
MEDIA = HERE / "media"
ICONS = HERE / "icons"
FONTS = REPO / "fonts"


def load_media(st):
    f = MEDIA / st["slug"] / "media.json"
    if not f.exists():
        return {"photos": [], "reel": None}
    m = json.loads(f.read_text())
    order = st.get("photo_order")
    if order:
        ph = {i + 1: p for i, p in enumerate(m["photos"])}
        m["photos"] = [ph[i] for i in order if i in ph] + [p for i, p in ph.items() if i not in order]
    return m


def murl(st, name):
    return f"/media/{st['slug']}/{name}"


_icon_cache = {}


def icon(name, cls="i"):
    if name not in _icon_cache:
        svg = (ICONS / f"{name}.svg").read_text().strip()
        _icon_cache[name] = re.sub(r"^<svg ", '<svg aria-hidden="true" focusable="false" ', svg)
    return _icon_cache[name].replace("<svg ", f'<svg class="{cls}" ', 1)


# ---------- 테마(카테고리) ----------
def has(text, *words):
    return bool(text) and any(w in text for w in words)


CATS = [  # (key, 이름, 아이콘)
    ("all", "전체", "squares-four"),
    ("water", "물놀이", "swimming-pool"),
    ("kids", "키즈룸·놀이", "puzzle-piece"),
    ("onsen", "온천", "bathtub"),
    ("snow", "눈·스키", "snowflake"),
    ("villa", "풀빌라", "house-line"),
    ("hotel", "호캉스", "buildings"),
    ("near", "가까운 1박", "path"),
    ("cheap", "넷이서 15만원 안쪽", "piggy-bank"),
    ("jeju", "제주", "island"),
    ("abroad", "해외", "airplane-tilt"),
]


def tags_of(st):
    pool = st["kids"].get("pool") or ""
    theme = st["theme"] + " " + st["type"]
    t = set()
    if pool and not has(pool, "여름", "없어요", "대신", "9월 말까지", "만 16세"):
        t.add("water")
    if has(theme + st["name"], "키즈") or has(st["kids"].get("second") or "", "정글짐", "놀이터", "키즈", "볼풀", "블록"):
        t.add("kids")
    if has(theme + st["name"], "온천", "히노끼", "료칸"):
        t.add("onsen")
    if has(theme, "스키", "눈", "썰매", "설경"):
        t.add("snow")
    if "풀빌라" in st["type"]:
        t.add("villa")
    if "호텔" in st["type"]:
        t.add("hotel")
    if st["km"] is not None and st["km"] < 150:
        t.add("near")
    if st["total4"] is not None and st["total4"] < 150000:
        t.add("cheap")
    if st["sido"] == "제주":
        t.add("jeju")
    if st["sido"] == "해외":
        t.add("abroad")
    return t


def place_label(st):
    if st["sido"] == "해외":
        return st["region"]
    return f"{st['sigungu']}, {st['sido']}" if st["sigungu"] else st["sido"]


def dist_label(st):
    if st["sido"] == "해외":
        return "비행기 여행 · 2박 이상"
    if st["sido"] == "제주":
        return "김포에서 비행기 · 2박 이상"
    return f"강동구에서 약 {st['km']:.0f}km"


def price_html(st, short=False):
    if st["total4"] is not None:
        return f'<b>{won(st["total4"])}</b> <span>넷이서 1박</span>'
    return f'<b>{won(st["room_price"])}</b> <span>객실 1박부터</span>'


# ---------- 화면 ----------
CSS = """
:root{--bg:#FFFFFF;--soft:#F7F6F3;--ink:#222222;--sub:#6A6A6A;--line:#EBEBEB;--acc:#D4512F;--acc-ink:#FFFFFF;--shadow:0 6px 20px rgba(60,40,20,.10);
--ease:cubic-bezier(.22,1,.36,1);--r:12px;--wrap:1280px}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#181818;--soft:#1F1F1F;--ink:#F2F2F2;--sub:#A3A3A3;--line:#313131;--shadow:0 6px 20px rgba(0,0,0,.4)}}
:root[data-theme=dark]{--bg:#181818;--soft:#1F1F1F;--ink:#F2F2F2;--sub:#A3A3A3;--line:#313131;--shadow:0 6px 20px rgba(0,0,0,.4)}
@font-face{font-family:P;font-weight:500;font-display:swap;src:url(/fonts/p500.woff2) format("woff2")}
@font-face{font-family:P;font-weight:600;font-display:swap;src:url(/fonts/p600.woff2) format("woff2")}
@font-face{font-family:P;font-weight:700;font-display:swap;src:url(/fonts/p700.woff2) format("woff2")}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:500 16px/24px P,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;word-break:keep-all;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}img,video{display:block;max-width:100%}
button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px;border-radius:8px}
.skip{position:absolute;left:-999px;top:8px;background:var(--ink);color:var(--bg);padding:8px 12px;border-radius:8px;z-index:30}.skip:focus{left:16px}
.wrap{max-width:var(--wrap);margin:0 auto;padding:0 24px}
@media (max-width:743px){.wrap{padding:0 16px}}
.i{width:24px;height:24px;flex:none}
.ad{font-size:12px;line-height:16px;color:var(--sub);text-align:center;padding:8px 16px;border-bottom:1px solid var(--line)}
/* 머리 */
.hd{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:saturate(1.6) blur(12px);-webkit-backdrop-filter:saturate(1.6) blur(12px);border-bottom:1px solid var(--line)}
.hd .row{display:flex;align-items:center;gap:16px;height:72px}
.logo{display:flex;align-items:center;gap:8px;font-weight:700;font-size:18px;letter-spacing:-.02em;color:var(--acc);white-space:nowrap}
.logo svg{width:32px;height:32px}
.search{flex:1;max-width:420px;margin:0 auto;display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:999px;padding:8px 8px 8px 16px;box-shadow:0 1px 2px rgba(0,0,0,.08),0 4px 12px rgba(0,0,0,.05);background:var(--bg)}
.search input{flex:1;min-width:0;border:0;outline:0;background:none;font:600 14px/20px P,sans-serif;color:var(--ink)}
.search input::placeholder{color:var(--sub);font-weight:500}
.search .go{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:var(--acc);color:#fff}.search .go .i{width:16px;height:16px}
.hd nav{display:flex;gap:4px}.hd nav a{font-size:14px;line-height:20px;font-weight:600;padding:8px 12px;border-radius:999px;transition:background .3s var(--ease)}
.hd nav a:hover{background:var(--soft)}
@media (max-width:743px){.hd .row{height:auto;flex-wrap:wrap;padding:12px 0;gap:12px}.search{order:3;flex-basis:100%;max-width:none}.hd nav a.hide-m{display:none}}
/* 카테고리 */
.cats{display:flex;gap:32px;overflow-x:auto;scrollbar-width:none;padding:12px 0 0}.cats::-webkit-scrollbar{display:none}
.cat{display:flex;flex-direction:column;align-items:center;gap:8px;padding:4px 0 12px;font-size:12px;line-height:16px;font-weight:600;color:var(--sub);white-space:nowrap;border-bottom:2px solid transparent;opacity:.78;transition:opacity .3s var(--ease),border-color .3s var(--ease),color .3s var(--ease)}
.cat:hover{opacity:1;border-color:var(--line);color:var(--ink)}
.cat[aria-pressed=true]{opacity:1;color:var(--ink);border-color:var(--ink)}
@media (max-width:743px){.cats{gap:24px}}
/* 영역 */
main{padding-bottom:96px}
.sec{margin-top:48px}.sec-h{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:16px}
h1,h2,h3{text-wrap:balance;margin:0}
.sec h2{font-size:24px;line-height:32px;font-weight:700;letter-spacing:-.02em}
.sec .sub{font-size:14px;line-height:20px;color:var(--sub);margin-top:4px}
.arrows{display:flex;gap:8px}.arrows button{width:32px;height:32px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;background:var(--bg);transition:transform .3s var(--ease),box-shadow .3s var(--ease)}
.arrows button:hover{box-shadow:var(--shadow)}.arrows button:active{transform:scale(.96)}.arrows .i{width:16px;height:16px}
@media (max-width:743px){.arrows{display:none}}
/* 가로 레일 */
.rail{display:grid;grid-auto-flow:column;grid-auto-columns:calc((100% - 72px)/4);gap:24px;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;padding-bottom:4px}
.rail::-webkit-scrollbar{display:none}.rail>*{scroll-snap-align:start}
.rail.reels{grid-auto-columns:calc((100% - 96px)/5)}
@media (max-width:1127px){.rail{grid-auto-columns:calc((100% - 48px)/3)}.rail.reels{grid-auto-columns:calc((100% - 48px)/3.4)}}
@media (max-width:743px){.rail{grid-auto-columns:72%;gap:16px;margin:0 -16px;padding:0 16px;scroll-padding:0 16px}.rail.reels{grid-auto-columns:44%}}
/* 카드 */
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:40px 24px}
@media (max-width:1127px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:743px){.grid{grid-template-columns:minmax(0,1fr);gap:32px}}
@media (min-width:560px) and (max-width:743px){.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:32px 16px}}
.card{position:relative;display:block;min-width:0}
.ph{position:relative;aspect-ratio:1/1;border-radius:var(--r);overflow:hidden;background:var(--soft)}
.ph .strip{display:flex;height:100%;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none}.ph .strip::-webkit-scrollbar{display:none}
.ph img{flex:none;width:100%;height:100%;object-fit:cover;scroll-snap-align:center;transition:transform .5s var(--ease)}
.card:hover .ph img{transform:scale(1.03)}
.dots{position:absolute;left:0;right:0;bottom:8px;display:flex;justify-content:center;gap:4px;pointer-events:none}
.dots i{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.6)}.dots i.on{background:#fff}
.badge{position:absolute;left:12px;top:12px;display:flex;align-items:center;gap:4px;background:rgba(255,255,255,.94);color:#222;font-size:12px;line-height:16px;font-weight:700;padding:4px 8px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.12)}
.badge .i{width:14px;height:14px}
.meta{margin-top:12px;font-size:15px;line-height:20px}
.meta .t{display:flex;justify-content:space-between;gap:8px;font-weight:700}
.meta .t span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.meta .t .reel{flex:none;display:flex;align-items:center;gap:2px;font-weight:600;font-size:13px;color:var(--sub)}.meta .t .reel .i{width:14px;height:14px}
.meta .l{color:var(--sub);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.meta .p{margin-top:4px;font-variant-numeric:tabular-nums}.meta .p b{font-weight:700}.meta .p span{color:var(--sub)}
/* 릴스 카드 */
.rc{position:relative;display:block;aspect-ratio:9/16;border-radius:var(--r);overflow:hidden;background:#111}
.rc img,.rc video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.rc video{opacity:0;transition:opacity .3s var(--ease)}.rc video.on{opacity:1}
.rc .cap{position:absolute;left:0;right:0;bottom:0;padding:40px 12px 12px;background:linear-gradient(transparent,rgba(0,0,0,.72));color:#fff}
.rc .cap b{display:block;font-size:14px;line-height:20px}.rc .cap span{font-size:12px;line-height:16px;opacity:.9}
.rc .play{position:absolute;right:8px;top:8px;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;background:rgba(0,0,0,.45);color:#fff}.rc .play .i{width:16px;height:16px}
/* 홈 머리 */
.intro{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:end;margin-top:32px}
.intro h1{font-size:36px;line-height:40px;font-weight:700;letter-spacing:-.03em;max-width:680px}
.intro p{margin:12px 0 0;color:var(--sub);max-width:600px;text-wrap:pretty}
.facts{display:flex;gap:8px;flex-wrap:wrap}.facts span{display:flex;align-items:center;gap:8px;font-size:13px;line-height:16px;font-weight:600;background:var(--soft);padding:8px 12px;border-radius:999px}
.facts .i{width:16px;height:16px;color:var(--acc)}
@media (max-width:743px){.intro{grid-template-columns:1fr;margin-top:24px}.intro h1{font-size:30px;line-height:36px}}
.empty{padding:48px 0;color:var(--sub);text-align:center}
.count{font-size:14px;color:var(--sub)}
/* 숙소 페이지 */
.crumb{font-size:14px;line-height:20px;color:var(--sub);margin-top:24px}.crumb a:hover{text-decoration:underline}
.st-h{margin-top:8px}.st-h h1{font-size:30px;line-height:36px;font-weight:700;letter-spacing:-.02em}
.st-h .sub{display:flex;flex-wrap:wrap;gap:4px 12px;margin-top:8px;font-size:14px;line-height:20px;color:var(--sub)}
.st-h .sub b{color:var(--ink);font-weight:600}
.gal{position:relative;display:grid;grid-template-columns:2fr 1fr 1fr;grid-template-rows:1fr 1fr;gap:8px;height:min(56vw,480px);margin-top:24px;border-radius:var(--r);overflow:hidden}
.gal a{position:relative;overflow:hidden;background:var(--soft)}.gal a:first-child{grid-row:span 2}
.gal img{width:100%;height:100%;object-fit:cover;transition:filter .3s var(--ease)}
.gal>.gv{grid-row:span 2}
.gv{position:relative;overflow:hidden;background:#111}
.gv .bg{position:absolute;inset:-24px;width:calc(100% + 48px);height:calc(100% + 48px);max-width:none;object-fit:cover;filter:blur(24px) brightness(.55);transform:scale(1.05)}
.gv video{position:relative;width:100%;height:100%;object-fit:contain;cursor:pointer}
.gv .tag{position:absolute;left:12px;top:12px;display:flex;align-items:center;gap:4px;background:rgba(0,0,0,.55);color:#fff;font-size:12px;line-height:16px;font-weight:600;padding:4px 8px;border-radius:6px}
.gv .tag .i{width:14px;height:14px}
.snd{position:absolute;right:12px;bottom:12px;width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:rgba(0,0,0,.55);color:#fff;transition:transform .3s var(--ease)}
.snd:active{transform:scale(.96)}.snd .i{width:20px;height:20px}.snd .on{display:none}.snd[aria-pressed=true] .on{display:block}.snd[aria-pressed=true] .off{display:none}.gal a:hover img{filter:brightness(.9)}
.gal.n1{grid-template-columns:1fr}.gal.n1 a:first-child{grid-row:span 2}
.gal.n2,.gal.n3{grid-template-columns:2fr 1fr}
.gal.n4{grid-template-columns:2fr 1fr 1fr}.gal.n4 a:nth-child(4){grid-column:span 2}
.gal .all{position:absolute;right:16px;bottom:16px;display:flex;align-items:center;gap:8px;background:var(--bg);color:var(--ink);border:1px solid var(--ink);font-size:14px;line-height:20px;font-weight:600;padding:8px 12px;border-radius:8px;transition:transform .3s var(--ease)}
.gal .all:active{transform:scale(.98)}.gal .all .i{width:16px;height:16px}
.mgal{display:none}
@media (max-width:743px){.gal{display:none}
.mgal{display:block;position:relative;margin:16px -16px 0}.mgal .strip{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none}.mgal .strip::-webkit-scrollbar{display:none}
.mgal img{flex:none;width:100%;aspect-ratio:4/5;object-fit:cover;scroll-snap-align:center}.mgal .gv{flex:none;width:100%;aspect-ratio:4/5;scroll-snap-align:center}.mgal .gv .bg{aspect-ratio:auto}
.mgal .n{position:absolute;right:12px;top:12px;background:rgba(0,0,0,.6);color:#fff;font-size:12px;line-height:16px;font-weight:600;padding:4px 8px;border-radius:6px}}
.credit{font-size:12px;line-height:16px;color:var(--sub);margin-top:8px}
.lay{display:grid;grid-template-columns:minmax(0,1fr) 372px;gap:80px;margin-top:32px}
@media (max-width:1127px){.lay{grid-template-columns:minmax(0,1fr) 320px;gap:48px}}
@media (max-width:743px){.lay{grid-template-columns:1fr;gap:0;margin-top:24px}}
.blk{padding:32px 0;border-bottom:1px solid var(--line)}.blk:first-child{padding-top:0}
.blk h2{font-size:22px;line-height:28px;font-weight:700;letter-spacing:-.02em;margin-bottom:16px}
.blk .lead{color:var(--sub);font-size:14px;line-height:20px;margin:-8px 0 16px}
.one{font-size:18px;line-height:28px;font-weight:600;text-wrap:pretty}
.feats{display:grid;gap:24px}.feat{display:grid;grid-template-columns:24px 1fr;gap:16px}
.feat b{display:block;font-weight:700}.feat p{margin:2px 0 0;color:var(--sub);text-wrap:pretty}.feat.no p{font-style:normal}
.fit{display:grid;grid-template-columns:1fr 1fr;gap:12px}.fit div{background:var(--soft);border-radius:var(--r);padding:16px}
.fit b{display:flex;align-items:center;gap:8px;font-size:14px;line-height:20px;margin-bottom:4px}.fit .i{width:18px;height:18px}
.fit .ok .i{color:#2F7D4F}.fit .ng .i{color:var(--acc)}
@media (max-width:743px){.fit{grid-template-columns:1fr}}
dl.kv{display:grid;grid-template-columns:minmax(96px,30%) 1fr;gap:12px 24px;margin:0}dl.kv dt{color:var(--sub)}dl.kv dd{margin:0;white-space:pre-line}
.reelnote q{display:block;font-size:18px;line-height:28px;font-weight:700;quotes:none;text-wrap:balance}
.reelnote .when{color:var(--sub);font-size:14px;line-height:20px;margin-top:8px}
.links{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.links a{display:flex;align-items:center;gap:8px;font-size:14px;line-height:20px;font-weight:600;padding:8px 12px;border:1px solid var(--line);border-radius:8px;transition:background .3s var(--ease)}
.links a:hover{background:var(--soft)}.links .i{width:18px;height:18px}
.faq{display:grid;grid-template-columns:1fr 1fr;gap:24px 32px}.faq h3{font-size:16px;line-height:24px;font-weight:700}.faq p{margin:4px 0 0;color:var(--sub);text-wrap:pretty}
@media (max-width:743px){.faq{grid-template-columns:1fr}}
.src{font-size:13px;line-height:20px;color:var(--sub)}.src a{text-decoration:underline}
/* 예약 카드 */
.book{position:sticky;top:104px;border:1px solid var(--line);border-radius:var(--r);padding:24px;box-shadow:var(--shadow);background:var(--bg)}
.book .big{font-size:22px;line-height:28px;font-weight:700;font-variant-numeric:tabular-nums}.book .big span{font-size:16px;font-weight:500;color:var(--sub)}
.book dl{display:grid;grid-template-columns:1fr auto;gap:8px 16px;margin:16px 0 0;font-size:14px;line-height:20px;font-variant-numeric:tabular-nums}
.book dt{color:var(--sub)}.book dd{margin:0;text-align:right}
.book .sum{border-top:1px solid var(--line);padding-top:12px;font-weight:700}.book .sum dt{color:var(--ink)}
.book .note{font-size:12px;line-height:16px;color:var(--sub);margin-top:12px}
.btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;background:var(--acc);color:var(--acc-ink);font-size:16px;line-height:24px;font-weight:600;padding:12px;border-radius:8px;margin-top:16px;transition:filter .3s var(--ease),transform .3s var(--ease)}
.btn:hover{filter:brightness(1.06)}.btn:active{transform:scale(.98)}.btn .i{width:18px;height:18px}
.why{font-size:14px;line-height:20px;color:var(--sub);margin:8px 0 0}
.mbar{display:none}
@media (max-width:743px){.book-col{display:none}
.mbar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:20;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px calc(12px + env(safe-area-inset-bottom));background:var(--bg);border-top:1px solid var(--line)}
.mbar b{display:block;font-size:16px;line-height:20px;font-variant-numeric:tabular-nums}.mbar span{font-size:12px;line-height:16px;color:var(--sub)}
.mbar .btn{width:auto;margin:0;padding:12px 20px;flex:none}}
.mtotal{display:none}@media (max-width:743px){.mtotal{display:block}}
/* 바닥 */
footer{border-top:1px solid var(--line);background:var(--soft);padding:32px 0 48px;font-size:14px;line-height:20px;color:var(--sub)}
footer .row{display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px}footer a{font-weight:600;color:var(--ink)}footer a:hover{text-decoration:underline}
footer nav{display:flex;gap:16px}
.prose{max-width:680px;margin-top:32px}.prose h1{font-size:30px;line-height:36px;font-weight:700;letter-spacing:-.02em}
.prose h2{font-size:20px;line-height:28px;margin:32px 0 8px}.prose p,.prose li{color:var(--ink);text-wrap:pretty}.prose ul{padding-left:20px}
/* 등장 */
.rv-in{opacity:0;transform:translateY(16px);transition:opacity .7s var(--ease),transform .7s var(--ease)}.rv-in.on{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}.rv-in{transform:none;transition:opacity .3s linear}.ph img,.card:hover .ph img{transition:none;transform:none}}
[hidden]{display:none!important}
"""

LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="11" cy="13" r="6" fill="currentColor"/>'
        '<circle cx="21" cy="13" r="6" fill="currentColor" opacity=".55"/>'
        '<path d="M5 26c1.5-3.5 4-5 6-5s4.5 1.5 5 3c.5-1.5 3-3 5-3s4.5 1.5 6 5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>')
FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#D4512F"/>'
           '<circle cx="12" cy="14" r="5" fill="#fff"/><circle cx="20" cy="14" r="5" fill="#fff" opacity=".7"/>'
           '<path d="M7 25c1.3-2.8 3.3-4 5-4s3.6 1.1 4 2.4c.4-1.3 2.3-2.4 4-2.4s3.7 1.2 5 4" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>')

JS = r"""
(()=>{const rm=matchMedia('(prefers-reduced-motion: reduce)').matches;
// 카드 사진 점
document.querySelectorAll('.ph .strip').forEach(s=>{const d=s.parentElement.querySelectorAll('.dots i');if(!d.length)return;
 s.addEventListener('scroll',()=>{const k=Math.round(s.scrollLeft/s.clientWidth);d.forEach((x,j)=>x.classList.toggle('on',j===k))},{passive:true})});
document.querySelectorAll('.mgal .strip').forEach(s=>{const n=s.parentElement.querySelector('.n'),t=s.children.length;
 s.addEventListener('scroll',()=>{n.textContent=(Math.round(s.scrollLeft/s.clientWidth)+1)+' / '+t},{passive:true})});
// 레일 화살표
document.querySelectorAll('[data-rail]').forEach(b=>b.addEventListener('click',()=>{const r=document.getElementById(b.dataset.rail);
 r.scrollBy({left:(b.dataset.dir==='1'?1:-1)*r.clientWidth*.9,behavior:rm?'auto':'smooth'})}));
// 보이는 릴스만 재생
const vids=[...document.querySelectorAll('video[data-auto]')];
if(vids.length&&'IntersectionObserver' in window&&!rm){const io=new IntersectionObserver(es=>es.forEach(e=>{const v=e.target;
 if(e.isIntersecting&&e.intersectionRatio>.6){if(!v.src&&v.dataset.src){v.src=v.dataset.src}v.play().then(()=>v.classList.add('on')).catch(()=>{})}else{v.pause()}}),{threshold:[0,.6]});vids.forEach(v=>io.observe(v))}
document.querySelectorAll('.gv video').forEach(v=>v.addEventListener('click',()=>{if(!v.src)v.src=v.dataset.src;v.paused?v.play():v.pause()}));
document.querySelectorAll('.snd').forEach(b=>b.addEventListener('click',()=>{const v=b.parentElement.querySelector('video');if(!v.src)v.src=v.dataset.src;v.muted=!v.muted;
 b.setAttribute('aria-pressed',String(!v.muted));b.setAttribute('aria-label',v.muted?'소리 켜기':'소리 끄기');if(v.paused)v.play()}));
// 등장
const rv=document.querySelectorAll('.rv-in');if('IntersectionObserver' in window){const o=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('on');o.unobserve(e.target)}}),{rootMargin:'0px 0px -8% 0px'});rv.forEach(x=>o.observe(x))}else rv.forEach(x=>x.classList.add('on'));
// 홈 필터
const grid=document.getElementById('all');if(!grid)return;
const cards=[...grid.children],q=document.getElementById('q'),cats=[...document.querySelectorAll('.cat')],extra=document.getElementById('extra'),
 head=document.getElementById('all-h'),cnt=document.getElementById('all-n'),none=document.getElementById('none');
let cur='all';
function apply(push){const w=(q.value||'').trim().toLowerCase();let n=0;
 cards.forEach(c=>{const ok=(cur==='all'||c.dataset.tags.split(' ').includes(cur))&&(!w||c.dataset.find.includes(w));c.hidden=!ok;if(ok)n++});
 cats.forEach(c=>c.setAttribute('aria-pressed',String(c.dataset.cat===cur)));
 const busy=cur!=='all'||w;extra.hidden=!!busy;none.hidden=n>0;
 const lab=cats.find(c=>c.dataset.cat===cur).dataset.label;
 head.textContent=w?('“'+q.value.trim()+'” 찾은 숙소'):(cur==='all'?'전체 숙소':lab+' 숙소');cnt.textContent=n+'곳';
 if(push){history.replaceState(null,'',cur==='all'?location.pathname:'#'+cur);if(busy)document.getElementById('list').scrollIntoView({behavior:rm?'auto':'smooth',block:'start'})}}
cats.forEach(c=>c.addEventListener('click',()=>{cur=c.dataset.cat;apply(true)}));
q.addEventListener('input',()=>apply(false));document.getElementById('qf').addEventListener('submit',e=>{e.preventDefault();apply(true)});
const h=location.hash.slice(1);if(cats.some(c=>c.dataset.cat===h)){cur=h}apply(false);
})();
"""


def page(title, desc, path, body, index=True, jsonld=None, og_image=None, search=False):
    robots = "index,follow" if index else "noindex,follow"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    og = f'<meta property="og:image" content="{SITE}{og_image}"><meta name="twitter:card" content="summary_large_image">' if og_image else ""
    sbox = ('<form class="search" id="qf" role="search"><input id="q" type="search" placeholder="숙소 이름·지역 찾기 (예: 가평, 온천)" '
            f'aria-label="숙소 찾기" autocomplete="off"><button class="go" aria-label="찾기">{icon("magnifying-glass")}</button></form>') if search else '<div style="flex:1"></div>'
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<meta name="robots" content="{robots}"><link rel="canonical" href="{SITE}{path}">
<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#181818" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preload" href="/fonts/p700.woff2" as="font" type="font/woff2" crossorigin>
<meta property="og:type" content="website"><meta property="og:site_name" content="투키즈노트"><meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{SITE}{path}">{og}
<style>{CSS}</style>{ld}</head><body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<div class="ad">네이버 여행 커넥트·쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</div>
<header class="hd"><div class="wrap"><div class="row"><a class="logo" href="/" aria-label="투키즈노트 홈">{LOGO}투키즈노트</a>{sbox}
<nav><a class="hide-m" href="/about/">숙소 고르는 기준</a><a href="https://www.instagram.com/2kids_note/" rel="noopener">인스타그램</a></nav></div>
{{cats}}</div></header>
<main id="main"><div class="wrap">{body}</div></main>
<footer><div class="wrap"><div class="row"><div>투키즈노트 · 쌍둥이 엄마의 아이랑 숙소 노트<br>가격·운영은 날짜와 상품에 따라 바뀌어요. 예약 전에 예약 페이지에서 꼭 확인해 주세요.</div>
<nav><a href="/">전체 숙소</a><a href="/about/">숙소 고르는 기준</a><a href="https://www.instagram.com/2kids_note/" rel="noopener">인스타그램</a></nav></div></div></footer>
<script>{JS}</script></body></html>"""


def cats_bar():
    return '<div class="cats" role="toolbar" aria-label="테마">' + "".join(
        f'<button class="cat" type="button" data-cat="{k}" data-label="{e(n)}" aria-pressed="{str(k == "all").lower()}">{icon(ic)}<span>{e(n)}</span></button>'
        for k, n, ic in CATS) + "</div>"


def go_url(st, where):
    return f'{GO.format(n=st["n"])}?src=kids-{where}'


BADGES = [("villa", "독채 풀빌라"), ("kids", "키즈룸·놀이"), ("onsen", "온천"), ("snow", "눈·스키"), ("water", "실내 물놀이"), ("abroad", "해외")]


def stay_card(st, lazy=True, rail=False, skip=None):
    ph = st["media"]["photos"][:5]
    imgs = "".join(
        f'<img src="{murl(st, p["small"])}" alt="{e(st["name"])} 사진 {i + 1}" width="{min(640, p["w"])}" height="{round(min(640, p["w"]) * p["h"] / p["w"])}"'
        f'{" loading=lazy decoding=async" if (lazy or i) else ""}>' for i, p in enumerate(ph))
    dots = f'<div class="dots">{"".join("<i class=on></i>" if i == 0 else "<i></i>" for i in range(len(ph)))}</div>' if len(ph) > 1 else ""
    t = st["tags"]
    badge_txt = next((lab for key, lab in BADGES if key in t and key != skip), "")
    badge = f'<span class="badge">{e(badge_txt)}</span>' if badge_txt else ""
    reel = f'<span class="reel">{icon("play")}릴스</span>' if st["media"]["reel"] else ""
    find = " ".join([st["name"], st["region"], st["type"], st["theme"], st["one"]]).lower()
    return (f'<a class="card" href="/stay/{st["slug"]}/" data-tags="{" ".join(sorted(t))}" data-find="{e(find)}">'
            f'<div class="ph"><div class="strip">{imgs}</div>{dots}{badge}</div>'
            f'<div class="meta"><div class="t"><span>{e(st["name"])}</span>{reel}</div>'
            f'<div class="l">{e(place_label(st))} · {e(dist_label(st))}</div>'
            f'<div class="l">{e(st["one"])}</div><div class="p">{price_html(st)}</div></div></a>')


def reel_card(st):
    r = st["media"]["reel"]
    return (f'<a class="rc" href="/stay/{st["slug"]}/" aria-label="{e(st["name"])} 릴스 보기">'
            f'<img src="{murl(st, r["poster"])}" alt="" loading="lazy" decoding="async">'
            f'<video muted playsinline loop preload="none" data-auto data-src="{murl(st, r["src"])}"></video>'
            f'<span class="play">{icon("play")}</span>'
            f'<span class="cap"><b>{e(st["name"])}</b><span>{e(place_label(st))}</span></span></a>')


def rail(rid, title, sub, items, reels=False, skip=None):
    if not items:
        return ""
    arrows = (f'<div class="arrows"><button type="button" data-rail="{rid}" data-dir="-1" aria-label="이전">{icon("caret-left")}</button>'
              f'<button type="button" data-rail="{rid}" data-dir="1" aria-label="다음">{icon("caret-right")}</button></div>')
    inner = "".join(reel_card(s) if reels else stay_card(s, rail=True, skip=skip) for s in items)
    return (f'<section class="sec rv-in"><div class="sec-h"><div><h2>{e(title)}</h2><div class="sub">{e(sub)}</div></div>{arrows}</div>'
            f'<div class="rail{" reels" if reels else ""}" id="{rid}">{inner}</div></section>')


def kv(rows):
    return '<dl class="kv">' + "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in rows) + "</dl>"


CHECK_ICONS = {"first": ("crown", "첫째 (공주·노래·춤)"), "second": ("car-profile", "둘째 (자동차·블록·공)"),
               "pool": ("swimming-pool", "물놀이 (둘 다 좋아함)"), "move": ("path", "강동구에서 거리"), "money": ("wallet", "우리 4인 가족 1박")}


def iso_dur(sec):
    s = int(round(sec))
    return f"PT{s // 60}M{s % 60}S" if s >= 60 else f"PT{s}S"


def stay_page(st, all_stays):
    title = f"{st['name']} | {st['one']}"
    if len(title) > 60:
        title = f"{st['name']} | {st['sigungu'] or st['region']} 아이랑 숙소 정리"
    money = st["checks"]["money"]
    desc = f"{st['one']}. {money} 객실 차이·추가 요금·아이 기준 체크를 정리했어요."
    path = f"/stay/{st['slug']}/"
    m = st["media"]
    photos = m["photos"]
    crumb = (f'<nav class="crumb" aria-label="위치"><a href="/">전체 숙소</a> › {e(st["sido"])}'
             f'{" › " + e(st["sigungu"]) if st["sigungu"] else ""}</nav>')
    head = (f'{crumb}<div class="st-h"><h1>{e(st["name"])}</h1><div class="sub"><span><b>{e(place_label(st))}</b></span>'
            f'<span>{e(st["type"])}</span><span>{e(dist_label(st))}</span>'
            f'{"<span>가격 " + e(st["price_date"]) + " 확인</span>" if st.get("price_date") else ""}</div></div>')
    gal = mgal = ""
    r = m["reel"]
    hero = ""
    if r:
        hero = (f'<div class="gv"><img class="bg" src="{murl(st, r["poster"])}" alt="" aria-hidden="true">'
                f'<video muted playsinline loop preload="none" poster="{murl(st, r["poster"])}" data-auto data-src="{murl(st, r["src"])}" '
                f'aria-label="{e(st["name"])} 릴스 영상"></video>'
                f'<span class="tag">{icon("play")}투키즈노트 릴스</span>'
                f'<button class="snd" type="button" aria-pressed="false" aria-label="소리 켜기">'
                f'<span class="off">{icon("speaker-slash")}</span><span class="on">{icon("speaker-high")}</span></button></div>')
    if photos or hero:
        show = photos[:4] if hero else photos[:5]
        cells = ([hero] if hero else []) + [
            f'<a href="{murl(st, p["src"])}" aria-label="사진 {i + 1} 크게 보기"><img src="{murl(st, p["src"] if (i == 0 and not hero) else p["small"])}" '
            f'alt="{e(st["name"])} 사진 {i + 1}"{"" if (i == 0 and not hero) else " loading=lazy"} decoding="async"></a>' for i, p in enumerate(show)]
        gal = f'<div class="gal n{min(len(cells), 5)}">{"".join(cells)}</div>'
        slides = ([hero] if hero else []) + [
            f'<img src="{murl(st, p["src"])}" alt="{e(st["name"])} 사진 {i + 1}"{"" if (i == 0 and not hero) else " loading=lazy"} decoding="async">'
            for i, p in enumerate(photos)]
        mgal = f'<div class="mgal"><div class="strip">{"".join(slides)}</div><span class="n">1 / {len(slides)}</span></div>'
        creds = sorted({p["credit"] for p in photos})
        gal += mgal + (f'<p class="credit">{"영상: 투키즈노트 릴스 · " if hero else ""}사진: {e(" · ".join(creds))} · 실제와 다를 수 있어요</p>' if creds else "")
    # 예약 카드
    if st["total4"] is not None:
        rows = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in st["total4_lines"])
        price_box = (f'<div class="big">{won(st["total4"])} <span>/ 넷이서 1박</span></div>'
                     f'<dl>{rows}<dt class="sum">합계</dt><dd class="sum">{won(st["total4"])}</dd></dl>')
        mbar_p = f'<b>{won(st["total4"])}</b><span>넷이서 1박 · {e(st["price_date"])} 기준</span>'
    else:
        price_box = f'<div class="big">{won(st["room_price"])} <span>/ 객실 1박부터</span></div><p class="why">{e(st["total4_lines"])}</p>'
        mbar_p = f'<b>{won(st["room_price"])}부터</b><span>객실 1박 · {e(st["price_date"])} 기준</span>'
    book = (f'<aside class="book-col"><div class="book">{price_box}'
            f'<a class="btn" rel="sponsored nofollow" href="{go_url(st, "top")}">예약 가능한 객실 보기{icon("arrow-up-right")}</a>'
            f'<p class="note">기준: {e(st["price_basis"])} · {e(st["price_date"])} 확인. 쿠팡 트래블로 이동하며, 링크로 예약하면 수수료를 받아요 (가격은 같아요).</p></div></aside>')
    mbar = f'<div class="mbar"><div>{mbar_p}</div><a class="btn" rel="sponsored nofollow" href="{go_url(st, "bottom")}">객실 보기</a></div>'
    mtotal = f'<section class="blk mtotal"><h2>넷이서 실제 1박</h2><div class="book" style="position:static">{price_box}<p class="note">기준: {e(st["price_basis"])}</p></div></section>'
    feats = "".join(
        f'<div class="feat{"" if st["checks"][k] else " no"}">{icon(ic)}<div><b>{e(lbl)}</b><p>{e(st["checks"][k] or "해당 시설 안내가 없어요")}</p></div></div>'
        for k, (ic, lbl) in CHECK_ICONS.items())
    fit = (f'<div class="fit"><div class="ok"><b>{icon("check-circle")}이런 집에 맞아요</b>{e(st["fit"]["good"])}</div>'
           f'<div class="ng"><b>{icon("x-circle")}이런 집은 다시 생각해요</b>{e(st["fit"]["bad"])}</div></div>')
    reel = ""
    if m["reel"]:
        r = m["reel"]
        links = ""
        if r.get("instagram"):
            links += f'<a href="{e(r["instagram"])}" rel="noopener">{icon("instagram-logo")}인스타그램에서 보기</a>'
        if r.get("youtube"):
            links += f'<a href="{e(r["youtube"])}" rel="noopener">{icon("youtube-logo")}유튜브 쇼츠</a>'
        when = f'{e(r["published"])} 투키즈노트 채널에 올린 영상 · {r["seconds"]:.0f}초' if r.get("published") else f'투키즈노트 릴스 · {r["seconds"]:.0f}초'
        reel = (f'<section class="blk" id="reel"><h2>우리 채널 영상</h2><div class="reelnote">'
                f'<q>{e(r["hook"])}</q><p class="when">{when}</p><div class="links">{links}</div></div></section>')
    sections = [
        f'<section class="blk"><p class="one">{e(st["one"])}</p></section>',
        mtotal,
        f'<section class="blk"><h2>우리 쌍둥이 기준 체크</h2><p class="lead">만 5세 딸 쌍둥이와 강동구에서 출발하는 4인 가족 기준이에요.</p><div class="feats">{feats}</div></section>',
        reel,
        f'<section class="blk"><h2>한 줄 판단</h2>{fit}</section>',
    ]
    if st.get("rooms"):
        sections.append(f'<section class="blk"><h2>객실별 차이</h2>{kv(st["rooms"])}</section>')
    if st.get("costs"):
        sections.append(f'<section class="blk"><h2>따로 드는 비용</h2>{kv(st["costs"])}</section>')
    if st.get("info"):
        sections.append(f'<section class="blk"><h2>이용 정보</h2>{kv(st["info"])}</section>')
    if st.get("faq"):
        sections.append('<section class="blk"><h2>자주 묻는 질문</h2><div class="faq">' +
                        "".join(f"<div><h3>{e(q)}</h3><p>{e(a)}</p></div>" for q, a in st["faq"]) + "</div></section>")
    hp = f' 공식 홈페이지: <a href="{e(st["homepage"])}" rel="nofollow noopener">{e(re.sub(r"^https?://", "", st["homepage"]).rstrip("/"))}</a>' if st.get("homepage") else ""
    sections.append(f'<section class="blk"><p class="src">직접 다녀온 후기가 아니라 공식 홈페이지와 예약 페이지 안내를 모아 정리했어요. '
                    f'정리 {e(st["checked"])} · 가격 {e(st["price_date"])} 확인.{hp}</p></section>')
    same = [s for s in all_stays if s is not st and (s["sido"] == st["sido"] or s["tags"] & st["tags"] - {"near", "hotel"})]
    same.sort(key=lambda s: (-len(s["tags"] & st["tags"]), s["km"] or 9999))
    rel = rail("similar", "비슷한 숙소", "같은 지역이거나 테마가 겹치는 곳", same[:8])
    body = f'{head}{gal}<div class="lay"><div>{"".join(sections)}</div>{book}</div>{rel}{mbar}'
    img0 = murl(st, "og.jpg") if photos else None
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "투키즈노트", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": st["name"], "item": SITE + path}]},
        {"@context": "https://schema.org", "@type": "Article", "headline": title[:110], "dateModified": st["checked"],
         "author": {"@type": "Organization", "name": "투키즈노트", "url": SITE + "/about/"},
         "image": [SITE + murl(st, p["src"]) for p in photos[:3]],
         "about": {"@type": "LodgingBusiness", "name": st["name"],
                   "address": {"@type": "PostalAddress", "addressRegion": st["sido"], "addressLocality": st["sigungu"],
                               "addressCountry": "JP" if st["sido"] == "해외" and "일본" in st["region"] else "KR"}}}]
    if m["reel"]:
        r = m["reel"]
        ld.append({"@context": "https://schema.org", "@type": "VideoObject", "name": f"{st['name']} — {r['hook']}"[:100],
                   "description": st["one"], "thumbnailUrl": [SITE + murl(st, r["poster"])],
                   "uploadDate": (r.get("published") or st["checked"]) + "T11:00:00+09:00",
                   "duration": iso_dur(r["seconds"]), "contentUrl": SITE + murl(st, r["src"])})
    return path, page(title, desc, path, body, st["index"], ld, og_image=img0).replace("{cats}", "")


def home(stays):
    reels = sorted([s for s in stays if s["media"]["reel"] and s["media"]["reel"].get("published")],
                   key=lambda s: s["media"]["reel"]["published"], reverse=True)
    near = sorted([s for s in stays if "near" in s["tags"]], key=lambda s: s["km"])
    cheap = sorted([s for s in stays if s["total4"] is not None], key=lambda s: s["total4"])
    water = [s for s in stays if "water" in s["tags"]]
    n_reel = sum(1 for s in stays if s["media"]["reel"])
    intro = (f'<section class="intro"><div><h1>쌍둥이 엄마가 찜해 둔 아이랑 숙소</h1>'
             f'<p>만 5세 딸 쌍둥이와 강동구에서 출발하는 4인 가족 기준으로, 추가 요금까지 더한 넷이서 실제 1박 가격과 아이 기준 체크를 정리해요.</p></div>'
             f'<div class="facts"><span>{icon("house-line")}숙소 {len(stays)}곳</span><span>{icon("play")}릴스 {n_reel}편</span>'
             f'<span>{icon("wallet")}넷이서 실제 가격</span></div></section>')
    extra = ('<div id="extra">'
             + rail("r-reel", "릴스로 먼저 보기", "투키즈노트 인스타그램에 올린 영상이에요", reels[:10], reels=True)
             + rail("r-near", "강동구에서 1박 다녀오기 좋은 곳", "직선 150km 안쪽, 가까운 순", near[:10])
             + rail("r-cheap", "넷이서 실제 1박이 가벼운 곳", "추가 인원·필수 현장결제까지 더한 가격 순", cheap[:10])
             + rail("r-water", "겨울에도 아이 둘이 물에 들어가는 곳", "실내 수영장·온수풀·온천", water[:10], skip="water")
             + "</div>")
    order = sorted(stays, key=lambda s: (not s["index"], -(len(s["media"]["photos"]) > 1), s["km"] if s["km"] is not None else 9999))
    grid = (f'<section class="sec" id="list"><div class="sec-h"><div><h2 id="all-h">전체 숙소</h2><div class="sub count" id="all-n">{len(stays)}곳</div></div></div>'
            f'<div class="grid" id="all">{"".join(stay_card(s) for s in order)}</div>'
            f'<p class="empty" id="none" hidden>찾는 숙소가 아직 없어요. 다른 테마를 눌러 보세요.</p></section>')
    return intro + extra + grid


ABOUT = """<article class="prose"><h1>숙소를 고르고 정리하는 기준</h1>
<p>투키즈노트는 만 5세 딸 쌍둥이를 키우는 엄마의 눈으로 아이랑 갈 숙소를 고르는 노트예요. 서울 강동구에서 출발하는 평범한 4인 가족 기준으로 봐요.</p>
<h2>우리 집 기준</h2><ul>
<li>첫째는 공주 스타일에 노래·춤을 좋아하고, 둘째는 자동차·블록·공놀이를 좋아해요. 둘 다 수영장을 좋아해요.</li>
<li>가격은 객실값만이 아니라 필수 현장결제·추가 인원 요금까지 더한 '넷이서 실제 1박'으로 봐요.</li>
<li>거리는 강동구에서의 직선거리로 1박이 편한지 따져요.</li></ul>
<h2>정보와 사진은 어디서 오나요</h2>
<p>공식 홈페이지와 예약 페이지(쿠팡 트래블) 안내를 모아 정리해요. 페이지마다 가격 확인일을 적고, 오래된 정보는 검색에 내보내지 않아요. 사진은 숙소 공식 홈페이지·예약 페이지 사진이고, 영상은 그 사진으로 만들어 투키즈노트 인스타그램에 올린 릴스예요. 직접 다녀온 후기가 아니고, 다녀온 곳은 따로 표시할 예정이에요.</p>
<h2>수익</h2><p>예약 버튼은 제휴 링크예요. 이 링크로 예약하면 투키즈노트가 수수료를 받지만, 가격은 똑같아요. 수수료 때문에 단점을 빼지 않아요.</p></article>"""


def subset_fonts(texts):
    """페이지에 쓰인 글자만 남긴 Pretendard woff2 (없으면 시스템 글꼴로)."""
    try:
        from fontTools import subset
    except ImportError:
        return "fonttools 없음 — 웹 글꼴 없이 시스템 글꼴로 보임 (pip install fonttools brotli)"
    chars = set("".join(texts)) | set("0123456789,.·…%₩원 ")
    chars = "".join(sorted(c for c in chars if ord(c) >= 32))
    (OUT / "fonts").mkdir(exist_ok=True)
    for w, name in ((500, "Medium"), (600, "SemiBold"), (700, "Bold")):
        opt = subset.Options()
        opt.flavor = "woff2"
        opt.layout_features = ["kern", "liga", "tnum"]
        f = subset.load_font(str(FONTS / f"Pretendard-{name}.otf"), opt)
        s = subset.Subsetter(opt)
        s.populate(text=chars)
        s.subset(f)
        subset.save_font(f, str(OUT / "fonts" / f"p{w}.woff2"), opt)
    return None


def og_image(st):
    """공유 썸네일 1200×630 (첫 사진)."""
    from PIL import Image
    dst = MEDIA / st["slug"] / "og.jpg"
    if dst.exists() or not st["media"]["photos"]:
        return
    im = Image.open(MEDIA / st["slug"] / st["media"]["photos"][0]["src"]).convert("RGB")
    W, H = 1200, 630
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    im.crop((l, t, l + W, t + H)).save(dst, "JPEG", quality=82, optimize=True)


def main():
    import shutil
    stays, errors = load()
    warns = []
    for st in stays:
        bad = lint(st)
        if bad:
            errors.append(f"{st['id']}: 방문·체험 표현 금지 {bad}")
        st["media"] = load_media(st)
        st["tags"] = tags_of(st)
        if not st["media"]["photos"]:
            warns.append(f"{st['id']}: 사진 없음 (python3 2kids/site/media.py {st['id']})")
        og_image(st)
    slugs = [s["slug"] for s in stays]
    if len(set(slugs)) != len(slugs):
        errors.append("slug 중복")
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=1))
        sys.exit(1)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    texts = []

    def write(path, text):
        f = OUT / path.strip("/") / "index.html" if path.endswith("/") else OUT / path.strip("/")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
        texts.append(re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.S))

    stays.sort(key=lambda s: (s["km"] is None, s["km"] or 0))
    indexed = [s for s in stays if s["index"]]
    for st in stays:
        path, html_ = stay_page(st, stays)
        write(path, html_)
        shutil.copytree(MEDIA / st["slug"], OUT / "media" / st["slug"], ignore=shutil.ignore_patterns("media.json"))

    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "투키즈노트", "url": SITE + "/"},
          {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "url": f"{SITE}/stay/{s['slug']}/"} for i, s in enumerate(indexed)]}]
    first = next((s for s in stays if s["media"]["photos"]), None)
    write("/", page("투키즈노트 | 쌍둥이 엄마가 정리한 아이랑 숙소",
                    "만 5세 쌍둥이 4인 가족 기준으로 정리한 아이랑 숙소. 넷이서 실제 1박 가격·물놀이·키즈룸·온천 테마별로.",
                    "/", home(stays), True, ld, og_image=murl(first, "og.jpg") if first else None, search=True).replace("{cats}", cats_bar()))
    write("/about/", page("투키즈노트가 숙소를 고르고 정리하는 기준", "누가 어떤 기준으로 숙소를 고르고 가격을 확인하는지.", "/about/",
                          ABOUT).replace("{cats}", ""))
    write("/404.html", page("페이지를 찾을 수 없어요 | 투키즈노트", "주소가 바뀌었거나 없는 페이지예요.", "/404.html",
                            '<article class="prose"><h1>찾는 페이지가 없어요</h1><p>주소가 바뀌었거나 내려간 숙소예요.</p>'
                            '<p><a class="btn" style="width:auto;display:inline-flex" href="/">전체 숙소 보기</a></p></article>', False).replace("{cats}", ""))

    warn = subset_fonts(texts)
    if warn:
        warns.append(warn)
    (OUT / "favicon.svg").write_text(FAVICON)
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    urls = [("/", TODAY.isoformat()), ("/about/", TODAY.isoformat())] + [(f"/stay/{s['slug']}/", s["price_date"]) for s in indexed]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{SITE}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n")
    (OUT / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n/media/*\n  Cache-Control: public, max-age=604800\n"
                                  "/fonts/*\n  Cache-Control: public, max-age=31536000, immutable\n")
    (OUT / "_redirects").write_text("/map/ / 301\n/map / 301\n")
    report = {"built": TODAY.isoformat(), "stays": len(stays), "indexed": len(indexed),
              "noindex": {s["id"]: s["why_noindex"] for s in stays if not s["index"]}, "warnings": warns}
    (HERE / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
