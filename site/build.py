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
    # 시안 A '한마디 바로 아래'는 애드센스 자리로 비워 둠 — ADSENSE 참고)
    "apt_mo": {"mq": "(max-width:1023px)", "height": 120,
               "opts": {"id": 1044447, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "120", "tsource": ""}},
    "apt_end_mo": {"mq": "(max-width:1023px)", "height": 300,
                   "opts": {"id": 1044447, "template": "carousel", "trackingCode": "AF3230467", "subId": "jupjupalarm", "width": "100%", "height": "300", "tsource": ""}},
}
# 애드센스 (승인 전이라 비어 있음 — client에 ca-pub-…, slots에 광고 단위 ID를 넣으면 그 자리에 나옴)
ADSENSE = {"client": "", "slots": {"apt_top": ""}}
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
KIND_INTRO = {
    "mujeonwi": "1·2순위 청약이 끝난 뒤 남은 세대나 계약 취소분을 다시 뽑는 공고예요. 청약통장 없이 추첨으로 뽑고, 2025.2 개편 뒤로는 무주택자만 신청할 수 있어요. 거주지역 요건과 재당첨 제한은 공고마다 달라요. 임의공급(사업주체가 조건을 따로 정하는 공급)도 여기에 함께 모았어요.",
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
    n["unit_word"] = "호" if hs else "세대"
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
    return f"{base} {'·'.join(pick)} · 줍줍알람"


def kw_h2(n, seo):
    """검색량이 있는 주제의 소제목 앞에 단지명을 붙인다 (최대 3개)."""
    h2 = {}
    if not seo:
        return h2
    nm = n.get("complex") or n["title"]
    cand = [("sch", "청약 일정", "청약 일정"), ("price", "분양가", None), ("plan", "평면도", "평면도·면적"),
            ("comp", "경쟁률", "청약 경쟁률"), ("elig", "자격", "신청 자격"), ("layout", "배치도", "단지 배치도")]
    cand = [c for c in cand if seo["has"].get(c[1]) and seo["vol"](c[1]) >= 50]
    cand.sort(key=lambda c: -seo["vol"](c[1]))
    for sec, _, label in cand[:3]:
        h2[sec] = f"{nm} {label}" if label else nm
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
    f1 = ImageFont.truetype(str(REPO / "fonts/BlackHanSans-Regular.ttf"), 150)
    f2 = ImageFont.truetype(str(REPO / "fonts/NotoSansKR-VF.ttf"), 44)
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
    key = json.dumps({"v": "B7", "lines": lines, "photo": ph and [ph["image"], ph.get("pos"), ph.get("credit"), src.stat().st_mtime]}, ensure_ascii=False)
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


def og_card(n, dst):
    """사진 없는 공고용 공유 썸네일 (1200×630, 남색 카드)."""
    from PIL import Image, ImageDraw, ImageFont
    lines = og_lines(n)
    tag = dst.with_suffix(".key")
    key = json.dumps(lines, ensure_ascii=False)
    if dst.exists() and tag.exists() and tag.read_text(encoding="utf-8") == key:
        return
    kind, st, title, loc, big, small = lines
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#0F1E3D")
    dr = ImageDraw.Draw(im)
    fh = lambda sz: ImageFont.truetype(str(REPO / "fonts/BlackHanSans-Regular.ttf"), sz)

    def fn(sz, bold=True):
        f = ImageFont.truetype(str(REPO / "fonts/NotoSansKR-VF.ttf"), sz)
        try:
            f.set_variation_by_name("Bold" if bold else "Regular")
        except Exception:
            pass
        return f
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


def notice_images(n):
    out = PUB / "apt" / n["key"]
    imgs = {}
    if n.get("photo"):
        sz = img_out(n["photo"]["image"], out / "hero.webp", 960)
        if sz:
            imgs["hero"] = {"src": "hero.webp", "w": sz[0], "h": sz[1]}
    if n.get("map"):
        sz = img_out(n["map"], out / "map.webp", 960)
        if sz:
            imgs["map"] = {"src": "map.webp", "w": sz[0], "h": sz[1]}
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
    e.filters.update(combine=lambda a, b: {**a, **b}, money=money, mrange=lambda r: f"{money(r[0])[:-1]}~{money(r[1])}" if r and r[0] != r[1] else money(r[0]) if r else '', d=d, drange=drange, won=won, py=py, m2=m2, tdate=tdate, trange=trange, tmonth=tmonth,
                     jsonld=lambda o: Markup(json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")))
    def crumb_ld(items, last, page_url):
        el = [{"@type": "ListItem", "name": lab, "item": BASE + u} for lab, u in items if u]
        el.append({"@type": "ListItem", "name": last})
        for i, x in enumerate(el, 1):
            x["position"] = i
        return {"@type": "BreadcrumbList", "itemListElement": el}
    def items_ld(items):
        return [{"@type": "ListItem", "position": i, "url": BASE + n["url"], "name": n["title"]} for i, n in enumerate(items, 1)]
    e.globals.update(HAS_GUIDES=bool(GUIDES.load()), RENTAL_EXPLAIN=RENTAL_EXPLAIN, BASE=BASE, IG=IG, THREADS=THREADS, COUPANG=COUPANG, COUPANG_NOTE=COUPANG_NOTE, ADSENSE=ADSENSE, STATUS=STATUS, KINDS=KINDS, crumb_ld=crumb_ld, items_ld=items_ld,
                     logo=Markup((SITE / "static/favicon.svg").read_text().replace('<svg xmlns="http://www.w3.org/2000/svg" ', '<svg class="mark" aria-hidden="true" focusable="false" ')))
    return e


PAGES = {}  # url → dict(title, desc, html)


def write(url, html_text, title, desc, kind, lastmod=None, index=True):
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

    # 출력 폴더 정리 (이미지는 남겨 재사용)
    PUB.mkdir(exist_ok=True)
    for p in PUB.iterdir():
        if p.name == "apt":
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    css_hash = None
    for f in (SITE / "static").iterdir():
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
        st = n["status"]
        typ = n["kind_label"]
        seo = seo_of(n)
        n["h2"] = kw_h2(n, seo)
        if n.get("moved"):
            title = f"{n['title']} 예상 vs 실제 분양가 — 공고 전 전망 정리 · 줍줍알람"
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
            desc = f"{n['units']:,}세대 · 예상 분양가 {n['price_text']} · {d(n['rcpt'][0])} 접수 예정(보도 기준). 공고 전 단지의 일정·분양가 전망·시세 비교를 정리. 공고가 나오면 공식 값으로 바꿔요."
        elif n["is_rental"] and n["houses"]:
            rr = n.get("rent_range") or {}
            cond = n.get("rent_level") or ""
            if rr.get("deposit"):
                cond += f" · 보증금 {money(rr['deposit'][0])[:-1]}~{money(rr['deposit'][1])} · 월 {money(rr['monthly'][0])[:-1]}~{money(rr['monthly'][1])}"
            sgs = "·".join(g for g, _ in n["house_groups"][:4])
            desc = f"{n['units']}호({sgs}) · {cond} · 접수 {rc} {n.get('receipt_note') or ''}. 주택 목록·면적·자격·신청 방법을 한 번에."
        elif n["is_rental"]:
            cond = f"보증금 {money(rs['deposit'])} · 월 {money(rs['monthly'])}" if rs.get("deposit") else f"주택형 {len(n['rent_models'])}개"
            desc = f"접수 {rc} · {cond} · {n['units']:,}세대 · {n.get('target') or n['kind_label']}. 신청 자격·일정과 공식 공고 링크를 한 번에."
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
        write(n["url"], h, title, desc, "apt", n["modified"])

    # ── 목록 공통
    list_tpl = E.get_template("list.html")

    def list_page(url, h1, title, desc, groups, intro=None, crumb=None, links=None, kind="list", empty=None):
        all_n = [x for _, g in groups for x in g]
        lm = max([x["modified"] for x in all_n], default=now.isoformat(timespec="seconds"))
        h = list_tpl.render(h1=h1, groups=groups, intro=intro, crumb=crumb or [("홈", "/")], links=links, empty=empty,
                            page_url=url, title=title, desc=desc, og="/og-default.jpg", items=all_n, **common)
        write(url, h, title, desc, kind, lm)

    def grouped(lst):
        s = sorted_n(lst)
        g = [("지금 접수 중", [x for x in s if x["status"] == "open"]),
             ("접수 예정", [x for x in s if x["status"] == "upcoming"]),
             ("공고 예정 (보도 기준)", [x for x in s if x["status"] == "pre"]),
             ("당첨자 발표 대기", [x for x in s if x["status"] == "waiting"]),
             ("최근 발표", [x for x in s if x["status"] == "announced"])]
        return [x for x in g if x[1]]

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
    title = "줍줍알람 — 청약 일정·아파트 분양·줍줍(무순위) 한눈에"
    desc = f"오늘 볼 청약 공고 {len([x for x in s if x['status'] in ('open', 'upcoming')])}곳. 무순위(줍줍)·민간분양·공공분양·신혼희망타운의 접수일, 분양가, 자격을 공식 데이터로 정리해요."
    regions_used = sorted(sido_map, key=lambda k: list(regions["sido"]).index(k))
    h = home_tpl.render(groups=home_groups, page_url="/", title=title, desc=desc, og="/og-default.jpg",
                        regions_used=regions_used, region_slug=regions["sido"], sido_map=sido_map, **common)
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
                  groups, intro, [("홈", "/"), ("청약 일정", "/schedule/this-week/")], links)

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
              [("홈", "/"), ("청약 일정", None)], links, empty="이번 주에 접수를 시작하는 공고가 없어요.")

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
        nearest = min((x["rcpt"][0] for x in open_n), default=None)
        list_page(f"/region/{slug}/", f"{sido} 청약 일정·분양 공고",
                  f"{sido} 청약 일정 — 아파트 분양·줍줍 접수 중·예정 {len(open_n)}곳 · 줍줍알람",
                  f"{sido} 청약 일정과 {sido} 아파트 분양 공고 {len(lst)}곳 중 접수 중·예정 {len(open_n)}곳." + (f" 가장 가까운 접수일 {d(nearest)}." if nearest else "") + " 줍줍(무순위)·민간분양·공공분양·신혼희망타운 분양가와 자격.",
                  grouped(lst), intro, [("홈", "/"), ("지역", "/region/")],
                  [(f"{a} 공고", f"/region/{slug}/{b}/") for a, b in sub])
    for (sido, sgg), lst in sgg_pages.items():
        slug, sslug = regions["sido"][sido], regions["sigungu"][sido][sgg]
        open_n = [x for x in lst if x["status"] in ("open", "upcoming")]
        list_page(f"/region/{slug}/{sslug}/", f"{sido} {sgg} 청약 공고",
                  f"{sido} {sgg} 청약 일정·분양가 — 접수 중·예정 {len(open_n)}곳 · 줍줍알람",
                  f"{sido} {sgg} 청약 공고 {len(lst)}곳의 접수일·분양가·자격.", grouped(lst),
                  None, [("홈", "/"), ("지역", "/region/"), (sido, f"/region/{slug}/")])
    # 지역 목록
    h = E.get_template("index_list.html").render(
        h1="지역별 청약 공고", title="지역별 청약 공고 · 줍줍알람",
        desc="시·도별 청약 공고 모음. " + ", ".join(f"{k} {len(v)}곳" for k, v in sido_map.items()) + ".",
        entries=[(k, f"/region/{regions['sido'][k]}/", len(sido_map[k]),
                  len([x for x in sido_map[k] if x["status"] in ("open", "upcoming")])) for k in regions_used],
        page_url="/region/", og="/og-default.jpg", crumb=[("홈", "/"), ("지역", None)], **common)
    write("/region/", h, "지역별 청약 공고 · 줍줍알람", "", "list")

    # 유형
    by_kind = {}
    for n in notices:
        by_kind.setdefault(n["kind"], []).append(n)
    for k, lst in by_kind.items():
        label, kw = KINDS[k]
        open_n = [x for x in lst if x["status"] in ("open", "upcoming")]
        sidos = sorted({x["sido"] for x in open_n}, key=lambda s_: list(regions["sido"]).index(s_))
        list_page(f"/type/{k}/", f"{label} 청약 공고",
                  f"{kw} 일정 — 접수 중·예정 {len(open_n)}곳 · 줍줍알람",
                  f"{kw} 공고 {len(lst)}곳 중 접수 중·예정 {len(open_n)}곳" + (f"({', '.join(sidos)})" if sidos else "") + ". 접수일·분양가·자격을 공식 데이터로 정리.",
                  grouped(lst), KIND_INTRO[k], [("홈", "/"), ("유형", "/type/")])
    h = E.get_template("index_list.html").render(
        h1="유형별 청약 공고", title="유형별 청약 공고 · 줍줍알람",
        desc="무순위(줍줍)·민간분양·공공분양·신혼희망타운 유형별 청약 공고 모음.",
        entries=[(KINDS[k][0], f"/type/{k}/", len(v), len([x for x in v if x["status"] in ("open", "upcoming")]))
                 for k, v in sorted(by_kind.items(), key=lambda kv: list(KINDS).index(kv[0]))],
        intros={KINDS[k][0]: KIND_INTRO[k] for k in by_kind},
        page_url="/type/", og="/og-default.jpg", crumb=[("홈", "/"), ("유형", None)], **common)
    write("/type/", h, "유형별 청약 공고 · 줍줍알람", "", "list")

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


def write_rss(notices, now):
    items = sorted(notices, key=lambda n: n["modified"], reverse=True)[:30]
    def rfc(iso):
        return dt.datetime.fromisoformat(iso).strftime("%a, %d %b %Y %H:%M:%S %z")
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           "<title>줍줍알람</title>", f"<link>{BASE}/</link>", "<description>무순위·청약 공고를 공식 데이터로 정리해요</description>",
           "<language>ko</language>", f'<atom:link href="{BASE}/rss.xml" rel="self" type="application/rss+xml"/>',
           f"<lastBuildDate>{rfc(now.isoformat())}</lastBuildDate>"]
    for n in items:
        out.append(f"<item><title>{xesc(n['page_title'].replace(' · 줍줍알람', ''))}</title><link>{BASE}{n['url']}</link>"
                   f"<guid isPermaLink=\"true\">{BASE}{n['url']}</guid><description>{xesc(n['desc'])}</description>"
                   f"<pubDate>{rfc(n['modified'])}</pubDate></item>")
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
