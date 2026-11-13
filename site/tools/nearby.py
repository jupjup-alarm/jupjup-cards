#!/usr/bin/env python3
"""주변 단지 실거래 비교 데이터 (2026-11-13 사용자 결정 — 애드센스 '가치가 별로 없는 콘텐츠' 대응:
"주변 단지와의 분석, 시세 비교 이런 콘텐츠를 더 넣어야겠네").

접수 중·예정 공고마다 국토부 실거래가 API로 같은 동(없으면 같은 시군구)·비슷한 면적(±8㎡) 아파트의
최근 6개월 매매(분양) 또는 월세(임대) 거래를 모아 site/data/nearby/<key>.json 에 저장한다.
사이트 build.py가 공고 페이지에 '주변 단지 실거래 비교' 표와 숫자 분석 문장을 그린다. 모델 없음.

사용: CHEONGYAK_ENV=<DATA_GO_KR_KEY 파일> python3 site/tools/nearby.py [--max 20] [--days 3] [--key K]
"""
import argparse
import datetime as dt
import json
import os
import re
import statistics as st
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "data" / "nearby"
TOOL = SITE / "tools" / "realprice.py"
SKIP_KIND = re.compile(r"청약결과|청약상식|부동산뉴스|정리|생활정보|주간")
SIDO = {"서울특별시": "서울", "서울시": "서울", "인천광역시": "인천", "경기도": "경기"}


def won(txt):
    """'4억7,552만원' / '275만원' / '54,660원' / '2,747,000원' → 원."""
    t = (txt or "").replace(" ", "")
    m = re.match(r"(?:(\d+)억)?(?:([\d,]+)만)?(?:([\d,]+))?원?", t)
    if not m or not any(m.groups()):
        return None
    e, man, w = (int((g or "0").replace(",", "") or 0) for g in m.groups())
    return e * 10**8 + man * 10**4 + w


def lawd_name(addr, codes):
    a = addr
    for k, v in SIDO.items():
        a = a.replace(k, v)
    best = None
    for name in codes:
        parts = name.split()
        if parts[0] not in a[:6]:
            continue
        if all(p in a for p in parts[1:]) and (not best or len(name) > len(best)):
            best = name
    return best


def dong_of(addr, lawd):
    for m in re.finditer(r"([가-힣]{1,5}\d?[동읍면가])(?=[\s,)\d]|$)", addr):
        w = m.group(1)
        if w in (lawd or "") or re.search(r"단지|센터|복지|아파트|행정|주공", w):
            continue
        return re.sub(r"\d+([동가])$", r"\1", w)   # 석수2동(행정동) → 석수동(법정동)
    return None


def our_terms(r):
    g = r.get("분양가/임대조건", "") or ""
    txt = " ".join(str(r.get(k, "")) for k in ("분류", "공급유형", "단지명"))
    rental = bool(re.search(r"임대|전세", txt)) or "보증금" in g
    if rental:
        dep = re.search(r"보증금\s*([\d억만,]+원)", g)
        mon = re.search(r"월\s*(?:임대료\s*)?([\d만,]+원)", g)
        area = re.search(r"전용\s*(\d{2,3}(?:\.\d+)?)", g + " " + str(r.get("공급세대", "")))
        return {"rental": True, "deposit": won(dep.group(1)) if dep else None,
                "monthly": won(mon.group(1)) if mon else None, "area": float(area.group(1)) if area else None}
    m = re.search(r"(\d{2,3})(?:\.\d+)?[A-Z]?\s*(?:㎡|형)?\s*(?:최고|최저)?\s*(\d+억\s*[\d,]*\s*만?\s*원|[\d,]+만\s*원)", g)
    if not m:
        return None
    return {"rental": False, "area": float(m.group(1)), "price": won(m.group(2)), "label": m.group(0)[:30]}


_CACHE = {}


def query(kind, lawd, dong, area, env):
    """realprice.py를 프로세스 안에서 불러 (시군구·월) 응답을 캐시 — 같은 시군구 공고가 여럿이어도 API는 월마다 한 번.
    (2026-11-13 첫 실행이 25분 시간 초과: 공고마다 따로 6개월×2번 호출하던 것)"""
    sys.path.insert(0, str(TOOL.parent))
    import realprice as rp
    os.environ["CHEONGYAK_ENV"] = env
    k = rp.key()
    deals = []
    mons = rp.months(6)
    for ym in mons:
        ck = (kind, lawd, ym)
        if ck not in _CACHE:
            try:
                _CACHE[ck] = rp.fetch(kind, lawd, ym, k)
            except BaseException as e:  # noqa: BLE001  (realprice는 SystemExit로 알림)
                raise RuntimeError(str(e)[:150])
        for it in _CACHE[ck]:
            r = rp.norm(kind, it)
            if not r:
                continue
            if kind == "trade" and "직거래" in (r.get("via") or ""):
                continue
            if kind != "trade" and (rp.PUBLIC.search(r["name"] or "") or not r.get("monthly")):
                continue
            if dong and r["dong"] != dong:
                continue
            if area and (r["area"] is None or abs(r["area"] - area) > 8):
                continue
            deals.append(r)
    deals.sort(key=lambda r: r["date"], reverse=True)
    by = {}
    for r in deals:
        g = by.setdefault((r["name"], r["dong"]), {"name": r["name"], "dong": r["dong"], "built": r["built"], "n": 0, "latest": r})
        g["n"] += 1
    raw = sum(len(_CACHE.get((kind, lawd, ym), [])) for ym in mons)
    if not deals:
        print(f"  [진단] {kind} {lawd} dong={dong} area={area} 원자료 {raw}건 → 조건 맞는 0건", file=sys.stderr)
    return {"source": "국토교통부 실거래가 공개시스템 (공공데이터포털 API)", "months": mons[::-1], "count": len(deals), "raw": raw,
            "complexes": sorted(by.values(), key=lambda g: -g["n"])[:20], "deals": deals[:200]}


def summarize(res, ours):
    deals = res.get("deals") or []
    rows = []
    for g in res.get("complexes") or []:
        mine = [d for d in deals if d["name"] == g["name"] and d["dong"] == g["dong"]]
        lt = g["latest"]
        row = {"name": g["name"], "dong": g["dong"], "built": g.get("built"), "n": g["n"], "date": lt.get("date"),
               "area": lt.get("area")}
        if ours["rental"]:
            row.update(deposit=lt.get("deposit"), monthly=lt.get("monthly"))
        else:
            ppa = [d["price"] / d["area"] for d in mine if d.get("price") and d.get("area")]
            row.update(price=lt.get("price"), ppa=round(st.median(ppa)) if ppa else None)
        rows.append(row)
    if ours["rental"]:
        mons = [d["monthly"] for d in deals if d.get("monthly")]
        deps = [d["deposit"] for d in deals if d.get("deposit") is not None]
        stats = {"n": len(mons), "monthly_med": st.median(mons) if mons else None,
                 "deposit_med": st.median(deps) if deps else None}
    else:
        ppas = [d["price"] / d["area"] for d in deals if d.get("price") and d.get("area")]
        prices = [d["price"] for d in deals if d.get("price")]
        top = max(deals, key=lambda d: d.get("price") or 0) if deals else None
        stats = {"n": len(ppas), "ppa_med": round(st.median(ppas)) if ppas else None,
                 "price_med": st.median(prices) if prices else None,
                 "top": {k: top.get(k) for k in ("name", "area", "price", "date", "built")} if top else None,
                 "built_med": round(st.median([int(g["built"]) for g in rows if str(g.get("built") or "").isdigit()])) if any(str(g.get("built") or "").isdigit() for g in rows) else None}
    return rows[:8], stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--days", type=int, default=3, help="이 날수 안에 만든 결과는 다시 안 받음")
    ap.add_argument("--key")
    a = ap.parse_args()
    env = os.environ.get("CHEONGYAK_ENV")
    if not env or not os.path.exists(env):
        sys.exit("CHEONGYAK_ENV 없음")
    codes = json.load(open(SITE / "data" / "lawd.json", encoding="utf-8"))["codes"]
    rows = {str(r["_row"]): r for r in json.load(open(SITE / "data" / "sheet" / "research.json", encoding="utf-8"))["rows"]}
    amap = json.load(open(SITE / "data" / "assets_map.json", encoding="utf-8"))
    today = dt.date.today()
    OUT.mkdir(parents=True, exist_ok=True)
    done, log = 0, []
    for name, v in amap.items():
        key, r = v.get("key"), rows.get(str(v.get("row")))
        if not key or not r or (a.key and key != a.key):
            continue
        if SKIP_KIND.search(str(r.get("분류", ""))) or (r.get("접수 마감") or "9999") < today.isoformat():
            continue
        f = OUT / f"{key}.json"
        if f.exists() and not a.key:
            age = (today - dt.date.fromisoformat(json.load(open(f)).get("made", "2000-01-01")[:10])).days
            if age < a.days:
                continue
        ours = our_terms(r)
        lawd = lawd_name(str(r.get("지역", "")), codes)
        if not ours or not lawd or (not ours.get("area") and not ours["rental"]):
            log.append(f"{name[:20]}: 건너뜀(주소·면적·가격 못 읽음)")
            continue
        dong = dong_of(str(r.get("지역", "")), lawd)
        kind = "rent" if ours["rental"] else "trade"
        try:
            res, scope = None, ""
            if dong:
                res, scope = query(kind, lawd, dong, ours.get("area"), env), f"{dong}"
            if not res or res.get("count", 0) < 3:
                res, scope = query(kind, lawd, None, ours.get("area"), env), lawd.split()[-1]
        except Exception as e:  # noqa: BLE001
            log.append(f"{name[:20]}: 조회 실패 {str(e)[:80]}")
            continue
        comps, stats = summarize(res, ours)
        json.dump({"key": key, "name": name, "made": dt.datetime.now().isoformat(timespec="minutes"), "kind": kind,
                   "lawd": lawd, "scope": scope, "dong": dong, "months": res.get("months"), "ours": ours,
                   "stats": stats, "comps": comps, "source": res.get("source")},
                  open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log.append(f"{name[:20]}: {scope} {stats.get('n')}건")
        done += 1
        if done >= a.max:
            break
    print(json.dumps({"made": done, "log": log}, ensure_ascii=False))


if __name__ == "__main__":
    main()
