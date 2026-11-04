#!/usr/bin/env python3
"""줍줍알람 사이트 생성기 — site/data → site/public

    python3 site/build.py            # 오늘(한국 시간) 기준으로 전체 빌드
    python3 site/build.py --today 2026-11-02   # 날짜를 정해 미리보기

입력
  data/applyhome.json   '청약홈API' 탭 행 (⑦이 매일 덮어씀)
  data/apt/{key}.json   공고별 편집 데이터 (⑦이 작성: 한마디·FAQ·자격·이미지 등)
  data/regions.json     지역 슬러그 표
  data/state.json       첫 공개일·내용 지문 (빌드가 갱신, 커밋할 것)
출력
  public/               Cloudflare Pages가 그대로 배포 (빌드 명령 없음)
검사에 실패하면 종료 코드 1 — 그때는 푸시하지 않는다.
"""
import argparse, datetime as dt, hashlib, html, json, os, re, shutil, sys
from pathlib import Path
from xml.sax.saxutils import escape as xesc

from jinja2 import Environment, FileSystemLoader, select_autoescape
sys.path.insert(0, str(Path(__file__).resolve().parent))
import guides as GUIDES
from markupsafe import Markup

SITE = Path(__file__).resolve().parent
REPO = SITE.parent
DATA = SITE / "data"
PUB = SITE / "public"
BASE = "https://jupjupalarm.com"
IG = "https://www.instagram.com/jupjup_alarm/"
THREADS = "https://www.threads.net/@jupjup_alarm"
BLOG = "https://blog.naver.com/jupjupalarm"          # 청약노트 네이버 블로그 (연관 채널)
YOUTUBE = "https://www.youtube.com/channel/UCbIKC-joj_M279Tii7sLSiA"
# 쿠팡 파트너스 다이나믹 배너 (공고 페이지). mq = 이 화면 조건일 때만 불러옴(숨긴 채 노출되지 않게)
COUPANG = {
    "pc": {"mq": "(min-width:1024px)", "height": 298,
           "opts": {"id": 1044288, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "298", "tsource": ""}},
    # 메인: 첫 공고 묶음 아래 가로형 (PC 배너 id를 크기만 바꿔 씀)
    "home": {"mq": "(min-width:768px)", "height": 140,
             "opts": {"id": 1044288, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "140", "tsource": ""}},
    # 메인 모바일 (사용자 결정 2026-10-29: 시안 A 첫 묶음 아래 띠 + 시안 C 목록 끝 큰 배너).
    # 모바일 전용 배너 id 1044447 (사용자 생성 2026-10-29, 원본 300×120 — 폭은 100%로 맞춤)
    "home_mo": {"mq": "(max-width:767px)", "height": 120,
                "opts": {"id": 1044447, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "120", "tsource": ""}},
    "home_end_mo": {"mq": "(max-width:767px)", "height": 300,
                    "opts": {"id": 1044447, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "300", "tsource": ""}},
    # 공고 상세 모바일 (사용자 결정 2026-10-29: 시안 B 신청 자격 아래 띠 + 시안 C FAQ 뒤 큰 배너.
    # 2026-11-03 사용자 결정: 요약 카드 바로 아래(한마디 위)에 띠 배너 하나 더 — apt_top_mo. 애드센스는 그 위 3초 판단 카드 아래로 올림)
    "apt_top_mo": {"mq": "(max-width:1023px)", "height": 120,
                   "opts": {"id": 1044447, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "120", "tsource": ""}},
    "apt_mo": {"mq": "(max-width:1023px)", "height": 120,
               "opts": {"id": 1044447, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "120", "tsource": ""}},
    "apt_end_mo": {"mq": "(max-width:1023px)", "height": 300,
                   "opts": {"id": 1044447, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "300", "tsource": ""}},
}
# 애드센스 (승인 전이라 비어 있음 — client에 ca-pub-…, slots에 광고 단위 ID를 넣으면 그 자리에 나옴)
ADSENSE = {"client": "ca-pub-1196853150959268", "slots": {"apt_top": "5439503161", "guide_mid": "5439503161"}}  # 2026-11-03 사이트 연결 + 광고 단위 '사각형_반응형' (공고 3초 판단 카드 아래 — 11/3 한마디 아래에서 올림 · 가이드 본문 중간)
# 구글 애널리틱스 4 — 측정 ID(G-XXXXXXXXXX)를 넣으면 모든 페이지에 붙음 (사용자 요청 2026-10-29). 비우면 아무것도 안 붙음
GA = {"id": "G-6103BRQ0LP"}
COUPANG_NOTE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
KST = dt.timezone(dt.timedelta(hours=9))
DOW = "월화수목금토일"

KINDS = {
    "mujeonwi": ("무순위·줍줍", "무순위(줍줍) 청약"),
    "private": ("민간분양", "민간분양 청약"),
    "public": ("공공분양", "공공분양 청약"),
    "newlywed": ("신혼희망타운", "신혼희망타운 청약"),
    "rental": ("공공임대", "공공임대·행복주택 모집"),
}
RENTAL_EXPLAIN = {
    "일반 매입임대": "LH가 도심의 기존 다가구·다세대 주택을 사들여 무주택 저소득 가구에 시중 시세보다 낮은 임대료로 빌려주는 공공임대예요. 단지 하나가 아니라 여러 동네의 집을 한 공고로 모집해요.",
    "청년 매입임대": "LH가 사들인 기존 주택을 무주택 청년에게 시중 시세보다 낮은 임대료로 빌려주는 공공임대예요. 여러 동네의 집을 한 공고로 모집해요.",
    "신혼·신생아 매입임대": "LH가 사들인 기존 주택을 신혼부부·신생아 가구에 시중 시세보다 낮은 임대료로 빌려주는 공공임대예요. 여러 동네의 집을 한 공고로 모집해요.",
    "다자녀 매입임대": "LH가 사들인 기존 주택을 다자녀 가구에 시중 시세보다 낮은 임대료로 빌려주는 공공임대예요.",
    "든든전세": "LH가 사들인 주택을 시세보다 낮은 전세로 빌려주는 매입임대예요. 월세 없이 보증금만 내요.",
}
COMP_FAQ = [   # 청약 경쟁률 허브 자주 묻는 질문 (2026-11-04) — 이 사이트 계산 방식과 일반 원칙만, 공고별 수치 없음
    ("평균 경쟁률과 최고 경쟁률은 어떻게 달라요?",
     "평균 경쟁률은 그 공고의 전체 접수 건수를 전체 공급 세대로 나눈 값이에요. 최고 경쟁률은 주택형·순위별로 따로 낸 경쟁률 중 가장 높은 값이라, 인기 타입 하나에 몰리면 평균보다 훨씬 높게 나와요."),
    ("경쟁률이 1대 1보다 낮으면 무슨 뜻이에요?",
     "접수한 사람이 공급 세대보다 적은 '미달'이에요. 남은 세대는 나중에 무순위(줍줍)로 다시 나올 수 있어서, 미달 단지는 줍줍 공고를 같이 지켜보는 게 좋아요."),
    ("이 페이지의 경쟁률은 어디서 가져와요?",
     "한국부동산원 청약홈이 공개하는 공식 경쟁률을 공공데이터포털로 받아 그대로 옮겨요. 평균은 그 값으로 줍줍알람이 계산한 값이고, 공식 결과는 청약홈에서 다시 확인하세요."),
]

KIND_INTRO = {
    "mujeonwi": "1·2순위 청약이 끝난 뒤 남은 세대나 계약 취소분을 다시 뽑는 공고예요. 청약통장 없이 추첨으로 뽑고, 2025년 6월 10일부터는 무주택세대구성원만 신청할 수 있어요. 거주지역 요건과 재당첨 제한은 공고마다 달라요. 임의공급(사업주체가 조건을 따로 정하는 공급)도 여기에 함께 모았어요.",
    "private": "민간 건설사가 짓는 아파트의 일반 청약이에요. 청약통장이 필요하고, 지역·면적에 따라 가점제와 추첨제 비율이 달라요.",
    "public": "LH·SH·GH 같은 공공기관이 공급하는 분양 주택이에요. 무주택세대구성원이 청약통장으로 신청하고, 소득·자산 기준과 전매 제한·거주의무가 붙는 경우가 많아요. 토지임대부도 여기에 모았어요.",
    "newlywed": "신혼부부·예비신혼부부·한부모가족에게 공급하는 공공분양이에요. 소득·자산 기준이 있고, 신혼희망타운 전용 모기지와 연계되는 경우가 많아요.",
    "rental": "LH·SH·GH의 행복주택·국민임대·매입임대 같은 공공임대 모집 공고예요.",
}
STATUS = {  # 코드: (배지, 배지 class)
    "upcoming": ("접수 예정", "b-soon"),
    "open": ("접수 중", "b-open"),
    "waiting": ("발표 대기", "b-wait"),
    "announced": ("발표 완료", "b-done"),
    "pre": ("공고 전", "b-pre"),
    "released": ("공고 나옴", "b-soon"),
}

# ───────────────────────── 표기 도우미 (디자인 방향 문서 '표기 규칙') ─────────────────────────
TODAY = None  # main()에서 정함


def d(iso):
    """'2026-11-02' → '11.2(월)' (올해), '2027.2.16(화)' (다른 해)."""
    if not iso:
        return ""
    x = dt.date.fromisoformat(iso[:10])
    s = f"{x.month}.{x.day}({DOW[x.weekday()]})"
    return s if x.year == TODAY.year else f"{x.year}.{s}"


def drange(a, b):
    if not b or a == b:
        return d(a)
    return f"{d(a)} ~ {d(b)}"


def month(s):
    """'2029년 10월' / '2029-10' → '2029.10'"""
    m = re.search(r"(\d{4})\D+(\d{1,2})", s or "")
    return f"{m.group(1)}.{int(m.group(2))}" if m else (s or "")


def won(n):
    """원 단위 정수 → '8억9,800만원' (만원 아래는 버림 — 금액 표기는 이 함수 하나로)."""
    man = n // 10000
    eok, rest = divmod(man, 10000)
    if eok and rest:
        return f"{eok}억{rest:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{rest:,}만원"


def money(n):
    """원 단위 정수 → '5,763만6,000원' (임대 보증금·월세처럼 원 단위까지 정확히)."""
    if n is None:
        return ""
    eok, rest = divmod(int(n), 10**8)
    man, w = divmod(rest, 10**4)
    out = ""
    if eok:
        out += f"{eok}억"
    if man:
        out += f"{man:,}만"
    if w:
        out += f"{w:,}"
    return (out or "0") + "원"


def parse_won(s):
    m = re.search(r"(?:(\d+)억)?\s*(?:([\d,]+)만)?\s*원", s)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 10**8 + int((m.group(2) or "0").replace(",", "")) * 10**4


def phone(s):
    s = re.sub(r"\D", "", s or "")
    if not s:
        return ""
    if s.startswith("02"):
        return f"02-{s[2:-4]}-{s[-4:]}"
    if len(s) == 8:
        return f"{s[:4]}-{s[4:]}"
    return f"{s[:3]}-{s[3:-4]}-{s[-4:]}"


def py(m2):
    return f"{m2 / 3.3058:.1f}"


def m2(v):
    return f"{v:g}㎡" if float(v).is_integer() else f"{v:.2f}㎡"


def fill(text):
    """편집 문장 안의 {d:2026-11-02}, {r:2026-11-02:2026-11-03} 을 날짜 표기로 바꿈."""
    text = re.sub(r"\{d:(\d{4}-\d\d-\d\d)\}", lambda m: d(m.group(1)), text or "")
    return re.sub(r"\{r:(\d{4}-\d\d-\d\d):(\d{4}-\d\d-\d\d)\}", lambda m: drange(m.group(1), m.group(2)), text)


def tdate(iso):
    """<time> 태그."""
    return Markup(f'<time datetime="{iso[:10]}">{html.escape(d(iso))}</time>')


def tlwhen(a, b=None):
    """일정 왼쪽 날짜칸: 다른 해면 연도를 작은 줄로 따로 (2027.3.22(월)이 칸에서 꺾이지 않게)."""
    def one(iso, show_year):
        x = dt.date.fromisoformat(iso[:10])
        y = f'<span class="y">{x.year}</span>' if show_year else ""
        return f'{y}<time datetime="{iso[:10]}">{x.month}.{x.day}({DOW[x.weekday()]})</time>'
    xa = dt.date.fromisoformat(a[:10])
    out = one(a, xa.year != TODAY.year)
    if b and b != a:
        xb = dt.date.fromisoformat(b[:10])
        out += ('<br><span class="y">' + str(xb.year) + "</span>~ " if xb.year != xa.year else "<br>~ ") + one(b, False)
    return Markup(out)


def sd(iso):
    """'2026-11-02' → '11.2' (올해), '2027.2.16' (다른 해) — 날짜 카드용 짧은 표기."""
    if not iso:
        return ""
    x = dt.date.fromisoformat(iso[:10])
    return f"{x.month}.{x.day}" if x.year == TODAY.year else f"{x.year}.{x.month}.{x.day}"


# 공고 상세 바로가기 칩 (2026-11-03 사용자 결정 — 페이지에 실제로 있는 칸만, 나오는 순서대로)
CHIPS = {"h-sch": "일정", "h-chk": "나도 될까", "h-gap": "시세 비교", "h-fund": "돈 계산", "h-rent": "입주·월 비용", "h-odds": "경쟁 예상",
         "h-trap": "주의점", "h-comp": "경쟁률", "h-price": "분양가 표", "h-houses": "주택 목록", "h-plan": "평면", "h-layout": "배치도",
         "h-tour": "둘러보기", "h-loc": "위치", "h-elig": "자격", "h-faq": "FAQ"}


def chipnav(h, n):
    ids = [i for i in re.findall(r'<h2 id="([\w-]+)"', h) if i in CHIPS]
    if len(ids) < 3:
        return h.replace("<!--CHIPNAV-->", "")
    lab = dict(CHIPS)
    if n.get("is_rental"):
        lab["h-price"] = "임대 조건"
    nav = '<nav class="chipnav" aria-label="이 페이지 바로가기">' + "".join(f'<a href="#{i}">{lab[i]}</a>' for i in ids) + "</nav>"
    return h.replace("<!--CHIPNAV-->", nav)


def h2s(text, n):
    """'계양신도시 카이브 유보라 AC3블록 청약 일정' → <span class="k">단지명</span> <span class="t">청약 일정</span> (검색어 그대로, 보기만 2단)."""
    t = str(text or "")
    for nm in sorted({x for x in (n.get("complex"), n.get("title"), n.get("h1_base")) if x}, key=len, reverse=True):
        if t.startswith(nm + " ") and len(t) > len(nm) + 1:
            return Markup(f'<span class="k">{html.escape(nm)}</span> <span class="t">{html.escape(t[len(nm) + 1:])}</span>')
    return t


def trange(a, b=None):
    if not b or a == b:
        return tdate(a)
    return Markup(f"{tdate(a)} ~ {tdate(b)}")


def tmonth(s):
    m = re.search(r"(\d{4})\D+(\d{1,2})", s or "")
    if not m:
        return s
    return Markup(f'<time datetime="{m.group(1)}-{int(m.group(2)):02d}">{m.group(1)}.{int(m.group(2))}</time>')


# ───────────────────────── 데이터 읽기 ─────────────────────────
def split_range(s):
    p = [x.strip() for x in (s or "").split("~")]
    return (p[0], p[1] if len(p) > 1 else p[0]) if p[0] else (None, None)


def parse_models(text):
    out = []
    for line in (text or "").splitlines():
        m = re.match(r"\s*([^:]+):\s*(.*)", line)
        if not m:
            continue
        name, rest = m.group(1).strip(), m.group(2)
        gen = re.search(r"일반\s*([\d,]+)", rest)
        spe = re.search(r"특공\s*([\d,]+)", rest)
        price = re.search(r"최고\s*([\d억,만\s]+원)", rest)
        out.append({
            "type": name,
            "general": int(gen.group(1).replace(",", "")) if gen else 0,
            "special": int(spe.group(1).replace(",", "")) if spe else 0,
            "max": parse_won(price.group(1)) if price else None,
        })
    return out


def parse_comp(text):
    if not text:
        return None
    lines = text.splitlines()
    summary, rows = "", []
    for ln in lines:
        if ln.startswith("합계") or ln.startswith("1순위 합계"):
            summary = ln.split(":", 1)[1].strip()
            continue
        m = re.match(r"\s*(.+?):\s*공급\s*(\d+)\s*/\s*접수\s*(\d+)\s*/\s*경쟁률\s*(.+)", ln)
        if m:
            rows.append({"name": m.group(1), "supply": int(m.group(2)), "apply": int(m.group(3)), "rate": m.group(4).strip()})
    short = ""
    m = re.search(r"([\d,]+)세대에\s*([\d,]+)\S*\s*접수.*?평균 약\s*([\d.]+)대 1", summary)
    if len(rows) == 1 and rows[0]["rate"][0].isdigit():
        r = rows[0]
        short = f"{r['supply']}세대에 {r['apply']:,}명 · {float(r['rate']):g}대 1"
    elif m:
        short = f"{m.group(1)}세대에 {m.group(2)}건 · 평균 {float(m.group(3)):g}대 1"
    return {"summary": summary, "rows": rows, "short": short}


def load():
    rows = {r["주택관리번호"]: r for r in json.loads((DATA / "applyhome.json").read_text())["rows"]}
    regions = json.loads((DATA / "regions.json").read_text())
    state_p = DATA / "state.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    items = []
    for p in sorted((DATA / "apt").glob("*.json")):
        e = json.loads(p.read_text())
        items.append((e, rows.get(e["key"])))
    return items, regions, state


REQUIRED = ["title", "kind", "region", "take", "faq", "eligibility"]


def build_notice(e, row, regions, problems):
    key = e["key"]
    miss = [f for f in REQUIRED if not e.get(f)]
    if e.get("source") == "applyhome" and not row:
        miss.append("청약홈API 행")
    if len(e.get("faq", [])) < 3:
        miss.append("FAQ 3개 이상")
    if miss:
        problems.append((key, "보류 — 빈 값: " + ", ".join(miss)))
        return None
    r = row or {}
    n = dict(e)
    n["url"] = f"/apt/{key}/"
    n["address"] = e.get("address") or r.get("공급위치", "")
    n["units"] = int(e.get("units") or r.get("공급규모(세대)") or 0)
    n["notice_date"] = e.get("notice_date") or r.get("모집공고일")
    n["rcpt"] = (e.get("receipt_override") or e.get("rcpt") or [r.get("접수 시작"), r.get("접수 종료")])
    n["announce"] = e.get("announce") or r.get("당첨자 발표")
    n["contract"] = split_range(e.get("contract") or r.get("계약"))
    n["move_in"] = month(e.get("move_in") or r.get("입주 예정"))
    n["models"] = e.get("models") or parse_models(r.get("주택형별 공급·최고 분양가"))
    n["is_pre"] = bool(e.get("pre"))
    n["is_rental"] = e["kind"] == "rental"
    n["source_name"] = e.get("source_name") or ("청약홈" if e.get("source") == "applyhome" else "")
    # 임대: 주택형별 조건 → 면적표도 여기서 만든다
    if n["is_rental"]:
        rms = e.get("rent_models") or []
        n["rent_models"] = rms
        if rms and not e.get("areas"):
            areas = {}
            for m in rms:
                if m.get("excl"):
                    areas.setdefault(m["type"], {"excl": m["excl"], "supply": m.get("supply_area")})
            n["areas"] = areas or None
        rs = e.get("rent_summary") or {}
        if not rs and rms:
            deps = [m for m in rms if m.get("deposit")]
            if deps:
                lo = min(deps, key=lambda m: m["deposit"])
                rs = {"deposit": lo["deposit"], "monthly": lo.get("monthly"), "basis": f"{lo['type']} 기준 (가장 낮은 보증금)"}
        n["rent_summary"] = rs
        if not n["units"]:
            n["units"] = sum(m.get("units") or 0 for m in rms)
    # 매입임대(여러 동네 다가구): 주택 목록 → 지역·면적 묶음
    hs = e.get("houses") or []
    n["houses"] = hs
    n["unit_word"] = e.get("unit_word") or ("호" if hs else "세대")
    if hs:
        if not n["units"]:
            n["units"] = len(hs)
        grp = {}
        for h in hs:
            grp.setdefault(f"{h['sido']} {h['sigungu']}".strip(), []).append(h)
        n["house_groups"] = sorted(grp.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        bk = [("20㎡ 미만", 0, 20), ("20~40㎡", 20, 40), ("40~60㎡", 40, 60), ("60㎡ 이상", 60, 999)]
        n["area_buckets"] = [(lab, len([h for h in hs if h.get("excl") and lo <= h["excl"] < hi])) for lab, lo, hi in bk]
        ex = [h["excl"] for h in hs if h.get("excl")]
        n["excl_range"] = (min(ex), max(ex)) if ex else None
        n["house_sidos"] = sorted({h["sido"] for h in hs})
        for h in hs:
            h["road_short"] = " ".join(h.get("road", "").split()[1:])
        n["house_max"] = max(len(v) for _, v in n["house_groups"])
        n["bucket_max"] = max([c for _, c in n["area_buckets"]] + [1])
        rr = e.get("rent_range") or {}
        if rr and not n.get("rent_summary"):
            n["rent_summary"] = {"deposit": rr.get("deposit", [None])[0], "monthly": (rr.get("monthly") or [None])[0],
                                 "basis": "가장 낮은 금액 · 집마다 달라요", "range": True}
    n["steps"] = [[fill(a), fill(b)] for a, b in (e.get("steps") or [])]
    if n.get("lease"):
        n["lease"] = fill(n["lease"])
    n["comp"] = parse_comp(r.get("경쟁률(청약홈 공식)"))
    n["source_url"] = e.get("source_url") or r.get("청약홈 상세(공식 공고)")
    n["homepage"] = e.get("homepage") or r.get("홈페이지") or ""
    bs = (r.get("시행·시공") or "").split(" / ")
    n["developer"] = e.get("developer") or bs[0]
    n["builder"] = e.get("builder") or (bs[1] if len(bs) > 1 and bs[1] != bs[0] else "")
    n["phone"] = phone(e.get("phone") or r.get("문의"))
    n["fetched_at"] = (DATA_FETCHED or "")
    # 지역 슬러그
    sido, sgg = e["region"]["sido"], e["region"].get("sigungu")
    n["sido"], n["sigungu"] = sido, sgg
    n["sido_slug"] = regions["sido"][sido]
    n["sgg_slug"] = regions["sigungu"].get(sido, {}).get(sgg) if sgg else None
    if sgg and not n["sgg_slug"]:
        problems.append((key, f"경고 — regions.json에 '{sido} {sgg}' 슬러그 없음"))
    # 가격
    prices = [m["max"] for m in n["models"] if m.get("max")]
    n["max_price"] = max(prices) if prices else None
    top = max((m for m in n["models"] if m.get("max")), key=lambda m: m["max"], default=None)
    n["max_type"] = top["type"] if top else ""
    n["has_special"] = any(m["special"] for m in n["models"])
    n["has_general"] = any(m["general"] for m in n["models"])
    n["sum_general"] = sum(m["general"] for m in n["models"])
    n["sum_special"] = sum(m["special"] for m in n["models"])
    if n["is_pre"]:
        ok = n["rcpt"][0] and e.get("price_text") and e.get("sources_extra")
    elif n["is_rental"]:
        ok = n["rcpt"][0] and n["source_url"] and (n["rent_models"] or n["rent_summary"] or (n["houses"] and e.get("rent_level")))
    else:
        ok = n["rcpt"][0] and n["max_price"] and n["source_url"]
    if not ok:
        problems.append((key, "보류 — 접수일·가격(임대조건)·공식 출처 중 빈 값"))
        return None
    # 일정
    if e.get("schedule"):
        sch = []
        for s in e["schedule"]:
            x = dict(s)
            if isinstance(x.get("date"), list):
                x["start"], x["end"] = x["date"]
            elif x.get("date"):
                x["start"] = x["end"] = x["date"]
            if x.get("note"):
                x["note"] = fill(x["note"])
            sch.append(x)
    else:
        sch = [{"label": "모집공고", "start": n["notice_date"], "end": n["notice_date"]}]
        if e["kind"] == "mujeonwi":
            sch.append({"label": "무순위 접수", "start": n["rcpt"][0], "end": n["rcpt"][1],
                        "note": "청약홈 인터넷 접수" + (", 하루" if n["rcpt"][0] == n["rcpt"][1] else "")})
        else:
            sp = r.get("특별공급 접수")
            if sp:
                a, b = split_range(sp)
                sch.append({"label": "특별공급 접수", "start": a, "end": b})
            f1a, f1b = split_range(r.get("1순위 접수"))
            if f1a:
                sch.append({"label": "1순위 접수", "start": f1a, "end": f1b})
            if n["rcpt"][1] and n["rcpt"][1] > (f1b or ""):
                sch.append({"label": "2순위 접수", "start": n["rcpt"][1], "end": n["rcpt"][1]})
        where = e.get("announce_where") or "청약홈"
        sch.append({"label": "당첨자 발표", "start": n["announce"], "end": n["announce"], "note": f"{where}에서 확인"})
        if n["contract"][0]:
            sch.append({"label": "계약", "start": n["contract"][0], "end": n["contract"][1],
                        "note": "하루" if n["contract"][0] == n["contract"][1] else ""})
        sch.append({"label": "입주 예정", "month": n["move_in"]})
    for x in sch:
        if x.get("month") and "-" in x["month"]:
            x["month"] = month(x["month"])
    n["schedule"] = sch
    # 텍스트 채우기
    for f in ("take", "who", "receipt_note", "plan_note", "rent_note", "pre_note"):
        if n.get(f):
            n[f] = fill(n[f])
    n["faq"] = [[q, fill(a)] for q, a in e["faq"]]
    # 본문 '자주 묻는 질문'과 같은 내용을 FAQPage 구조화 데이터로 (2026-11-02 SEO 기획안)
    n["faq_ld"] = {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {
        "@type": "Answer", "text": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(a))).strip()}} for q, a in n["faq"]]}
    if n.get("gap"):
        n["gap"] = dict(n["gap"], text=fill(n["gap"]["text"]))
    n["price_label"] = e.get("price_label", "최고 분양가")
    return n


DATA_FETCHED = ""


KWDIR = DATA / "keywords"
SEO_GAPS = {}


def _ns(x):
    return re.sub(r"\s+", "", x).upper()


def seo_of(n):
    """site/data/keywords/{key}.json(네이버 검색량)으로 제목 단어·설명 끝·소제목을 고른다.
    페이지에 실제로 있는 내용의 단어만 쓰고, 검색은 많은데 페이지에 없는 주제는 SEO_GAPS에 남긴다."""
    f = KWDIR / f"{n['key']}.json"
    if not f.exists():
        return None
    k = json.loads(f.read_text())
    vol = {}
    for r in k.get("rows", []):
        vol[_ns(r["kw"])] = max(vol.get(_ns(r["kw"]), 0), r["total"])
    names = k.get("names") or [n.get("complex") or n["title"]]

    def v(word):
        return max([vol.get(_ns(f"{nm} {word}"), 0) for nm in names] or [0])

    has = {
        "분양가": not n["is_rental"] and bool(n.get("max_price") or n.get("price_text")),
        "청약 일정": True, "분양 일정": n["is_pre"],
        "경쟁률": bool(n.get("comp")), "당첨자 발표": not n["is_pre"] and bool(n.get("announce")),
        "평면도": bool(n["imgs"].get("plans")), "배치도": bool(n["imgs"].get("layouts")),
        "줍줍": n["kind"] == "mujeonwi", "무순위": n["kind"] == "mujeonwi",
        "보증금": n["is_rental"] and bool((n.get("rent_summary") or {}).get("deposit")),
        "월세": n["is_rental"] and bool((n.get("rent_summary") or {}).get("monthly")),
        "자격": True, "입주자격": n["is_rental"], "시세": bool(n.get("gap")),
        "모델하우스": bool(n.get("model_house")), "입주": True,
    }
    words = [w for w in has if has[w] and w not in ("자격", "입주") and v(w) >= 20]
    words.sort(key=lambda w: -v(w))
    if "줍줍" in words and "무순위" in words:
        words.remove("무순위" if v("줍줍") >= v("무순위") else "줍줍")
    gaps = [(f"{names[0]} {w}", v(w)) for w in has if not has[w] and v(w) >= 100]
    gaps += [(r["kw"], r["total"]) for r in k.get("related", [])[:5] if r["total"] >= 300 and _ns(names[0]) in _ns(r["kw"])]
    if gaps:
        SEO_GAPS[n["key"]] = gaps
    return {"vol": v, "words": words, "names": names, "has": has}


def kw_title(n, seo, required=None, default=()):
    base = n["title"]
    words = list(seo["words"]) if seo else []
    if "줍줍" in words and base.endswith("무순위"):
        base += "(줍줍)"
        words.remove("줍줍")
    words = [w for w in words if w not in base]
    if n["is_pre"]:
        words = ["예상 분양가" if w == "분양가" else w for w in words]
    pick = [required] if required else []
    for w in words + list(default):
        if len(pick) >= 2:
            break
        if w not in pick and w not in base and not (w == "청약 일정" and "분양 일정" in pick):
            pick.append(w)
    # H1도 같은 검색 문장으로 (2026-11-02 SEO 전략 v2 — 단지명 + 작은 글씨 검색어)
    n["h1_base"], n["h1_kw"] = base, "·".join(pick)
    return f"{base} {'·'.join(pick)} · 줍줍알람"


def brand_h2(n, h2):
    """우리만 있는 분석 칸의 소제목을 검색어가 들어간 이름으로 (2026-11-02 SEO 전략 v2).
    단지명은 '한눈에 보기'·'시세 비교'와 kw_h2가 고른 3개, 합쳐 5개까지만 (모든 소제목 반복은 스팸처럼 보임)."""
    nm = n.get("complex") or n["title"]
    h2.setdefault("dz", f"{nm} 한눈에 보기")
    h2.setdefault("take", "넣을 만할까? 줍줍알람 한마디")
    h2.setdefault("gap", f"{nm} {'임대료' if n['is_rental'] else '분양가'} vs 주변 시세")
    h2.setdefault("odds", "경쟁률 예상 — 얼마나 몰릴까요?")
    h2.setdefault("trap", "청약 전 주의점 — 이건 알고 넣으세요")
    if n["kind"] == "mujeonwi":
        h2.setdefault("elig", "무순위(줍줍) 신청 자격")
    h2.setdefault("loc", "위치·교통")
    return h2


def kw_h2(n, seo):
    """검색량이 있는 주제의 소제목 앞에 단지명을 붙인다 (최대 3개)."""
    h2 = {}
    nm = n.get("complex") or n["title"]
    if not seo:  # 키워드 파일이 없으면 검색이 가장 많은 두 주제(분양가·청약 일정)에만
        if not n["is_rental"] and not n["is_pre"]:
            h2["price"] = nm
        h2["sch"] = f"{nm} 청약 일정"
        return h2
    cand = [("sch", "청약 일정", "청약 일정"), ("price", "분양가", None), ("plan", "평면도", "평면도·면적"),
            ("comp", "경쟁률", "청약 경쟁률"), ("elig", "자격", "신청 자격"), ("layout", "배치도", "단지 배치도")]
    cand = [c for c in cand if seo["has"].get(c[1]) and seo["vol"](c[1]) >= 50]
    cand.sort(key=lambda c: -seo["vol"](c[1]))
    for sec, _, label in cand[:3]:
        h2[sec] = f"{nm} {label}" if label else nm
    # 검색량이 작아도 제목·H1에 쓴 두 주제(분양가·청약 일정)는 단지명으로 (2026-11-02 SEO 전략 v2)
    if len(h2) < 2 and not n["is_rental"] and not n["is_pre"]:
        h2.setdefault("price", nm)
    if len(h2) < 2:
        h2.setdefault("sch", f"{nm} 청약 일정")
    return h2


def status_of(n):
    t = TODAY.isoformat()
    if n.get("status_override"):
        return n["status_override"]
    if n.get("moved"):
        return "released"
    if n.get("is_pre"):
        return "pre"
    a, b = n["rcpt"]
    if t < a:
        return "upcoming"
    if t <= b:
        return "open"
    if n["announce"] and t < n["announce"]:
        return "waiting"
    return "announced"


def dday(n):
    a = dt.date.fromisoformat(n["rcpt"][0])
    return (a - TODAY).days


# ───────────────────────── 이미지 ─────────────────────────
def img_out(src_rel, dst, width, quality=78, force=False):
    from PIL import Image
    src = REPO / src_rel
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force and dst.stat().st_mtime >= src.stat().st_mtime:
        from PIL import Image as I
        with I.open(dst) as im:
            return im.size
    im = Image.open(src).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dst, "WEBP", quality=quality, method=6)
    return im.size


def og_from(src_rel, dst, pos=None):
    """공유 썸네일(1200×630) = 페이지 실사(photo)를 페이지 표지와 같은 구도(photo.pos 'center 40%')로 자름."""
    from PIL import Image
    src = REPO / src_rel
    tag = dst.with_suffix(".pos")
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and tag.exists() and tag.read_text() == str(pos):
        return
    im = Image.open(src).convert("RGB")
    W, H = 1200, 630
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    fy = 0.5
    m = re.search(r"(\d+(?:\.\d+)?)%\s*$", str(pos or ""))
    if m:
        fy = min(max(float(m.group(1)) / 100, 0), 1)
    x, y = (im.width - W) // 2, round((im.height - H) * fy)
    im.crop((x, y, x + W, y + H)).save(dst, "JPEG", quality=82, optimize=True, progressive=True)
    tag.write_text(str(pos))


def og_default(dst):
    if dst.exists():
        return
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#0F1E3D")
    dr = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(str(REPO / "fonts/Pretendard-Black.otf"), 150)
    f2 = ImageFont.truetype(str(REPO / "fonts/Pretendard-Bold.otf"), 44)
    dr.text((W // 2, 250), "줍줍알람", font=f1, fill="#FFFFFF", anchor="mm")
    dr.rounded_rectangle((W // 2 - 300, 370, W // 2 + 300, 450), radius=40, fill="#FF5233")
    dr.text((W // 2, 410), "청약 공고를 한눈에", font=f2, fill="#FFFFFF", anchor="mm")
    dr.text((W // 2, 540), "jupjupalarm.com", font=f2, fill="#AEB5C1", anchor="mm")
    im.save(dst, "JPEG", quality=85)


def won_band(v):
    """원 → 썸네일용 짧은 금액(내림 + '대'): 138,640 → '13만원대', 57,636,000 → '5천만원대', 143,600,000 → '1억4천만원대'."""
    v = int(v or 0)
    if v >= 100_000_000:
        e, c = divmod(v, 100_000_000)
        c //= 10_000_000
        exact = v % 10_000_000 == 0
        return f"{e}억{f'{c}천' if c else ''}만원{'' if exact else '대'}" if c else f"{e}억원{'' if v % 100_000_000 == 0 else '대'}"
    if v >= 10_000_000:
        return f"{v // 10_000_000}천만원{'' if v % 10_000_000 == 0 else '대'}"
    return f"{v // 10_000:,}만원{'' if v % 10_000 == 0 else '대'}"



# ── 판단형 공고 페이지 (2026-10-29 사용자 요청 "넣는 게 이득인지 판단할 수 없다") ──
# apt JSON의 "decide" 블록이 있으면: 3초 판단 카드 · 이런 분께 · 시세 막대 · 돈 흐름(계산기) · 경쟁 근거 · 다만 · 자가 체크
def won_about(v):
    """'약 1억7천만원' — 천만 단위 내림 (판단 카드용 어림값)."""
    v = int(v or 0)
    e, r = divmod(v, 10**8)
    c = r // 10**7
    if e:
        return f"약 {e}억{f'{c}천' if c else ''}만원" if c else f"약 {e}억원"
    if c:
        return f"약 {c}천만원"
    return f"약 {v // 10**4:,}만원"


def comp_refs(notices, kind="mujeonwi", days=45):
    """최근 접수 끝난 같은 유형 공고의 청약홈 공식 경쟁률 (줍줍알람이 모은 값)."""
    out = []
    for r in json.loads((DATA / "applyhome.json").read_text())["rows"]:
        c = parse_comp(r.get("경쟁률(청약홈 공식)") or "")
        if not c or not c["rows"]:
            continue
        if kind == "mujeonwi" and not re.search(r"무순위|임의공급", r.get("구분") or ""):
            continue
        end = r.get("접수 종료") or ""
        if not end or (TODAY - dt.date.fromisoformat(end)).days > days:
            continue
        sup = sum(x["supply"] for x in c["rows"])
        app = sum(x["apply"] for x in c["rows"])
        if not sup:
            continue
        page = next((n for n in notices if n["key"] == r["주택관리번호"]), None)
        loc = re.sub(r"^(서울|인천|경기)\S*\s+(\S+).*$", r"\1 \2", r.get("공급위치") or "")
        out.append({"name": re.sub(r"\(.*?\)", "", r["주택명"]).strip(), "loc": loc, "supply": sup, "apply": app,
                    "rate": app / sup, "end": end, "url": f"/apt/{page['key']}/" if page else None})
    out.sort(key=lambda x: x["end"], reverse=True)
    return out


def make_decide_rental(n, src):
    """임대 판단 카드: 월 부담 · 문턱 · 거주기간 · 입주 돈 (2026-10-29 시범: 화성 동탄 행복주택)."""
    ms = [m for m in n.get("rent_models") or [] if m.get("deposit")]
    rs = n.get("rent_summary") or {}
    rr = n.get("rent_range") or {}
    mon = [m["monthly"] for m in ms if m.get("monthly")] or ([rs["monthly"]] if rs.get("monthly") else []) or (list(rr.get("monthly") or []))
    dep = [m["deposit"] for m in ms] or ([rs["deposit"]] if rs.get("deposit") else []) or (list(rr.get("deposit") or []))
    cards, rule = [], []
    # ① 월 부담 — 비교 시세(gap) > 공고의 '시중시세 O% 수준' > 금액만
    gap = n.get("gap") or {}
    v = gap.get("verdict") or ""
    if mon:
        lo, hi = min(mon), max(mon)
        head = f"월 {won_band(lo)}" if lo == hi else f"월 {won_band(lo)}~{won_band(hi)}"
    else:
        head = "월 임대료 공고문 확인"
    m = re.search(r"주변 시세의 약 (\d+(?:\.\d+)?)% 수준", v)
    pm = re.search(r"(\d+(?:\.\d+)?)%", n.get("rent_level") or "")
    if m:
        pct = float(m.group(1))
        cards.append({"k": "월 부담", "sig": "g" if pct <= 60 else ("y" if pct <= 85 else "r"), "head": head, "sub": f"주변 시세의 약 {m.group(1)}% (추정)"})
    elif re.search(r"저렴\(추정\)$", v):
        cards.append({"k": "월 부담", "sig": "g", "head": head, "sub": "주변 시세보다 " + v[:-4].strip() + " (추정)"})
    elif pm:
        pct = float(pm.group(1))
        cards.append({"k": "월 부담", "sig": "g" if pct <= 60 else ("y" if pct <= 85 else "r"), "head": head, "sub": n["rent_level"] + " (공고 기준)"})
    else:
        cards.append({"k": "월 부담", "sig": "n", "head": head, "sub": "주변 시세와 비교는 확인 중이에요"})
    rule.append("월 부담: 주변 시세(또는 공고의 시중시세)의 60% 이하면 초록, 85% 이하면 노랑, 그보다 비싸면 빨강, 비교 전이면 회색")
    d = src.get("door") or {}
    if d.get("head"):
        cards.append({"k": "문턱", "sig": d.get("sig", "n"), "head": d["head"], "sub": d.get("sub", "")})
    rule.append("문턱: 무주택·계층 자격 말고 소득·자산 기준과 거주지역 제한이 없으면 초록, 하나 있으면 노랑, 둘 다 있으면 빨강")
    st = src.get("stay") or {}
    if st.get("head"):
        cards.append({"k": "거주기간", "sig": st.get("sig", "n"), "head": st["head"], "sub": st.get("sub", "")})
    rule.append("거주기간: 최장 10년 이상 살 수 있으면 초록, 4~9년이면 노랑, 그보다 짧으면 빨강")
    if dep:
        lo, hi = min(dep), max(dep)
        sig = "r" if hi >= 100_000_000 else ("y" if hi >= 30_000_000 else "g")
        cards.append({"k": "입주 돈", "sig": sig, "head": f"보증금 {won(lo)}" if lo == hi else f"보증금 {won(lo)[:-1]}~{won(hi)}",
                      "sub": src.get("dep_sub") or "블록·주택형·계층별로 달라요"})
    rule.append("입주 돈: 보증금이 1억원 이상이면 빨강, 3천만원 이상이면 노랑, 그보다 적으면 초록")
    conv = src.get("conv")
    opts = [[m["type"], m["deposit"], m.get("monthly") or 0] for m in ms]
    return {"rental": True, "cards": cards, "rule": rule, "fit": src.get("fit"),
            "traps": [[a, fill(b)] for a, b in src.get("traps", [])], "check": src.get("check"),
            "rent": {"opts": opts, "conv": conv, "note": fill(src.get("rent_note", "")), "basis": src.get("rent_basis", "")},
            "links": src.get("links") or []}


def make_decide(n, notices):
    src = n["decide"]
    if n.get("is_rental"):
        return make_decide_rental(n, src)
    rcpt = n.get("rcpt") or [None, None]
    one_day = bool(rcpt[0]) and (not rcpt[1] or rcpt[0] == rcpt[1])
    cards, rule = [], []
    # ① 이득 — gap 첫 줄(시세) vs 둘째 줄(분양가)
    gap = n.get("gap") or {}
    rows = gap.get("rows") or []
    mk = parse_won(rows[0][1]) if rows else None
    pr = parse_won(rows[1][1]) if len(rows) > 1 else None
    bars = None
    if mk and pr and re.search(r"저렴\(추정\)$", gap.get("verdict", "")):
        pct = round(pr * 100 / mk)
        sig = "g" if pct <= 70 else ("y" if pct <= 90 else "r")
        base = re.sub(r"\s*\(.*?\)\s*$", "", rows[0][0])
        cards.append({"k": "이득", "sig": sig, "head": "시세보다 " + gap["verdict"][:-4].strip(), "sub": f"주변 시세의 {pct}% 가격 · {base} 대비 (추정)"})
        bars = {"mk": rows[0], "pr": rows[1], "pct": pct}
    elif gap.get("verdict"):
        cards.append({"k": "이득", "sig": "r", "head": gap["verdict"], "sub": "근거는 아래 '시세와 비교하면'"})
    else:
        cards.append({"k": "이득", "sig": "n", "head": "비교 시세 확인 중", "sub": "근거 단지를 찾으면 채워요"})
    rule.append("이득: 분양가가 주변 시세의 70% 이하면 초록, 90% 이하면 노랑, 그보다 비싸거나 차익 기대가 낮으면 빨강")
    # ② 문턱 — 사람이 판정 (지역·소득·자산 조건 수)
    d = src.get("door") or {}
    if d.get("head"):
        cards.append({"k": "문턱", "sig": d.get("sig", "n"), "head": d["head"], "sub": d.get("sub", "")})
    rule.append("문턱: 청약통장·소득·거주지역 조건이 없으면 초록, 하나 있으면 노랑, 둘 이상이면 빨강")
    # ③ 경쟁 — 공급 세대 수 + 최근 같은 유형 경쟁률
    refs = comp_refs(notices, n["kind"]) if n["kind"] == "mujeonwi" else []
    rates = sorted(x["rate"] for x in refs)
    med = rates[len(rates) // 2] if rates else None
    u = n.get("units") or 0
    sig = "r" if u <= 5 else ("y" if u <= 30 else "g")
    head = f"{u:,}세대뿐" if u <= 30 else f"{u:,}세대"
    if one_day:
        head += " · 하루 접수"
    sub = f"최근 수도권 줍줍 {len(rates)}곳 경쟁률 가운데값 {med:.1f}대 1" if med is not None else (src.get("comp_sub") or "")
    cards.append({"k": "경쟁", "sig": sig, "head": head, "sub": sub})
    rule.append("경쟁: 공급이 5세대 이하면 빨강, 30세대 이하면 노랑, 그보다 많으면 초록")
    # ④ 자금 — 계약금
    f = src.get("funds") or {}
    price = n.get("max_price") or 0
    dep = f.get("deposit_pct")
    if price and dep:
        amt = price * dep // 100
        sig = "r" if amt >= 150_000_000 else ("y" if amt >= 50_000_000 else "g")
        rest = price - amt
        cards.append({"k": "자금", "sig": sig, "head": f"계약금 {won_about(amt)}", "sub": f"입주 전까지 {won_about(rest)} 더" + (f" · {f['card_tail']}" if f.get("card_tail") else "")})
    rule.append("자금: 계약 때 필요한 현금이 1억5천만원 이상이면 빨강, 5천만원 이상이면 노랑, 그보다 적으면 초록")
    # 돈 흐름
    opts = f.get("price_options") or ([[n.get("max_type") or "최고가", price]] if price else [])
    steps = [{"label": a, "when": fill(b), "pct": c} for a, b, c in f.get("steps", [])]
    out = {"cards": cards, "rule": rule, "bars": bars, "refs": refs[:10], "med": med,
           "fit": src.get("fit"), "traps": [[a, fill(b)] for a, b in src.get("traps", [])],
           "check": src.get("check"), "funds": {"opts": opts, "steps": steps, "dep": dep, "basis": f.get("basis", ""), "note": fill(f.get("note", ""))},
           "comp_note": fill(src.get("comp_note", ""))}
    return out


def og_price_label(n):
    """썸네일 가격 라벨: '최고 분양가' → '분양가' (사용자 요청 2026-10-29). 토지임대부 '최고 건물분양가' → '건물분양가'."""
    return re.sub(r"^최고\s*", "", n.get("price_label") or "분양가") or "분양가"


def gap_hook(n):
    """비교 단지 시세 차이 → (큰 줄, 작은 줄). 근거 단지가 있는 '저렴(추정)'·'O% 수준(추정)'만."""
    gap = n.get("gap") or {}
    v = (gap.get("verdict") or "").strip()
    base = re.sub(r"\s*\(.*?\)\s*$", "", (gap.get("rows") or [[""]])[0][0])
    if not base:
        return None
    if n.get("is_rental"):
        if re.fullmatch(r"(보증금|월세|전세|월 임대료) 약 .+ 저렴\(추정\)", v):
            big = "주변 시세보다 " + v[:-4].strip()       # '주변 시세보다 월세 약 32만원 저렴'
        elif re.fullmatch(r"주변 시세의 약 \d+(?:\.\d+)?% 수준\(추정\)", v):
            big = v[:-4].strip()                           # '주변 시세의 약 35% 수준'
        else:
            return None
    elif re.fullmatch(r"약 .+ 저렴\(추정\)", v):            # 토지임대부 '건물분양가 기준 …'은 제외 (단서가 썸네일에 안 들어감)
        big = "시세보다 " + v[:-4].strip()
    else:
        return None
    return big, f"(추정) {base} 대비"


def og_lines(n):
    """사진 없는 공고의 공유 카드 문구: (분류, 상태, 단지명, 지역, 큰 줄, 작은 줄)."""
    kind = n.get("kind_label") or KINDS.get(n["kind"], ("",))[0]
    st = STATUS.get(n["status"], ("", ""))[0]
    unit = f"{n['units']:,}{n.get('unit_word') or '세대'}" if n.get("units") else ""
    rcpt = n.get("rcpt") or [None, None]
    rng = (d(rcpt[0]) if not rcpt[1] or rcpt[0] == rcpt[1] else f"{d(rcpt[0])} ~ {d(rcpt[1])}") if rcpt[0] else ""
    rs = n.get("rent_summary") or {}
    big, small = "", ""
    if n.get("is_pre"):
        big = f"예상 {n.get('price_short') or n.get('price_text') or ''}".strip()
        small = f"{d(rcpt[0])} 접수 예정 · 보도 기준" if rcpt[0] else "보도 기준"
    elif n.get("is_rental"):
        if n.get("houses") and n.get("rent_level"):
            big = n["rent_level"]
        elif rs.get("deposit"):
            # 썸네일은 한눈에 — 원 단위까지 쓰지 않고 '대'로 (내림이라 사실과 어긋나지 않음)
            big = f"월 {won_band(rs['monthly'])} · 보증금 {won_band(rs['deposit'])}" if rs.get("monthly") else f"보증금 {won_band(rs['deposit'])}"
        else:
            big = unit
        small = " · ".join(x for x in (f"{rng} 접수" if rng and n["status"] in ("open", "upcoming") else "", unit if big != unit else "") if x)
    elif n["status"] in ("waiting", "announced"):
        comp = (n.get("comp") or {}).get("short")
        big = comp or (f"{og_price_label(n)} {won(n['max_price'])}" if n.get("max_price") else "")
        small = f"당첨자 발표 {d(n['announce'])}" if n.get("announce") else ""
    else:
        big = f"{og_price_label(n)} {won(n['max_price'])}" if n.get("max_price") else ""
        small = " · ".join(x for x in (f"{rng} 접수" if rng else "", unit) if x)
    loc = " ".join(x for x in (n.get("sido"), n.get("sigungu")) if x)
    head = None
    # 모든 공고(임대 포함)에 비교 단지 시세를 확보 (사용자 결정 2026-10-29) — 있으면 그 차이가 썸네일 주인공
    gh = gap_hook(n)
    if gh and n["kind"] != "mujeonwi" and n["status"] in ("open", "upcoming") and not n.get("is_pre"):
        big = gh[0]
        small = " · ".join(x for x in (gh[1], f"{rng} 접수" if rng else "") if x)
    # 줍줍(무순위·임의공급)은 분양가보다 '얼마나 싸게·언제까지'가 훅 (사용자 요청 2026-10-29, 마케터 관점)
    # 무엇인지(무순위 줍줍·임의공급 줍줍)는 항상 윗줄에 — 사용자 요청 "줍줍·분양·행복주택·매입임대처럼 어떤 건지 알려줘야"
    if n["kind"] == "mujeonwi":
        kind = f"{kind} 줍줍" if "줍줍" not in kind else kind
    if n["kind"] == "mujeonwi" and n["status"] in ("open", "upcoming") and not n.get("is_pre"):
        one_day = rcpt[0] and (not rcpt[1] or rcpt[0] == rcpt[1])
        when = f"{d(rcpt[0])} 하루 접수" if one_day else (f"{rng} 접수" if rng else "")
        bucket = next((c[0] for c in n.get("chips") or [] if re.fullmatch(r"\d+(?:\.\d+)?㎡ \d+억대", c[0])), "")
        city = loc.split(" ")[-1] if loc else ""
        gh = gap_hook(n)
        if gh:  # 근거 단지가 있는 차익만 (공고 페이지 gap과 같은 문장)
            big = gh[0]                                                  # '시세보다 약 10억9천만원 저렴'
            small = " · ".join(x for x in (gh[1], when) if x)            # 추정 표시는 바로 아래 줄에 항상
        else:
            big = bucket or big
            small = " · ".join(x for x in (when, unit) if x)
        head = f"{city} {kind}".strip()
    # ── 썸네일 = 훅만 (사용자 요청 2026-10-29 "핵심만, 정보 나열·의미 없는 문구 빼기") ──
    # 작은 줄은 쓰지 않는다: 비교 단지·(추정)·세대수 같은 근거는 공고 페이지 '시세와 비교하면'에서 (훅엔 꼬리표 없이 — ③ 규칙과 같음)
    small = ""
    # 발표 대기·발표 완료: '{단지명}' / '경쟁률 O대 1'
    if n["status"] in ("waiting", "announced") and not n.get("is_pre"):
        m = re.search(r"([\d.]+)대 1", (n.get("comp") or {}).get("short") or "")
        if m:
            big = f"경쟁률 {float(m.group(1)):.1f}".rstrip("0").rstrip(".") + "대 1"
            head = n.get("og_name") or re.sub(r"\s*(무순위|임의공급|잔여세대|줍줍)$", "", n["title"])  # 유형은 칩에
    # 상태 칩 = 급한 정도 (D-day·오늘 마감·하루 접수)
    if n["status"] in ("open", "upcoming") and rcpt[0] and not n.get("is_pre"):
        end = rcpt[1] or rcpt[0]
        one_day = not rcpt[1] or rcpt[0] == rcpt[1]
        if n["status"] == "open":
            left = (dt.date.fromisoformat(end) - TODAY).days
            st = "오늘 마감" if left <= 0 else (f"D-{left} 마감" if left <= 7 else "접수 중")
        else:
            left = (dt.date.fromisoformat(rcpt[0]) - TODAY).days
            st = f"D-{left}" if 0 < left <= 7 else f"{d(rcpt[0])} 접수"
            if one_day and 0 < left <= 7:
                st += " · 하루만 접수"
    return (kind, st, n["title"], loc, big, small) + ((head,) if head else ())


def og_make(n, dst, has_photo):
    """공유 썸네일 — site/og.py render() (시안 B·남색). 바뀐 게 없으면 다시 그리지 않음. 반환: 버전(내용 해시 8자)."""
    import og as OG
    lines = list(og_lines(n))
    ph = n.get("photo") if has_photo else None
    src = (REPO / ph["image"]) if ph else None
    key = json.dumps({"v": "B8-pretendard", "lines": lines, "photo": ph and [ph["image"], ph.get("pos"), ph.get("credit"), src.stat().st_mtime]}, ensure_ascii=False)
    ver = hashlib.sha1(key.encode()).hexdigest()[:8]
    tag = dst.with_suffix(".key")
    if dst.exists() and tag.exists() and tag.read_text(encoding="utf-8") == key:
        return ver
    im = OG.render(lines, ph, ph.get("credit") if ph else None)
    im.save(dst, "JPEG", quality=86, optimize=True, progressive=True)
    tag.write_text(key, encoding="utf-8")
    for old in (dst.with_suffix(".pos"),):
        if old.exists():
            old.unlink()
    return ver


HUB_OG_FILE = DATA / "hub_og.json"   # 허브별 고정 썸네일 사진 — 처음 고른 단지 사진을 계속 씀 (날마다 바뀌지 않게)


def og_hub(url, chip_t, l1, l2, small, pool):
    """목록·허브 페이지 고정 공유 썸네일 (2026-11-02 SEO 기획안 개선안 4). 날짜·건수 없는 문구만.
    사진은 그 허브 공고 중 단지 사진이 있는 것을 한 번 골라 hub_og.json에 고정. 반환: 이미지 주소(?v=)."""
    import og as OG
    fixed = json.loads(HUB_OG_FILE.read_text()) if HUB_OG_FILE.exists() else {}
    ph = fixed.get(url)
    if ph and not (REPO / ph["image"]).exists():
        ph = None
    if not ph:
        cand = sorted((x for x in pool if x.get("photo") and (REPO / x["photo"]["image"]).exists()), key=lambda x: x["key"])
        if cand:   # 허브마다 다른 사진이 되도록 주소로 고름 (한 번 정하면 고정)
            pick = cand[int(hashlib.sha1(url.encode()).hexdigest(), 16) % len(cand)]
            ph = {k: pick["photo"].get(k) for k in ("image", "pos", "credit")}
            fixed[url] = ph
            HUB_OG_FILE.write_text(json.dumps(fixed, ensure_ascii=False, indent=1, sort_keys=True))
    slug = re.sub(r"[^a-z0-9]+", "-", url.strip("/").lower()) or "home"
    dst = PUB / "og" / f"{slug}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    key = json.dumps({"v": "H2-pretendard", "t": [chip_t, l1, l2, small], "photo": ph}, ensure_ascii=False)
    ver = hashlib.sha1(key.encode()).hexdigest()[:8]
    OG.render_hub(chip_t, l1, l2, small, ph, ph.get("credit") if ph else None).save(dst, "JPEG", quality=84, optimize=True, progressive=True)
    return f"/og/{slug}.jpg?v={ver}"


def og_card(n, dst):
    """사진 없는 공고용 공유 썸네일 (1200×630, 남색 카드)."""
    from PIL import Image, ImageDraw, ImageFont
    lines = og_lines(n)
    tag = dst.with_suffix(".key")
    key = json.dumps(lines + ["font:pretendard"], ensure_ascii=False)
    if dst.exists() and tag.exists() and tag.read_text(encoding="utf-8") == key:
        return
    kind, st, title, loc, big, small = lines
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#0F1E3D")
    dr = ImageDraw.Draw(im)
    fh = lambda sz: ImageFont.truetype(str(REPO / "fonts/Pretendard-Black.otf"), sz)

    def fn(sz, bold=True):
        return ImageFont.truetype(str(REPO / ("fonts/Pretendard-Bold.otf" if bold else "fonts/Pretendard-Medium.otf")), sz)
    NOGLYPH = "·・‧∙•"  # Black Han Sans에 없는 글자는 Noto로

    def parts(t, f):
        out, cur, cf = [], "", None
        for ch in t:
            g = fn(f.size, True) if ch in NOGLYPH else f
            if cf is not None and (ch in NOGLYPH) != cf:
                out.append((cur, fn(f.size, True) if cf else f)); cur = ""
            cf = ch in NOGLYPH
            cur += ch
        if cur:
            out.append((cur, fn(f.size, True) if cf else f))
        return out

    def tlen(t, f):
        return sum(dr.textlength(x, font=g) for x, g in parts(t, f))

    def tdraw(x, y, t, f, fill):
        base = y + f.getmetrics()[0]  # 글꼴이 섞여도 같은 기준선에
        for seg, g in parts(t, f):
            dr.text((x, base), seg, font=g, fill=fill, anchor="ls")
            x += dr.textlength(seg, font=g)
    X = 80
    maxw = W - X - 70
    # 분류·상태 칩
    x, y = X, 60
    f = fn(30)
    for i, t in enumerate(c for c in (kind, st) if c):
        w = dr.textlength(t, font=f) + 44
        if i == 0:
            dr.rounded_rectangle((x, y, x + w, y + 54), 27, fill="#FF5233")
        else:
            dr.rounded_rectangle((x, y, x + w, y + 54), 27, outline="#AEB5C1", width=3)
        dr.text((x + 22, y + 27), t, font=f, fill="#FFFFFF", anchor="lm")
        x += w + 14
    # 아래쪽부터: 바닥글 → 작은 줄 → 큰 줄
    dr.text((X, H - 56), "줍줍알람 · jupjupalarm.com", font=fn(28), fill="#AEB5C1", anchor="lm")
    yb = H - 108
    if small:
        fs = fn(34, False)
        dr.text((X, yb), small, font=fs, fill="#FFFFFF", anchor="ls"); yb -= 56
    if big:
        fb = fn(52)
        while dr.textlength(big, font=fb) > maxw and fb.size > 34:
            fb = fn(fb.size - 4)
        dr.text((X, yb), big, font=fb, fill="#FFB4A3", anchor="ls"); yb -= fb.size + 26
    # 위쪽: 단지명(2줄까지, 넘치면 줄임) → 지역 — 큰 줄 위 공간 안에서
    room = yb - 140
    for sz in (84, 76, 68, 60, 54, 48):
        ft = fh(sz)
        rows, cur = [], ""
        for wd in title.split(" "):
            t2 = (cur + " " + wd).strip()
            if tlen(t2, ft) > maxw and cur:
                rows.append(cur); cur = wd
            else:
                cur = t2
        rows.append(cur)
        need = len(rows) * int(sz * 1.18) + (52 if loc else 0)
        if len(rows) <= 2 and all(tlen(r, ft) <= maxw for r in rows) and need <= room:
            break
    y = 140
    for r in rows[:2]:
        tdraw(X, y, r, ft, "#FFFFFF")
        y += int(sz * 1.18)
    if loc:
        dr.text((X, y + 4), loc, font=fn(32, False), fill="#AEB5C1")
    im.save(dst, "JPEG", quality=86, optimize=True)
    tag.write_text(key, encoding="utf-8")


def site_assets(n):
    """분양 홈페이지 자료 (photos/site/{key}/index.json — ① 조사 담당이 고른 것을 tools/site_photos.py로 받은 것, 2026-11-02).
    공고 json에 photo·plans·layouts가 없으면 여기서 채우고, 커뮤니티·인테리어·조감도는 '단지 둘러보기' 갤러리, E모델하우스·VR은 링크로."""
    f = REPO / "photos" / "site" / n["key"] / "index.json"
    if not f.exists():
        return None
    try:
        idx = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None
    ims = [im for im in idx.get("images", []) if (REPO / im["file"]).exists()]
    if not n.get("image_credit_owner"):
        n["image_credit_owner"] = idx.get("owner") or "분양 홈페이지"
    owner = n["image_credit_owner"]
    bird = [im for im in ims if im["cat"] == "birdseye"]
    if not n.get("photo"):
        big = next((im for im in bird if im["w"] >= 1000), None)
        if big:
            n["photo"] = {"image": big["file"], "credit": f"이미지: {owner} 조감도 · 실제와 다를 수 있음",
                          "alt": f"{n['title']} 조감도", "pos": "center 55%"}
    if not n.get("plans"):
        n["plans"] = [{"type": im["label"] or f"평면 {i}", "image": im["file"], "alt": f"{n['title']} {im['label']} 평면도"}
                      for i, im in enumerate((im for im in ims if im["cat"] == "plan"), 1)][:8]
    if not n.get("layouts"):
        lay = [im for im in ims if im["cat"] == "siteplan"][:2] + [im for im in ims if im["cat"] == "dongho"][:2]
        n["layouts"] = [{"kind": "동호배치도" if im["cat"] == "dongho" else "단지 배치도", "image": im["file"],
                         "alt": f"{n['title']} {'동호배치도' if im['cat'] == 'dongho' else '단지 배치도'}{(' ' + im['label']) if im['label'] else ''}"}
                        for im in lay]
    hero = (n.get("photo") or {}).get("image")
    gal = [im for im in bird if im["file"] != hero] + [im for im in ims if im["cat"] == "community"] + [im for im in ims if im["cat"] == "interior"]
    kind_ko = {"birdseye": "단지", "community": "커뮤니티", "interior": "인테리어"}
    n["gallery"] = [{"image": im["file"], "label": im["label"] or kind_ko[im["cat"]], "kind": kind_ko[im["cat"]],
                     "alt": f"{n['title']} {kind_ko[im['cat']]} {im['label']}".strip(), "photo": im.get("photo", True)} for im in gal[:8]]
    n["site_links"] = [l for l in idx.get("links", []) if l.get("kind") in ("emodel", "vr") and l.get("url", "").startswith("http")
                       and "youtube.com/embed" not in l["url"]][:3]
    return idx


def locmap(n, out):
    """네이버 지도가 없는 공고의 위치 지도 — 통계청 SGIS 2018 행정구역 경계(공공누리 1유형)로 오프라인 생성 (2026-11-03 사용자 결정: 이미지 없는 공고에도 그림 하나)."""
    try:
        sys.path.insert(0, str(REPO))
        import mapgen
    except Exception:
        return None
    addr = (n.get("address") or "").replace("(", " ").replace(")", " ")
    toks = addr.split()
    sgg = None
    big = ("광역시", "특별시", "특별자치시", "특별자치도", "도")
    for i in range(len(toks) - 1):
        if toks[i].endswith(("시", "특례시")) and not toks[i].endswith(big) and toks[i + 1].endswith("구"):
            sgg = f"{toks[i]} {toks[i + 1]}"
            break
    sgg = sgg or n.get("sigungu") or ""
    # 2018 경계 자료 기준 이름으로: '화성특례시' → '화성시', 2026 인천 서구 분구(서해구·검단구) → '서구'
    sgg = sgg.replace("특례시", "시")
    if n.get("sido") == "인천" and sgg in ("서해구", "검단구"):
        sgg = "서구"
    dong = next((t for t in toks if re.fullmatch(r"[가-힣]+\d*(동|읍|면)", t) and not t.endswith("지구")), None)
    if not sgg:
        return None
    try:
        svg, info = mapgen.make_map(sgg, dong, n.get("sido"), width=780, height=440, accent="#FF5233", tint="#FFE3D9",
                                    label_dong=dong)
        if not svg and " " in sgg:
            svg, info = mapgen.make_map(sgg.split()[0], None, n.get("sido"), width=780, height=440, accent="#FF5233", tint="#FFE3D9")
    except Exception as e:
        print("위치 지도 실패", n["key"], e, file=sys.stderr)
        return None
    if not svg:
        return None
    out.mkdir(parents=True, exist_ok=True)
    (out / "locmap.svg").write_text(svg)
    return {"src": "locmap.svg", "w": 780, "h": 440, "area": f"{n.get('sido', '')} {sgg}" + (f" {dong}" if dong and info.get("found_dong") else "")}


def lead_of(n):
    if n.get("is_pre") or n.get("moved") or not n.get("rcpt") or not n["rcpt"][0]:
        return ""
    a, b = n["rcpt"]
    parts = []
    if n.get("units"):
        parts.append(f"{n['units']:,}{n.get('unit_word') or '세대'} 모집")
    rng = d(a) if (not b or a == b) else f"{d(a)}~{d(b)}"
    s = f"{rng} 접수"
    if n.get("is_rental"):
        rs = n.get("rent_summary") or {}
        if rs.get("deposit"):
            s += f", 보증금 {money(rs['deposit'])}" + (f"·월 {money(rs['monthly'])}" if rs.get("monthly") else "") + (f"({rs['basis']})" if rs.get("basis") else "")
    elif n.get("max_price"):
        s += f", {n.get('price_label') or '최고 분양가'} {won(n['max_price'])}" + (f"({n['max_type']})" if n.get("max_type") else "")
    if n.get("announce"):
        s += f", 당첨자 발표 {d(n['announce'])}"
    parts.append(s)
    return ". ".join(parts) + "."


def notice_images(n):
    out = PUB / "apt" / n["key"]
    imgs = {}
    site_assets(n)
    if n.get("photo"):
        sz = img_out(n["photo"]["image"], out / "hero.webp", 960)
        if sz:
            imgs["hero"] = {"src": "hero.webp", "w": sz[0], "h": sz[1]}
    if n.get("map"):
        sz = img_out(n["map"], out / "map.webp", 960)
        if sz:
            imgs["map"] = {"src": "map.webp", "w": sz[0], "h": sz[1]}
    if "map" not in imgs and not n.get("houses"):
        lm = locmap(n, out)
        if lm:
            imgs["locmap"] = lm
    plans = []
    for p in n.get("plans", []):
        slug = re.sub(r"[^a-z0-9]+", "-", p["type"].lower()).strip("-")
        sz = img_out(p["image"], out / f"plan-{slug}.webp", 1200, 80)
        if sz:
            plans.append(dict(p, src=f"plan-{slug}.webp", w=sz[0], h=sz[1], slug=slug))
    imgs["plans"] = plans
    lays = []
    for i, p in enumerate(n.get("layouts", []), 1):
        sz = img_out(p["image"], out / f"layout-{i}.webp", 1200, 80)
        if sz:
            lays.append(dict(p, src=f"layout-{i}.webp", w=sz[0], h=sz[1]))
    imgs["layouts"] = lays
    gal = []
    for i, p in enumerate(n.get("gallery", []), 1):
        sz = img_out(p["image"], out / f"tour-{i}.webp", 1200, 80)
        if sz:
            gal.append(dict(p, src=f"tour-{i}.webp", w=sz[0], h=sz[1]))
    imgs["gallery"] = gal
    og_ver = ""
    try:
        out.mkdir(parents=True, exist_ok=True)
        og_ver = og_make(n, out / "og.jpg", "hero" in imgs)
    except Exception as e:  # 글꼴 문제 등 — 기본 이미지로
        print("og 썸네일 실패", n["key"], e, file=sys.stderr)
    # ?v= : 카카오톡 등은 같은 주소의 썸네일을 오래 기억해서, 내용이 바뀌면 주소를 바꿔 새로 읽게 함
    imgs["og"] = f"/apt/{n['key']}/og.jpg?v={og_ver}" if (out / "og.jpg").exists() and og_ver else "/og-default.jpg"
    return imgs


# ───────────────────────── 렌더링 ─────────────────────────
def env():
    e = Environment(loader=FileSystemLoader(SITE / "templates"), autoescape=select_autoescape(["html", "xml"]),
                    trim_blocks=True, lstrip_blocks=True)
    e.filters.update(sd=sd, h2s=h2s, combine=lambda a, b: {**a, **b}, money=money, mrange=lambda r: f"{money(r[0])[:-1]}~{money(r[1])}" if r and r[0] != r[1] else money(r[0]) if r else '', d=d, drange=drange, won=won, py=py, m2=m2, tdate=tdate, tlwhen=tlwhen, trange=trange, tmonth=tmonth,
                     jsonld=lambda o: Markup(json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")))
    def crumb_ld(items, last, page_url):
        el = [{"@type": "ListItem", "name": lab, "item": BASE + u} for lab, u in items if u]
        el.append({"@type": "ListItem", "name": last})
        for i, x in enumerate(el, 1):
            x["position"] = i
        return {"@type": "BreadcrumbList", "itemListElement": el}
    def items_ld(items):
        return [{"@type": "ListItem", "position": i, "url": BASE + n["url"], "name": n["title"]} for i, n in enumerate(items, 1)]
    e.globals.update(HAS_GUIDES=bool(GUIDES.load()), RENTAL_EXPLAIN=RENTAL_EXPLAIN, BASE=BASE, IG=IG, THREADS=THREADS, BLOG=BLOG, YOUTUBE=YOUTUBE, COUPANG=COUPANG, COUPANG_NOTE=COUPANG_NOTE, ADSENSE=ADSENSE, GA=GA, STATUS=STATUS, KINDS=KINDS, crumb_ld=crumb_ld, items_ld=items_ld,
                     logo=Markup((SITE / "static/favicon.svg").read_text().replace('<svg xmlns="http://www.w3.org/2000/svg" ', '<svg class="mark" aria-hidden="true" focusable="false" ')))
    return e


PAGES = {}  # url → dict(title, desc, html)


# ── 검색어 허브용 표 (2026-11-02 SEO 전략 v2)
def mk_table(cap, head, rows, left=2, txt=False):
    """head: 열 이름들, rows: [[셀…]] — 첫 칸은 행 머리(th). 셀이 Markup이면 그대로, 문자열이면 escape."""
    def c(v):
        return v if isinstance(v, Markup) else html.escape(str(v))
    LS, LC = ' style="text-align:left"', ' class="l"'
    th = "".join(f'<th scope="col"{LS if i < left else ""}>{c(h)}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join((f'<th scope="row">{c(v)}</th>' if i == 0 else f'<td{LC if i < left else ""}>{c(v)}</td>')
                                    for i, v in enumerate(r)) + "</tr>" for r in rows)
    return Markup(f'<div class="tbl ntbl{" txt" if txt else ""}"><table class="num"><caption>{c(cap)}</caption><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>')


def alink(n):
    return Markup(f'<a href="{n["url"]}">{html.escape(n["title"])}</a>')


def gap_won(v):
    """'약 12억9천만원 저렴(추정)' → 1,290,000,000 (정렬용)"""
    t = 0
    for num, unit in re.findall(r"(\d[\d,]*)\s*(억|천|백|만)", v or ""):
        t += int(num.replace(",", "")) * {"억": 10**8, "천": 10**7, "백": 10**6, "만": 10**4}[unit]
    return t


def comp_table(rows, cap):
    return mk_table(cap, ["단지", "지역", "접수 마감", "공급", "접수", "평균 경쟁률", "최고 경쟁률"],
                    [[alink(r["n"]), f"{r['n']['sido']} {r['n']['sigungu'] or ''}", tdate(r["n"]["rcpt"][1]), r["supply"], r["apply"], r["avg"], r["top"]] for r in rows])


def mu_sections(crow_mu):
    """줍줍 허브 본문 — 자격 요약(가이드 facts와 같은 근거) + 최근 경쟁률 (청약로그ON 무순위 허브 구성 참고)"""
    rule = mk_table("무순위(줍줍) 신청 자격 — 주택공급에 관한 규칙 2026.6.15 시행본 기준", ["항목", "내용", "근거"], [
        ["청약통장", "필요 없어요", "규칙 제26조 제5항 단서·제47조의3 (통장 요건 없음)"],
        ["주택 소유", "무주택세대구성원 (세대원 전원 무주택, 분양권·입주권도 주택으로 셈)", "제26조 제5항 단서 제1호 · 2025.6.10 시행"],
        ["거주지역", "시장·군수·구청장이 필요하면 추가 — 해당 지역 또는 광역권(수도권 등). 공고마다 달라요", "제26조 제5항 제2호"],
        ["뽑는 방법", "추첨 (가점·순위 없음)", "제19조 제5항"],
        ["당첨 뒤", "계약하지 않아도 당첨자로 관리돼 재당첨 제한이 붙을 수 있어요. 계약금은 며칠 안에", "공고문 확인"],
    ], left=3, txt=True)
    out = [{"h2": "무순위(줍줍) 청약 신청 자격", "small": "한눈에",
            "html": rule + Markup('<p class="tbl-more"><a href="/guide/mujeonwi/">무순위 청약 조건·신청 방법 총정리 →</a></p>')}]
    if crow_mu:
        out.append({"h2": "최근 줍줍 경쟁률", "small": f"{len(crow_mu[:10])}곳",
                    "html": comp_table(crow_mu[:10], f"최근 접수가 끝난 무순위·임의공급 {len(crow_mu[:10])}곳 — 청약홈 공식 경쟁률")
                    + Markup('<p class="tbl-more"><a href="/competition/">청약 경쟁률 전체 보기 →</a></p>')})
    return out


# ── 허브·홈의 고정 제목·설명 (2026-11-04 사용자 결정 — 네이버 웹마스터 가이드: 메인 title·description을 자주 바꾸거나
#    80자 넘게 길면 불이익. 날짜·곳 수 같은 매일 바뀌는 숫자는 본문에만 두고, 제목·설명은 브랜드 문구로 고정) ──
HOME_TITLE = "줍줍알람 - 놓치기 쉬운 청약 공고 알림"
HOME_DESC = "줍줍(무순위)부터 공공분양·임대까지, 청약 공고의 일정·분양가·자격을 공식 데이터로 쉽게 정리해요."
FIXED_META = {
    "/type/": ("유형별 청약 공고 — 줍줍·분양·임대", "무순위(줍줍), 민간분양, 공공분양, 신혼희망타운, 공공임대 공고를 유형별로 모아 접수 일정과 자격을 정리해요."),
    "/type/mujeonwi/": ("줍줍·무순위 청약 공고 — 접수일·분양가·자격", "청약통장 없이 추첨으로 뽑는 줍줍(무순위)·임의공급 공고를 모아 접수일, 분양가, 신청 자격을 정리해요."),
    "/type/private/": ("민간분양 청약 일정 — 아파트 분양 공고 모음", "민간 건설사 아파트 분양 공고의 접수일, 분양가, 가점·추첨 비율과 자격을 청약홈 공식 데이터로 정리해요."),
    "/type/public/": ("공공분양 청약 일정 — LH·SH·GH 분양 공고", "LH·SH·GH 공공분양과 토지임대부 공고의 접수일, 분양가, 소득·자산 기준을 공식 데이터로 정리해요."),
    "/type/newlywed/": ("신혼희망타운 청약 일정 — 공고 모음", "신혼부부·예비신혼부부·한부모가족 대상 신혼희망타운 공고의 접수일, 분양가, 소득·자산 기준을 정리해요."),
    "/type/rental/": ("행복주택·공공임대 모집 공고 — 보증금·월세·자격", "LH·SH·GH 행복주택, 국민임대, 매입임대, 전세임대 모집 공고의 보증금·월세와 신청 자격을 정리해요."),
    "/region/": ("지역별 청약 공고 — 서울·경기·인천", "서울·경기·인천 시군구별 청약 공고를 모아 접수 일정, 분양가, 자격을 한눈에 볼 수 있게 정리해요."),
    "/region/seoul/mujeonwi/": ("서울 줍줍·무순위 청약 — 공고 모음", "서울 무순위(줍줍)·임의공급 공고의 접수일, 분양가, 자격과 청약홈 공식 경쟁률을 한 페이지에 모았어요."),
    "/region/gyeonggi/dongtan/": ("동탄 청약 일정 — 아파트 분양·임대", "화성 동탄 일대 아파트 분양과 행복주택 공고의 접수일, 분양가, 보증금과 자격을 정리해요."),
    "/competition/": ("청약 경쟁률 — 청약홈 공식 경쟁률 모음", "최근 접수가 끝난 아파트 분양·무순위(줍줍) 단지의 청약홈 공식 경쟁률을 공급·접수 건수와 함께 정리해요."),
    "/lotto/": ("로또 청약 — 시세보다 싸게 나온 공고", "주변 실거래보다 분양가가 낮게 나온 청약 공고를 비교 단지, 거래 시점과 함께 모았어요. 금액은 추정이에요."),
    "/schedule/this-week/": ("이번 주 청약 일정 — 아파트 분양·줍줍", "이번 주와 다음 주에 접수하는 아파트 분양, 줍줍(무순위), 공공분양, 임대 공고를 날짜순으로 정리해요."),
}


def fixed_meta(url, html_text):
    """허브 주소면 (제목, 설명) 고정값, 아니면 None. 지역·월별 허브는 이름만 넣는 틀."""
    if url == "/":
        return HOME_TITLE, HOME_DESC
    if url in FIXED_META:
        t, d_ = FIXED_META[url]
        return f"{t} · 줍줍알람", d_
    m = re.fullmatch(r"/schedule/(\d{4})-(\d{2})/", url)
    if m:
        ym = f"{m.group(1)}년 {int(m.group(2))}월"
        return (f"{ym} 청약 일정 — 아파트 분양·줍줍·임대 · 줍줍알람",
                f"{ym}에 접수하는 아파트 분양, 줍줍(무순위), 임대 공고의 접수일과 분양가를 날짜순으로 정리해요.")
    m = re.fullmatch(r"/region/[a-z-]+/(?:[a-z-]+/)?", url)
    if m:
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
        place = re.sub(r"<[^>]+>", " ", h1.group(1)) if h1 else ""
        place = re.split(r"\s*청약", html.unescape(re.sub(r"\s+", " ", place)).strip())[0].strip()
        if place:
            return (f"{place} 청약 일정 — 아파트 분양·줍줍 공고 · 줍줍알람",
                    f"{place} 아파트 분양, 줍줍(무순위), 공공분양, 임대 공고의 접수일과 분양가, 자격을 날짜순으로 정리해요.")
    return None


def _set_meta(h, title, desc):
    e = lambda x: html.escape(x, quote=True)
    h = re.sub(r"<title>.*?</title>", lambda _: f"<title>{e(title)}</title>", h, count=1, flags=re.S)
    h = re.sub(r'<meta name="description" content="[^"]*">', lambda _: f'<meta name="description" content="{e(desc)}">', h, count=1)
    h = re.sub(r'<meta property="og:title" content="[^"]*">', lambda _: f'<meta property="og:title" content="{e(title.replace(" · 줍줍알람", ""))}">', h, count=1)
    h = re.sub(r'<meta property="og:description" content="[^"]*">', lambda _: f'<meta property="og:description" content="{e(desc)}">', h, count=1)
    if '<meta name="description"' not in h:
        h = h.replace("</title>", f'</title>\n<meta name="description" content="{e(desc)}">\n<meta property="og:description" content="{e(desc)}">', 1)
    return h


def write(url, html_text, title, desc, kind, lastmod=None, index=True):
    fm = fixed_meta(url, html_text) if kind == "list" or url == "/" else None
    if fm:
        title, desc = fm
        html_text = _set_meta(html_text, title, desc)
    PAGES[url] = {"title": title, "desc": desc, "kind": kind, "lastmod": lastmod, "index": index, "html": html_text}
    p = PUB / url.lstrip("/") / "index.html" if url.endswith("/") else PUB / url.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_text)


def content_hash(n):
    skip = {"fetched_at"}
    keep = {k: v for k, v in n.items() if k not in skip}
    return hashlib.sha1(json.dumps(keep, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def card(n):
    return n  # 템플릿 매크로가 그대로 씀


def main():
    global TODAY, DATA_FETCHED
    ap = argparse.ArgumentParser()
    ap.add_argument("--today")
    ap.add_argument("--no-state", action="store_true", help="state.json을 고치지 않음 (미리보기용)")
    a = ap.parse_args()
    now = dt.datetime.now(KST)
    TODAY = dt.date.fromisoformat(a.today) if a.today else now.date()
    DATA_FETCHED = json.loads((DATA / "applyhome.json").read_text()).get("fetched_at", "")

    items, regions, state = load()
    problems = []
    notices = []
    for e, row in items:
        n = build_notice(e, row, regions, problems)
        if n:
            notices.append(n)
    byk = {n["key"]: n for n in notices}
    # 공고 전 페이지에 공고가 나오면: 페이지는 그대로 두고(검색 순위 유지) 새 공고로 안내 + 예상 vs 실제 비교
    for n in notices:
        t = byk.get(n.get("moved_to") or "")
        if n.get("is_pre") and t:
            n["moved"] = t
            t["pre_page"] = n

    # 상태·지문·공개일
    for n in notices:
        n["status"] = status_of(n)
        n["dday"] = dday(n)
        h = content_hash({k: v for k, v in n.items() if k not in ("status", "dday", "moved", "pre_page")}
                         | {"_moved": (n.get("moved") or {}).get("key"), "_pre": (n.get("pre_page") or {}).get("key")})
        st = state.get(n["key"], {})
        if st.get("hash") != h:
            st["modified"] = now.isoformat(timespec="seconds")
            st["hash"] = h
        st.setdefault("published", now.isoformat(timespec="seconds"))
        state[n["key"]] = st
        n["published"], n["modified"] = st["published"], st["modified"]

    for n in notices:
        if n.get("decide"):
            n["dz"] = make_decide(n, notices)

    # 출력 폴더 정리 (이미지는 남겨 재사용)
    PUB.mkdir(exist_ok=True)
    for p in PUB.iterdir():
        if p.name == "apt":
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    css_hash = None
    for f in (SITE / "static").iterdir():
        if f.is_dir():
            shutil.copytree(f, PUB / f.name)
            continue
        if f.name == "style.css":
            css_hash = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
            shutil.copy2(f, PUB / f"style.{css_hash}.css")
        else:
            shutil.copy2(f, PUB / f.name)
    og_default(PUB / "og-default.jpg")

    E = env()
    order = {"open": 0, "upcoming": 1, "pre": 2, "waiting": 3, "announced": 4, "released": 5}

    def sort_key(n):
        return (order[n["status"]], n["rcpt"][0] if n["status"] in ("open", "upcoming") else "~" + n["announce"], n["title"])

    def sorted_n(lst):
        lst = sorted(lst, key=sort_key)
        ann = [n for n in lst if n["status"] == "announced"]
        ann.sort(key=lambda n: n["announce"], reverse=True)
        return [n for n in lst if n["status"] != "announced"] + ann

    common = dict(today=TODAY, built=now, css=f"/style.{css_hash}.css", kinds_used=sorted({n["kind"] for n in notices}, key=list(KINDS).index))

    # 지역 목록 구성
    sido_map = {}
    for n in notices:
        for sd in ([n["sido"]] + [x for x in n.get("house_sidos", []) if x != n["sido"]]):
            sido_map.setdefault(sd, []).append(n)
    sgg_pages = {}
    for n in notices:
        if n["sgg_slug"]:
            sgg_pages.setdefault((n["sido"], n["sigungu"]), []).append(n)
    sgg_pages = {k: v for k, v in sgg_pages.items() if len(v) >= 3}

    def crumb_for(n):
        c = [("홈", "/"), (n["sido"], f"/region/{n['sido_slug']}/")]
        if n["sigungu"]:
            u = f"/region/{n['sido_slug']}/{n['sgg_slug']}/" if (n["sido"], n["sigungu"]) in sgg_pages else None
            c.append((n["sigungu"], u))
        return c

    # ── 공고 페이지
    apt_tpl = E.get_template("apt.html")
    gmeta = GUIDES.load()

    def guide_for(n):
        for g in gmeta:
            if n["kind"] in (g.get("notice_kinds") or []):
                mt = g.get("notice_match") or []
                if not mt or any(w in n["title"] + (n.get("kind_label") or "") + (n.get("rental_type") or "") for w in mt):
                    return {"url": f"/guide/{g['slug']}/", "h1": g["h1"]}
        return None

    # 공고 상세 '신청 전에 읽어볼 가이드' (사용자 요청 2026-10-29) — 이름이 맞는 칼럼(notice_match) → 공고 유형별 기본 칼럼 순, 있는 글만 최대 3편
    KIND_GUIDES = {
        "mujeonwi": ["mujeonwi", "homeless-criteria", "after-winning-money", "dsr-ltv-dti"],
        "private": ["cheongyak-gajeom", "first-priority", "dsr-ltv-dti", "after-winning-money"],
        "public": ["homeless-criteria", "didimdol-bogeumjari", "cheongyak-gajeom", "newborn-loan"],
        "newlywed": ["newlywed", "newborn-loan", "didimdol-bogeumjari", "homeless-criteria"],
        "rental": ["lh-rental-types", "homeless-criteria", "youth-jeonse-loan"],  # 행복주택·청년·국민임대·매입임대 칼럼은 notice_match로 붙음
    }
    gby = {g["slug"]: g for g in gmeta}

    def guides_for(n):
        text = n["title"] + (n.get("kind_label") or "") + (n.get("rental_type") or "") + " ".join(n.get("aliases") or []) + (n.get("sigungu") or "")
        picks = [g["slug"] for g in gmeta if g.get("notice_match") and (not g.get("notice_kinds") or n["kind"] in g["notice_kinds"])
                 and any(w in text for w in g["notice_match"])]
        picks += [s for s in KIND_GUIDES.get(n["kind"], []) if s in gby]
        out, seen = [], set()
        for s in picks:
            if s in seen:
                continue
            seen.add(s)
            g = gby[s]
            out.append({"url": f"/guide/{s}/", "h1": g["h1"], "category": g.get("category", ""), "read_min": GUIDES.read_min(g)})
        return out[:4]

    for n in notices:
        n["imgs"] = notice_images(n)
        same = [x for x in notices if x is not n and x["sido"] == n["sido"] and x["status"] in ("open", "upcoming")]
        same_kind = [x for x in notices if x is not n and x["kind"] == n["kind"] and x not in same and x["status"] in ("open", "upcoming")]
        extra = [byk[k] for k in n.get("related_extra", []) if k in byk]
        rel = extra + [x for x in sorted_n(same) + sorted_n(same_kind) if x not in extra]
        n["related"] = rel[:4]
        n["related_title"] = f"{n['sido']}에서 곧 접수하는 공고" if same else "함께 볼 공고"
        # 첫 문단: 검색자가 찾는 답(세대·접수·가격·발표)을 먼저 한 문장으로 (2026-11-03 리디자인 v2 — SEO 우선)
        n["lead"] = lead_of(n)
        # 한마디: 결론 한 문장 + 나머지는 '왜 그런지 보기'로 접음 (2026-11-03 사용자 결정 — 읽기 쉬운 구조)
        tk = (n.get("take") or "").strip()
        m_ = re.search(r"(?<=[.!?])\s+", tk)
        n["take_head"], n["take_rest"] = (tk[:m_.start()], tk[m_.end():]) if m_ and m_.start() >= 20 else (tk, "")
        # 첫 화면 '다음 할 일' (2026-11-03 사용자 결정 — 접수 끝난 공고로 들어온 사람을 지금 넣을 수 있는 공고로)
        n["next_alts"] = []
        if n["status"] in ("waiting", "announced"):
            for x in rel[:2]:
                if x["status"] == "open":
                    tag = "오늘 마감" if x["rcpt"][1] == TODAY.isoformat() else f"마감 {d(x['rcpt'][1])}"
                else:
                    tag = f"D-{dday(x)}"
                n["next_alts"].append({"url": x["url"], "title": x["title"], "tag": tag})
        st = n["status"]
        typ = n["kind_label"]
        seo = seo_of(n)
        n["h2"] = brand_h2(n, kw_h2(n, seo))
        if n.get("moved"):
            title = f"{n['title']} 예상 vs 실제 분양가 — 공고 전 전망 정리 · 줍줍알람"
            n["h1_base"], n["h1_kw"] = n["title"], "예상 vs 실제 분양가"
        elif n["is_pre"]:
            title = kw_title(n, seo, None, ("분양 일정", "예상 분양가"))
        elif n["is_rental"]:
            title = kw_title(n, seo, None, ("보증금", "월세", "자격"))
        elif st == "announced" or (st == "waiting" and n["comp"]):
            title = kw_title(n, seo, "경쟁률", ("당첨자 발표",))
        else:
            title = kw_title(n, seo, None, ("분양가", "청약 일정"))
        rc = drange(*n["rcpt"])
        rs = n.get("rent_summary") or {}
        if n.get("moved"):
            m = n["moved"]
            desc = f"공고 전 예상 {n.get('price_short') or n['price_text']} → 실제 최고 {won(m['max_price']) if m.get('max_price') else '공고문 확인'}. 보도로 알려진 전망과 실제 입주자모집공고를 비교하고, 확정 일정·분양가 페이지로 안내해요."
        elif n["is_pre"]:
            desc = f"{n['units']:,}세대 · 예상 분양가 {n['price_text']} · 청약 접수 {d(n['rcpt'][0])} 전망(보도 기준). 공고 전 단지의 일정·분양가 전망·시세 비교를 정리. 공고가 나오면 공식 값으로 바꿔요."
        elif n["is_rental"] and n["houses"]:
            rr = n.get("rent_range") or {}
            cond = n.get("rent_level") or ""
            if rr.get("deposit"):
                cond += f" · 보증금 {money(rr['deposit'][0])[:-1]}~{money(rr['deposit'][1])} · 월 {money(rr['monthly'][0])[:-1]}~{money(rr['monthly'][1])}"
            sgs = "·".join(g for g, _ in n["house_groups"][:4])
            desc = f"{n['units']}호({sgs}) · {cond} · 접수 {rc} {n.get('receipt_note') or ''}. 주택 목록·면적·자격·신청 방법을 한 번에."
        elif n["is_rental"]:
            cond = (f"보증금 {money(rs['deposit'])}" + (f" · 월 {money(rs['monthly'])}" if rs.get("monthly") else "")) if rs.get("deposit") else f"주택형 {len(n['rent_models'])}개"
            ucnt = f" · {n['units']:,}{n['unit_word']}" if n["units"] else ""
            desc = f"접수 {rc} · {cond}{ucnt} · {n.get('target') or n['kind_label']}. 신청 자격·일정과 공식 공고 링크를 한 번에."
        elif n["comp"] and n["comp"]["rows"]:
            best = max(n["comp"]["rows"], key=lambda r: r["apply"] / max(r["supply"], 1))
            desc = f"{n['comp']['summary'] or ''} · 당첨자 발표 {d(n['announce'])} · {n['price_label']} {won(n['max_price'])}. 일정·분양가·자격과 공식 공고 링크를 한 번에."
        else:
            desc = f"접수 {rc} · {n['max_type']} {n['price_label']} {won(n['max_price'])} · {n['units']:,}세대 · {typ}. 일정·분양가·자격과 공식 공고 링크를 한 번에."
        if seo and seo["words"] and not n.get("moved"):
            tail = "·".join(seo["words"][:3])
            desc = re.sub(r"(일정·분양가·자격과 공식 공고 링크를 한 번에|신청 자격·일정과 공식 공고 링크를 한 번에|주택 목록·면적·자격·신청 방법을 한 번에)\.$",
                          f"{n.get('complex') or n['title']} {tail}까지 공식 공고 기준으로 정리.", desc)
        n["page_title"], n["desc"] = title, desc
        gl = guides_for(n)  # 가장 맞는 칼럼은 신청 자격 아래 '처음이라면' 링크, 나머지는 FAQ 뒤 가이드 섹션
        n["guide_link"] = gl[0] if gl else guide_for(n)
        n["guides"] = gl[1:4]
        n["crumb"] = crumb_for(n)
        h = apt_tpl.render(n=n, **common, page_url=n["url"], title=title, desc=desc, og=n["imgs"]["og"])
        h = chipnav(h, n)
        write(n["url"], h, title, desc, "apt", n["modified"])

    # ── 목록 공통
    list_tpl = E.get_template("list.html")

    def hub_lead(groups_, order_):
        """허브 첫 문단: 오늘 기준 묶음별 접수 중·예정 수 (2026-11-04 허브 보강 — 구글이 먼저 읽은 허브가 목록뿐이라 부실)."""
        act = [(k, len([x for x in groups_[k] if x["status"] in ("open", "upcoming")])) for k in order_ if k in groups_]
        tot = sum(len(groups_[k]) for k in order_ if k in groups_)
        live_ = sum(a for _, a in act)
        parts = ", ".join(f"{k} {a}곳" for k, a in act if a)
        return (f"{d(TODAY.isoformat())} 기준 청약 공고 {tot}곳 중 지금 접수 중이거나 곧 접수하는 공고는 {live_}곳이에요"
                + (f" ({parts})" if parts else "") + ". 묶음마다 마감이 가까운 공고부터 3곳씩 보여드려요.")

    def hub_desc(prefix, groups_, order_):
        act = [(k, len([x for x in groups_[k] if x["status"] in ("open", "upcoming")])) for k in order_ if k in groups_]
        return (f"{d(TODAY.isoformat())} 기준 {prefix} 청약 공고 모음 — 접수 중·예정 "
                + ", ".join(f"{k} {a}곳" for k, a in act) + ". 접수일·분양가·자격을 공식 데이터로 정리.")

    def list_page(url, h1, title, desc, groups, intro=None, crumb=None, links=None, kind="list", empty=None, tbl_label=None, og_t=None,
                  sections=None, h1_kw=None, tbl=True):
        all_n = [x for _, g in groups for x in g]
        lm = max([x["modified"] for x in all_n], default=now.isoformat(timespec="seconds"))
        # '한눈에 보기' 표 — 접수 중·예정만 최대 12곳 (2026-11-02 SEO 기획안 개선안 1)
        live = tsort({x["key"]: x for x in all_n if x["status"] in ("open", "upcoming")}.values())
        tbl = live[:12] if tbl else []
        cap = (f"{tbl_label or h1} 접수 중·예정 {len(live)}곳" + (f" 중 {len(tbl)}곳" if len(live) > len(tbl) else "")
               + f" — {d(TODAY.isoformat())} 기준 · 청약홈·LH·마이홈 공식 데이터")
        h = list_tpl.render(h1=h1, groups=groups, intro=intro, crumb=crumb or [("홈", "/")], links=links, empty=empty,
                            page_url=url, title=title, desc=desc, og=og_hub(url, *og_t, all_n) if og_t else "/og-default.jpg",
                            items=all_n, tbl=tbl, tbl_cap=cap, sections=sections or [], h1_kw=h1_kw, **common)
        write(url, h, title, desc, kind, lm)

    def tsort(lst):
        """표 순서: 접수 중은 마감 빠른 순(수시모집처럼 오래 열린 건 뒤로), 그다음 접수 예정은 시작 빠른 순."""
        return sorted(lst, key=lambda x: (0, x["rcpt"][1] or x["rcpt"][0], x["title"]) if x["status"] == "open" else (1, x["rcpt"][0], x["title"]))

    def grouped(lst):
        s = sorted_n(lst)
        g = [("지금 접수 중", [x for x in s if x["status"] == "open"]),
             ("접수 예정", [x for x in s if x["status"] == "upcoming"]),
             ("공고 예정 (보도 기준)", [x for x in s if x["status"] == "pre"]),
             ("당첨자 발표 대기", [x for x in s if x["status"] == "waiting"]),
             ("최근 발표", [x for x in s if x["status"] == "announced"])]
        return [x for x in g if x[1]]

    # ── 검색어 허브 (2026-11-02 SEO 전략 v2) — 행정구역·유형이 아니라 사람들이 검색하는 이름으로 묶은 목록
    def gtxt(x):
        return " ".join([x["title"], x.get("complex") or "", x.get("address") or "", " ".join(x.get("aliases") or [])])
    seoul_mu = [x for x in notices if x["sido"] == "서울" and x["kind"] == "mujeonwi"]          # 서울 줍줍 1,310 · 서울 무순위 청약 760
    dongtan = [x for x in notices if x["sido"] == "경기" and "동탄" in gtxt(x)]                   # 동탄 청약 2,410 · 동탄 분양 2,830
    lotto = [x for x in notices if not x["is_rental"] and x.get("gap") and "저렴" in (x["gap"].get("verdict") or "")
             and "건물분양가" not in x["gap"]["verdict"]]  # 로또 청약 2,160 · 토지임대부는 시세 훅으로 쓰지 않음(README 공유 썸네일 규칙)
    hw = regions["sigungu"].get("경기", {}).get("화성특례시")
    HUB_LINKS, hub_quick = {}, []
    if seoul_mu:
        HUB_LINKS["/region/seoul/"] = [("서울 줍줍·무순위", "/region/seoul/mujeonwi/")]
        hub_quick.append(("서울 줍줍", "/region/seoul/mujeonwi/", f"무순위·임의공급 {len(seoul_mu)}곳"))
    if dongtan:
        HUB_LINKS["/region/gyeonggi/"] = [("동탄 청약", "/region/gyeonggi/dongtan/")]
        if hw:
            HUB_LINKS[f"/region/gyeonggi/{hw}/"] = [("동탄 청약만 보기", "/region/gyeonggi/dongtan/")]
        hub_quick.append(("동탄 청약", "/region/gyeonggi/dongtan/", f"공고 {len(dongtan)}곳"))
    if lotto:
        hub_quick.append(("로또 청약", "/lotto/", "시세보다 싼 공고"))

    # 홈
    home_tpl = E.get_template("home.html")
    s = sorted_n(notices)
    week_end = TODAY + dt.timedelta(days=6 - TODAY.weekday())
    nxt_end = week_end + dt.timedelta(days=7)
    home_groups = [
        ("지금 접수 중", [x for x in s if x["status"] == "open"]),
        ("이번 주 접수", [x for x in s if x["status"] == "upcoming" and x["rcpt"][0] <= week_end.isoformat()]),
        ("다가오는 접수", [x for x in s if x["status"] == "upcoming" and x["rcpt"][0] > week_end.isoformat()]),
        ("공고 예정 (보도 기준)", [x for x in s if x["status"] == "pre"]),
        ("당첨자 발표 대기", [x for x in s if x["status"] == "waiting"]),
        ("최근 발표", [x for x in s if x["status"] == "announced"][:6]),
    ]
    home_groups = [g for g in home_groups if g[1]]
    # 제목·설명: 검색어('청약 공고'·'줍줍')와 오늘 숫자를 앞에 (2026-11-02 SEO 기획안 개선안 2)
    n_open = len([x for x in s if x["status"] == "open"])
    n_up = len([x for x in s if x["status"] == "upcoming"])
    mu_now = [x for x in s if x["kind"] == "mujeonwi" and x["status"] in ("open", "upcoming")]
    title = f"줍줍알람 — 청약 일정·줍줍 공고 | 지금 접수 중 {n_open}곳·예정 {n_up}곳"   # 청약 일정 5,890 · 줍줍 5,210 (_site.json 10/29)
    desc = (f"{d(TODAY.isoformat())} 기준 청약 공고 접수 중 {n_open}곳·접수 예정 {n_up}곳."
            + ((f" 줍줍(무순위) {len(mu_now)}건: " + "·".join((x.get("complex") or x["title"]) for x in mu_now[:2]) + (" 등." if len(mu_now) > 2 else ".")) if mu_now else "")
            + " 무순위·민간분양·공공분양·신혼희망타운·임대의 접수일, 분양가, 자격을 청약홈 공식 데이터로 정리해요.")
    regions_used = sorted(sido_map, key=lambda k: list(regions["sido"]).index(k))
    home_tbl = tsort([x for x in s if x["status"] in ("open", "upcoming")])[:12]
    home_og = og_hub("/", "청약 공고 모음", "오늘 볼 청약 공고", "한눈에 보기", "줍줍(무순위) · 분양 · 신혼희망타운 · 임대 — 접수일 · 분양가 · 자격", s)
    # 홈 첫 화면: 마감 임박 (2026-11-03 리디자인 v2 — 링크 상자 대신 실제 공고가 먼저)
    t0, t1 = TODAY.isoformat(), (TODAY + dt.timedelta(days=1)).isoformat()
    due = [("오늘 마감", d(t0), [x for x in s if x["status"] == "open" and x["rcpt"][1] == t0]),
           ("내일 마감", d(t1), [x for x in s if x["status"] == "open" and x["rcpt"][1] == t1])]
    due = [g for g in due if g[2]]
    if not due:
        soon = tsort([x for x in s if x["status"] == "upcoming"])[:5]
        if soon:
            due = [("곧 접수 시작", "", soon)]
    h = home_tpl.render(groups=home_groups, page_url="/", title=title, desc=desc, og=home_og, due=due,
                        regions_used=regions_used, region_slug=regions["sido"], sido_map=sido_map, hub_quick=hub_quick, n_open=n_open, n_up=n_up,
                        tbl=home_tbl, tbl_cap=f"청약 공고 접수 중·예정 {n_open + n_up}곳 중 {len(home_tbl)}곳 — {d(TODAY.isoformat())} 기준 · 청약홈·LH·마이홈 공식 데이터", **common)
    write("/", h, title, desc, "list", max(x["modified"] for x in notices))

    # 월별 일정 (접수 시작 달 기준)
    months = {}
    for n in notices:
        months.setdefault(n["rcpt"][0][:7], []).append(n)
    mkeys = sorted(months)
    for i, mk in enumerate(mkeys):
        y, m = int(mk[:4]), int(mk[5:])
        lst = sorted(months[mk], key=lambda x: (x["rcpt"][0], x["title"]))
        days = {}
        for x in lst:
            days.setdefault(x["rcpt"][0], []).append(x)
        groups = [(Markup(f"{tdate(k)} 접수 시작"), v) for k, v in days.items()]
        kinds = {}
        for x in lst:
            kinds[KINDS[x["kind"]][0]] = kinds.get(KINDS[x["kind"]][0], 0) + 1
        sidos = sorted({x["sido"] for x in lst}, key=lambda k: list(regions["sido"]).index(k))
        intro = (f"{y}년 {m}월에 접수를 시작하는 청약 공고 {len(lst)}곳을 날짜순으로 모았어요. "
                 f"지역은 {', '.join(sidos)}, 유형은 " + ", ".join(f"{k} {v}곳" for k, v in kinds.items()) + "이에요.")
        links = []
        if i > 0:
            links.append((f"← {int(mkeys[i-1][5:])}월 일정", f"/schedule/{mkeys[i-1]}/"))
        if i < len(mkeys) - 1:
            links.append((f"{int(mkeys[i+1][5:])}월 일정 →", f"/schedule/{mkeys[i+1]}/"))
        list_page(f"/schedule/{mk}/", f"{y}년 {m}월 청약 일정",
                  f"{y}년 {m}월 청약 일정 — 아파트 분양·줍줍·임대 {len(lst)}곳 · 줍줍알람",
                  f"{m}월 청약 일정: {y}년 {m}월에 접수하는 아파트 분양·줍줍(무순위)·임대 {len(lst)}곳의 접수일과 분양가를 날짜순으로 정리. " + ", ".join(sidos) + ".",
                  groups, intro, [("홈", "/"), ("청약 일정", "/schedule/this-week/")], links,
                  og_t=("청약 일정", f"{y}년 {m}월", "청약 일정", "아파트 분양 · 줍줍 · 임대 — 접수 시작일 순서"))

    # 이번 주
    wk_start = TODAY - dt.timedelta(days=TODAY.weekday())
    this_wk = [x for x in notices if wk_start.isoformat() <= x["rcpt"][0] <= week_end.isoformat()]
    next_wk = [x for x in notices if week_end.isoformat() < x["rcpt"][0] <= nxt_end.isoformat()]
    groups = []
    for label, lst in ((f"이번 주 {d(wk_start.isoformat())} ~ {d(week_end.isoformat())}", this_wk),
                       (f"다음 주 {d((week_end + dt.timedelta(days=1)).isoformat())} ~ {d(nxt_end.isoformat())}", next_wk)):
        groups.append((label, sorted(lst, key=lambda x: (x["rcpt"][0], x["title"]))))
    links = [(f"{int(k[5:])}월 전체 일정", f"/schedule/{k}/") for k in mkeys]
    list_page("/schedule/this-week/", "이번 주 청약 일정", f"이번 주 청약 일정 — 아파트 분양·줍줍 {len(this_wk)}곳 · 줍줍알람",
              f"이번 주({drange(wk_start.isoformat(), week_end.isoformat())}) 청약 일정과 다음 주 아파트 분양 일정 미리보기. 줍줍(무순위)·민간분양·공공분양·임대 {len(this_wk)}곳의 접수일·분양가·자격을 한눈에.",
              groups, "월요일부터 일요일까지 접수를 시작하는 공고예요. 다음 주 공고도 미리 확인하세요.",
              [("홈", "/"), ("청약 일정", None)], links, empty="이번 주에 접수를 시작하는 공고가 없어요.", tbl_label="이번 주·다음 주",
              og_t=("청약 일정", "이번 주", "청약 일정", "접수일 · 분양가 · 자격 한눈에"))

    # 지역
    for sido, lst in sido_map.items():
        slug = regions["sido"][sido]
        open_n = [x for x in lst if x["status"] in ("open", "upcoming")]
        sub = sorted({(x["sigungu"], x["sgg_slug"]) for x in lst if (x["sido"], x["sigungu"]) in sgg_pages})
        sgg_counts = {}
        for x in lst:
            sgg_counts[x["sigungu"] or "기타"] = sgg_counts.get(x["sigungu"] or "기타", 0) + 1
        intro = (f"{sido}의 청약 공고 {len(lst)}곳을 모았어요. 지금 접수 중이거나 접수 예정인 공고는 {len(open_n)}곳이에요. "
                 + "시·군·구별로는 " + ", ".join(f"{k} {v}곳" for k, v in sgg_counts.items()) + "이에요.")
        nearest = min((x["rcpt"][0] for x in open_n if x["status"] == "upcoming"), default=None)   # 이미 접수 중인 수시모집(2월 시작 등)이 '가장 가까운 접수일'로 잡히던 문제 (2026-11-02)
        list_page(f"/region/{slug}/", f"{sido} 청약 일정·분양 공고",
                  f"{sido} 청약 일정 — 아파트 분양·줍줍 접수 중·예정 {len(open_n)}곳 · 줍줍알람",
                  f"{sido} 청약 일정과 {sido} 아파트 분양 공고 {len(lst)}곳 중 접수 중·예정 {len(open_n)}곳." + (f" 다음 접수 시작 {d(nearest)}." if nearest else "") + " 줍줍(무순위)·민간분양·공공분양·신혼희망타운 분양가와 자격.",
                  grouped(lst), intro, [("홈", "/"), ("지역", "/region/")], tbl_label=f"{sido} 청약 공고", og_t=(sido, f"{sido} 청약 공고", "한눈에 보기", "아파트 분양 · 줍줍 · 임대 — 접수일 · 분양가 · 자격"), links=
                  [(f"{a} 공고", f"/region/{slug}/{b}/") for a, b in sub] + HUB_LINKS.get(f"/region/{slug}/", []))
    for (sido, sgg), lst in sgg_pages.items():
        slug, sslug = regions["sido"][sido], regions["sigungu"][sido][sgg]
        open_n = [x for x in lst if x["status"] in ("open", "upcoming")]
        list_page(f"/region/{slug}/{sslug}/", f"{sido} {sgg} 청약 공고",
                  f"{sido} {sgg} 청약 일정·분양가 — 접수 중·예정 {len(open_n)}곳 · 줍줍알람",
                  f"{sido} {sgg} 청약 공고 {len(lst)}곳의 접수일·분양가·자격.", grouped(lst),
                  None, [("홈", "/"), ("지역", "/region/"), (sido, f"/region/{slug}/")], links=HUB_LINKS.get(f"/region/{slug}/{sslug}/"),
                  og_t=(sido, f"{sgg} 청약 공고", "한눈에 보기", "아파트 분양 · 줍줍 · 임대 — 접수일 · 분양가 · 자격"))
    # 지역 목록
    h = E.get_template("index_list.html").render(
        h1="지역별 청약 공고", title="지역별 청약 공고 · 줍줍알람",
        desc=hub_desc("시·도별", sido_map, regions_used),
        entries=[(k, f"/region/{regions['sido'][k]}/", len(sido_map[k]),
                  len([x for x in sido_map[k] if x["status"] in ("open", "upcoming")]),
                  tsort([x for x in sido_map[k] if x["status"] in ("open", "upcoming")])[:3]) for k in regions_used],
        lead=hub_lead(sido_map, regions_used),
        page_url="/region/", og="/og-default.jpg", crumb=[("홈", "/"), ("지역", None)], **common)
    write("/region/", h, "지역별 청약 공고 · 줍줍알람", hub_desc("시·도별", sido_map, regions_used), "list")

    # 청약 경쟁률 표 행 (경쟁률 허브·줍줍 허브 공용)
    crow = []
    for n in sorted((x for x in notices if x.get("comp") and x["comp"]["rows"]), key=lambda x: (x["rcpt"][1] or x["rcpt"][0], x["title"]), reverse=True):
        m = re.search(r"([\d,]+)세대에\s*([\d,]+)\S*\s*·\s*(?:평균\s*)?([\d.]+)대 1", n["comp"]["short"] or "")
        rates = [float(r["rate"]) for r in n["comp"]["rows"] if re.fullmatch(r"[\d.]+", r["rate"])]
        if not m:
            continue
        crow.append({"n": n, "supply": f"{m.group(1)}세대", "apply": f"{m.group(2)}건", "avg": f"{float(m.group(3)):g}대 1",
                     "top": f"{max(rates):g}대 1" if rates else "—", "topv": max(rates) if rates else 0})
    # 유형
    by_kind = {}
    for n in notices:
        by_kind.setdefault(n["kind"], []).append(n)
    for k, lst in by_kind.items():
        label, kw = KINDS[k]
        open_n = [x for x in lst if x["status"] in ("open", "upcoming")]
        sidos = sorted({x["sido"] for x in open_n}, key=lambda s_: list(regions["sido"]).index(s_))
        if k == "mujeonwi":   # '줍줍 공고' 검색어 허브 (2026-11-02 SEO 기획안 개선안 2)
            o_ = [x for x in sorted_n(lst) if x["status"] == "open"]
            u_ = [x for x in sorted_n(lst) if x["status"] == "upcoming"]
            top = [(x.get("complex") or x["title"]) for x in (o_ + u_)[:2]]
            cnt = f"지금 접수 중 {len(o_)}건" + (f"·예정 {len(u_)}건" if u_ else "") if o_ else (f"접수 예정 {len(u_)}건" if u_ else "접수 일정 모음")
            t_ = f"줍줍·무순위 청약 공고 — {cnt} · 줍줍알람"   # 네이버 검색량: 줍줍 5,210 · 무순위 청약 3,450 · 줍줍 청약 3,230 (_site.json 10/29)
            ds_ = (f"{d(TODAY.isoformat())} 기준 줍줍(무순위)·임의공급 공고 {cnt.replace('지금 ', '')}"
                   + ((f": {'·'.join(top)}" + (" 등" if len(o_) + len(u_) > 2 else "")) if top else "")
                   + ". 청약통장 없이 추첨으로 뽑는 공고의 접수일·분양가·자격을 공식 데이터로 정리.")
        else:
            t_ = f"{kw} 일정 — 접수 중·예정 {len(open_n)}곳 · 줍줍알람"
            ds_ = f"{kw} 공고 {len(lst)}곳 중 접수 중·예정 {len(open_n)}곳" + (f"({', '.join(sidos)})" if sidos else "") + ". 접수일·분양가·자격을 공식 데이터로 정리."
        h1_, links_, secs_, h1_kw_ = f"{label} 청약 공고", None, None, None
        if k == "rental":   # 검색은 '행복주택'(월 47,500)으로 한다 — 이름·제목 앞에 (2026-11-02 SEO 전략 v2, 주소는 유지)
            h1_ = "행복주택·공공임대 모집 공고"
            t_ = f"행복주택·공공임대 모집 공고 — 접수 중·예정 {len(open_n)}곳 · 줍줍알람"
            ds_ = (f"{d(TODAY.isoformat())} 기준 행복주택·국민임대·매입임대·전세임대 모집 공고 {len(lst)}곳 중 접수 중·예정 {len(open_n)}곳"
                   + (f"({', '.join(sidos)})" if sidos else "") + ". 보증금·월세·자격·주변 시세 비교를 공식 공고 기준으로 정리.")
            links_ = [(lb, u) for lb, u in (("행복주택 자격·소득 기준", "/guide/happy-house/"), ("청년 임대주택 종류 비교", "/guide/youth-rental/"),
                                            ("LH 임대주택 유형", "/guide/lh-rental-types/")) if u.split("/")[2] in gby]
        if k == "mujeonwi":
            links_ = [("서울 줍줍·무순위", "/region/seoul/mujeonwi/"), ("로또 청약 (시세보다 싼 공고)", "/lotto/"),
                      ("무순위 자격 총정리", "/guide/mujeonwi/"), ("청약 경쟁률", "/competition/")]
            secs_ = mu_sections([r for r in crow if r["n"]["kind"] == "mujeonwi"])
            h1_kw_ = cnt if (o_ or u_) else None
        list_page(f"/type/{k}/", h1_, t_, ds_,
                  grouped(lst), KIND_INTRO[k], [("홈", "/"), ("유형", "/type/")], tbl_label=label, links=links_, sections=secs_, h1_kw=h1_kw_,
                  og_t=("줍줍(무순위)", "줍줍 공고", "한눈에 보기", "청약통장 없이 추첨 · 접수일 · 분양가 · 자격") if k == "mujeonwi"
                  else (label, f"{label} 공고", "한눈에 보기", "접수일 · 분양가 · 자격 — 공식 데이터로 정리"))
    h = E.get_template("index_list.html").render(
        h1="유형별 청약 공고", title="유형별 청약 공고 · 줍줍알람",
        desc=hub_desc("무순위(줍줍)·민간분양·공공분양·신혼희망타운·공공임대 유형별", {KINDS[k][0]: v for k, v in by_kind.items()}, [KINDS[k][0] for k in sorted(by_kind, key=list(KINDS).index)]),
        entries=[(KINDS[k][0], f"/type/{k}/", len(v), len([x for x in v if x["status"] in ("open", "upcoming")]),
                  tsort([x for x in v if x["status"] in ("open", "upcoming")])[:3])
                 for k, v in sorted(by_kind.items(), key=lambda kv: list(KINDS).index(kv[0]))],
        intros={KINDS[k][0]: KIND_INTRO[k] for k in by_kind},
        lead=hub_lead({KINDS[k][0]: v for k, v in by_kind.items()}, [KINDS[k][0] for k in sorted(by_kind, key=list(KINDS).index)]),
        page_url="/type/", og="/og-default.jpg", crumb=[("홈", "/"), ("유형", None)], **common)
    write("/type/", h, "유형별 청약 공고 · 줍줍알람",
          hub_desc("무순위(줍줍)·민간분양·공공분양·신혼희망타운·공공임대 유형별", {KINDS[k][0]: v for k, v in by_kind.items()},
                   [KINDS[k][0] for k in sorted(by_kind, key=list(KINDS).index)]), "list")

    # 검색어 허브 그리기
    def lcnt(lst):
        o_ = len([x for x in lst if x["status"] == "open"])
        u_ = len([x for x in lst if x["status"] == "upcoming"])
        return (f"지금 접수 중 {o_}건" + (f"·예정 {u_}건" if u_ else "")) if o_ else (f"접수 예정 {u_}건" if u_ else "최근 공고 모음")
    if seoul_mu:
        c_ = lcnt(seoul_mu)
        cr = [r for r in crow if r["n"] in seoul_mu]
        list_page("/region/seoul/mujeonwi/", "서울 줍줍·무순위 청약 공고", f"서울 줍줍·무순위 청약 — {c_} · 줍줍알람",
                  f"{d(TODAY.isoformat())} 기준 서울 무순위(줍줍)·임의공급 공고 {len(seoul_mu)}곳({c_.replace('지금 ', '')}). 접수일·분양가·자격·청약홈 공식 경쟁률을 한 페이지에.",
                  grouped(seoul_mu),
                  f"서울에서 나온 무순위(줍줍)·임의공급 공고 {len(seoul_mu)}곳을 모았어요. 청약통장 없이 추첨으로 뽑고, 무주택세대구성원만 넣을 수 있어요. "
                  "거주지역 요건(서울 또는 수도권 등)은 공고마다 달라요.",
                  [("홈", "/"), ("지역", "/region/"), ("서울", "/region/seoul/"), ("줍줍·무순위", None)],
                  [("서울 전체 청약", "/region/seoul/"), ("전국 줍줍 공고", "/type/mujeonwi/"), ("무순위 자격 총정리", "/guide/mujeonwi/")],
                  tbl_label="서울 줍줍·무순위", h1_kw=c_,
                  sections=[{"h2": "서울 줍줍 최근 경쟁률", "small": f"{len(cr[:10])}곳",
                             "html": comp_table(cr[:10], f"서울 무순위·임의공급 최근 {len(cr[:10])}곳 — 청약홈 공식 경쟁률")}] if cr else None,
                  og_t=("서울 줍줍", "서울 줍줍 공고", "한눈에 보기", "청약통장 없이 추첨 · 접수일 · 분양가 · 경쟁률"))
    if dongtan:
        c_ = lcnt(dongtan)
        crumb_ = [("홈", "/"), ("지역", "/region/"), ("경기", "/region/gyeonggi/")] + ([("화성", f"/region/gyeonggi/{hw}/")] if hw else []) + [("동탄", None)]
        list_page("/region/gyeonggi/dongtan/", "동탄 청약·분양 공고", f"동탄 청약 일정 — 아파트 분양·임대 {len(dongtan)}곳 · 줍줍알람",
                  f"{d(TODAY.isoformat())} 기준 화성 동탄 일대 청약 공고 {len(dongtan)}곳({c_.replace('지금 ', '')}). 동탄 아파트 분양·행복주택의 접수일·분양가·보증금·자격.",
                  grouped(dongtan),
                  f"화성 동탄신도시 일대에서 나온 청약 공고 {len(dongtan)}곳을 모았어요. 화성시 전체 공고는 화성 페이지에 있어요.",
                  crumb_, ([("화성 전체 청약", f"/region/gyeonggi/{hw}/")] if hw else []) + [("경기 청약", "/region/gyeonggi/")]
                  + ([("2기 신도시 정리", "/guide/new-town-2nd/")] if "new-town-2nd" in gby else []),
                  tbl_label="동탄", h1_kw=c_,
                  og_t=("동탄", "동탄 청약 공고", "한눈에 보기", "아파트 분양 · 임대 — 접수일 · 분양가 · 자격"))
    if lotto:
        lot = sorted(lotto, key=lambda x: (x["status"] not in ("open", "upcoming", "pre"), -gap_won(x["gap"]["verdict"])))
        live_ = [x for x in lot if x["status"] in ("open", "upcoming")]
        rows_ = []
        for x in lot:
            g = x["gap"]
            base = " · ".join(f"{k} {v}" for k, v in (g.get("rows") or [])[:1])
            rows_.append([alink(x), f"{x['sido']} {x['sigungu'] or ''}", STATUS[x["status"]][0], g["verdict"], base or "—"])
        tbl_ = mk_table(f"주변 실거래보다 분양가가 낮은 공고 {len(lot)}곳 — 비교 단지 실거래 기준 추정 · {d(TODAY.isoformat())}",
                        ["단지", "지역", "상태", "시세 대비", "비교 기준 (실거래)"], rows_, left=5, txt=True)
        top_ = live_[0] if live_ else lot[0]
        list_page("/lotto/", "로또 청약 — 시세보다 싸게 나온 공고", f"로또 청약 — 시세보다 싸게 나온 공고 {len(lot)}곳 · 줍줍알람",
                  f"{d(TODAY.isoformat())} 기준 주변 실거래보다 분양가가 낮은 청약 공고 {len(lot)}곳(접수 중·예정 {len(live_)}곳). "
                  f"{top_.get('complex') or top_['title']} {top_['gap']['verdict']} 등. 비교 단지와 실거래 시점을 함께 정리.",
                  grouped(lot),
                  "같은 생활권·비슷한 면적 아파트의 최근 실거래가보다 분양가가 낮게 나온 공고만 모았어요. 비교 단지와 거래 시점을 표에 함께 적었고, 금액은 모두 추정이에요. "
                  "차익이 클수록 경쟁이 몰리고, 실거주 의무·전매 제한·재당첨 제한이 붙는 경우가 많으니 공고별 '주의점'을 꼭 확인하세요.",
                  [("홈", "/"), ("로또 청약", None)],
                  [("줍줍 공고", "/type/mujeonwi/"), ("청약 경쟁률", "/competition/"), ("서울 줍줍", "/region/seoul/mujeonwi/")],
                  tbl=False, h1_kw=f"접수 중·예정 {len(live_)}곳",
                  sections=[{"h2": "시세보다 얼마나 싼가요", "small": f"{len(lot)}곳", "top": True, "html": tbl_}],
                  og_t=("로또 청약", "시세보다 싼 공고", "한눈에 보기", "주변 실거래와 비교 · 비교 단지 · 거래 시점"))

    def comp_intro(rows_, best_):
        """경쟁률 허브 첫 문단 — 숫자 요약 (2026-11-04 허브 보강)."""
        avgv = [float(r["avg"].split("대")[0]) for r in rows_]
        under = sum(1 for v in avgv if v < 1)
        mu = sum(1 for r in rows_ if r["n"]["kind"] == "mujeonwi")
        bn = best_["n"].get("complex") or best_["n"]["title"]
        return (f"최근 접수가 끝난 {len(rows_)}곳(무순위·줍줍 {mu}곳 포함)의 청약홈 공식 경쟁률이에요. "
                f"주택형 기준 최고 경쟁률은 {bn} {best_['top']}이고, 평균 경쟁률이 1대 1에 못 미친 미달 단지는 {under}곳이에요.")

    # 청약 경쟁률 허브 (2026-11-02 SEO 기획안 3단계 — 네이버 '청약 경쟁률' 월 약 4,300회 검색, _site.json) — crow는 유형 허브 앞에서 계산
    if crow:
        best = max(crow, key=lambda r: r["topv"])
        h1 = "청약 경쟁률"
        title = f"청약 경쟁률 — 최근 청약홈 공식 경쟁률 {len(crow)}곳 · 줍줍알람"
        desc = (f"{d(TODAY.isoformat())} 기준 최근 접수가 끝난 아파트 청약·무순위(줍줍) {len(crow)}곳의 청약홈 공식 경쟁률. "
                f"최고 {best['n'].get('complex') or best['n']['title']} {best['top']}. 단지별 공급·접수 건수와 평균·최고 경쟁률을 한 표로.")
        crumb = [("홈", "/"), ("청약 경쟁률", None)]
        h = E.get_template("competition.html").render(
            h1=h1, rows=crow, crumb=crumb, page_url="/competition/", title=title, desc=desc,
            intro=comp_intro(crow, best),
            faq=COMP_FAQ, faq_ld={"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in COMP_FAQ]},
            tbl_cap=f"청약홈 공식 경쟁률 {len(crow)}곳 — {d(TODAY.isoformat())} 기준 · 접수 마감이 최근인 순서",
            og=og_hub("/competition/", "청약 경쟁률", "청약 경쟁률", "한눈에 보기", "청약홈 공식 경쟁률 — 무순위(줍줍) · 아파트 분양", [r["n"] for r in crow]),
            **common)
        write("/competition/", h, title, desc, "list", max(r["n"]["modified"] for r in crow))

    # 가이드 칼럼
    GUIDES.build(E, notices, write, common, PUB, BASE, TODAY, problems)

    # 기본 페이지
    pg = E.get_template("page.html")
    for slug, (h1, desc) in BASIC.items():
        body = E.get_template(f"pages/{slug}.html").render(**common, n_count=len(notices))
        title = f"{h1} · 줍줍알람"
        h = pg.render(h1=h1, body=Markup(body), page_url=f"/{slug}/", title=title, desc=desc, og="/og-default.jpg",
                      crumb=[("홈", "/"), (h1, None)], **common)
        write(f"/{slug}/", h, title, desc, "page")

    # 404
    h = E.get_template("404.html").render(page_url="/404.html", title="페이지를 찾을 수 없어요 · 줍줍알람",
                                          desc="", og="/og-default.jpg", groups=home_groups[:2], **common)
    (PUB / "404.html").write_text(h)

    # 단지 이름 → 페이지 주소 (시트 스크립트가 스레드 링크·DM에 씀). 공개는 되지만 사이트맵에는 넣지 않음.
    links = []
    for n in notices:
        names = [n["title"], n.get("complex") or ""] + list(n.get("aliases") or [])
        row = next((r for e_, r in items if e_["key"] == n["key"] and r), None)
        if row:
            names.append(row.get("주택명", ""))
        links.append({"key": n["key"], "url": BASE + n["url"], "status": n["status"], "kind": n["kind"],
                      "names": sorted({x for x in names if x}), "rcpt": n["rcpt"],
                      "moved_to": (BASE + n["moved"]["url"]) if n.get("moved") else None})
    (PUB / "links.json").write_text(json.dumps({"built_at": now.isoformat(timespec="seconds"), "links": links},
                                               ensure_ascii=False, separators=(",", ":")))

    # 사이트맵·RSS·robots·헤더
    write_sitemaps(now)
    write_rss(notices, now)
    (PUB / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /data/\nDisallow: /drafts/\n\nSitemap: {BASE}/sitemap.xml\n")
    (PUB / "_headers").write_text(HEADERS)
    redirects = json.loads((DATA / "redirects.json").read_text()) if (DATA / "redirects.json").exists() else []
    (PUB / "_redirects").write_text("".join(f"{a} {b} 301\n" for a, b in redirects))

    # 고아 공고 이미지 폴더 정리 (페이지가 없는 apt/ 폴더는 이미지뿐이면 남겨둠 — 지우지 않음)
    errs = check(notices)
    report = {"built_at": now.isoformat(timespec="seconds"), "today": TODAY.isoformat(), "pages": len(PAGES),
              "notices": len(notices), "problems": problems, "errors": errs,
              "seo_gaps": {k: [f"{a} ({b:,})" for a, b in v] for k, v in SEO_GAPS.items()}}
    (SITE / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    if not a.no_state:
        (DATA / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True))
    print(f"pages {len(PAGES)} · notices {len(notices)} · problems {len(problems)} · errors {len(errs)}")
    for p in problems:
        print("  ", *p)
    for e_ in errs:
        print("  ERROR", e_)
    sys.exit(1 if errs else 0)


BASIC = {
    "about": ("소개·작성 원칙", "줍줍알람이 누구이고, 어떤 자료로 청약 공고를 정리하고 확인하는지, 추정 차익을 어떻게 계산하는지 설명해요."),
    "sources": ("데이터 출처", "청약홈·LH·마이홈 공공데이터, 국토부 실거래가, 지도, 단지 이미지 등 줍줍알람이 쓰는 자료의 출처와 이용 조건."),
    "privacy": ("개인정보 처리방침", "줍줍알람 사이트의 개인정보 처리방침. 수집하는 정보, 쿠키, 방문 통계, 문의 방법."),
    "terms": ("이용약관", "줍줍알람 사이트 이용약관. 정보 제공 목적, 책임의 한계, 저작권."),
    "contact": ("문의·오류 제보", "줍줍알람에 문의하거나 공고 정보의 오류를 알려주는 방법."),
}

HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN
  Permissions-Policy: interest-cohort=()
/style.*.css
  Cache-Control: public, max-age=31536000, immutable
/apt/*/*.webp
  Cache-Control: public, max-age=604800
/favicon.*
  Cache-Control: public, max-age=604800
/links.json
  Cache-Control: public, max-age=300
  Access-Control-Allow-Origin: *
"""


def write_sitemaps(now):
    groups = {"apt": [], "list": [], "page": []}
    for url, p in PAGES.items():
        if p["index"]:
            groups[p["kind"]].append((url, p["lastmod"]))
    files = {"apt": "sitemap-apt.xml", "list": "sitemap-list.xml", "page": "sitemap-guide.xml"}
    latest = {}
    for k, f in files.items():
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for url, lm in sorted(groups[k]):
            lines.append(f"<url><loc>{BASE}{xesc(url)}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>")
        lines.append("</urlset>")
        (PUB / f).write_text("\n".join(lines) + "\n")
        latest[f] = max([lm for _, lm in groups[k] if lm], default=now.isoformat(timespec="seconds"))
    idx = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for f, lm in latest.items():
        idx.append(f"<sitemap><loc>{BASE}/{f}</loc><lastmod>{lm}</lastmod></sitemap>")
    idx.append("</sitemapindex>")
    (PUB / "sitemap.xml").write_text("\n".join(idx) + "\n")


def rfc_dt(iso):
    """'2026-10-29'(가이드)·'2026-11-02T20:42:02+09:00'(공고) → 시간대 있는 datetime (날짜만이면 9시 KST)"""
    t = dt.datetime.fromisoformat(iso if "T" in iso else iso + "T09:00:00")
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))


def write_rss(notices, now):
    # 공고 최근 30건 + 가이드 칼럼 전부 (2026-11-02 — 처음엔 공고만 넣어 가이드가 빠져 있었음)
    items = [{"title": n["page_title"], "url": n["url"], "desc": n["desc"], "date": n["modified"]}
             for n in sorted(notices, key=lambda n: n["modified"], reverse=True)[:30]]
    for g in GUIDES.load():
        u = f"/guide/{g['slug']}/"
        if u in PAGES:   # 실제로 발행된 칼럼만
            items.append({"title": PAGES[u]["title"], "url": u, "desc": PAGES[u]["desc"], "date": g.get("published") or g.get("checked")})
    items.sort(key=lambda x: rfc_dt(x["date"]), reverse=True)

    def rfc(iso):
        return rfc_dt(iso).strftime("%a, %d %b %Y %H:%M:%S %z")
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           "<title>줍줍알람</title>", f"<link>{BASE}/</link>", "<description>무순위·청약 공고를 공식 데이터로 정리해요</description>",
           "<language>ko</language>", f'<atom:link href="{BASE}/rss.xml" rel="self" type="application/rss+xml"/>',
           f"<lastBuildDate>{rfc(now.isoformat())}</lastBuildDate>"]
    for n in items:
        out.append(f"<item><title>{xesc(n['title'].replace(' · 줍줍알람', ''))}</title><link>{BASE}{n['url']}</link>"
                   f"<guid isPermaLink=\"true\">{BASE}{n['url']}</guid><description>{xesc(n['desc'])}</description>"
                   f"<pubDate>{rfc(n['date'])}</pubDate></item>")
    out.append("</channel></rss>")
    (PUB / "rss.xml").write_text("\n".join(out) + "\n")


def check(notices):
    """기획안 '검사 체크리스트' 자동 확인."""
    errs = []
    seen_t, seen_d = {}, {}
    for url, p in PAGES.items():
        if not p["index"]:
            continue
        if p["title"] in seen_t:
            errs.append(f"title 중복: {url} = {seen_t[p['title']]}")
        seen_t[p["title"]] = url
        if p["desc"]:
            if p["desc"] in seen_d:
                errs.append(f"description 중복: {url} = {seen_d[p['desc']]}")
            seen_d[p["desc"]] = url
        hx = p["html"]
        if f'<link rel="canonical" href="{BASE}{url}">' not in hx:
            errs.append(f"canonical 없음/다름: {url}")
        if hx.count("<h1") != 1:
            errs.append(f"H1 개수 {hx.count('<h1')}: {url}")
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', hx, re.S):
            try:
                json.loads(m.group(1))
            except Exception as ex:
                errs.append(f"JSON-LD 오류 {url}: {ex}")
        for m in re.finditer(r'<img [^>]*>', hx):
            tag = m.group(0)
            for attr in ("width=", "height=", "alt="):
                if attr not in tag:
                    errs.append(f"img {attr} 없음: {url} {tag[:60]}")
    # 내부 링크
    exist = set(PAGES) | {"/404.html"}
    for url, p in PAGES.items():
        for m in re.finditer(r'href="(/[^"#]*)"', p["html"]):
            h = m.group(1)
            if "?" in h:
                errs.append(f"주소에 ? : {url} → {h}")
            if h.endswith("/") and h not in exist:
                errs.append(f"깨진 링크: {url} → {h}")
            elif not h.endswith("/") and not (PUB / h.lstrip("/")).exists() and not (PUB / url.lstrip("/") / h).exists():
                errs.append(f"없는 파일: {url} → {h}")
        for m in re.finditer(r'src="([^":]+)"', p["html"]):
            s = m.group(1)
            base = PUB / url.lstrip("/") if url.endswith("/") else (PUB / url.lstrip("/")).parent
            f = PUB / s.lstrip("/") if s.startswith("/") else base / s
            if not f.exists():
                errs.append(f"없는 이미지: {url} → {s}")
    # 화면 숫자 = 데이터
    for n in notices:
        hx = PAGES[n["url"]]["html"]
        if n.get("max_price") and not n["is_pre"] and not n["is_rental"] and won(n["max_price"]) not in hx:
            errs.append(f"최고가 표시 누락: {n['url']}")
    return errs


if __name__ == "__main__":
    main()
