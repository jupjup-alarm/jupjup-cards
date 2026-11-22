"""줍줍 분석 글 숫자 계산 — site/data/analysis/raw.json → 표준 출력(JSON). 글 원고의 숫자는 이 결과에서만 가져온다.
정의:
  · 대상: 모집공고일 2026-01-01 이후, 수도권(서울 100·인천 400·경기 410) APT 분양주택(민영·국민·신혼희망타운, 임대 제외), 청약홈 경쟁률 공개된 단지
  · 주택형 최종 미달: 그 주택형의 마지막 접수 행(2순위가 있으면 2순위, 기타지역>기타경기>해당지역 순)의 경쟁률이 △(미달 세대)
  · 1순위 마감: 2순위 접수 행이 없고 1순위 마지막 행 경쟁률이 숫자인 주택형 → 모든 주택형이 그러면 '전 주택형 1순위 마감'
  · 1순위 평균 경쟁률: 1순위 접수 합(해당+기타) ÷ 주택형별 공급 세대 합 (청약홈 경쟁률과 계산 방식이 다를 수 있어 '계산값')
"""
import json, re, sys, collections
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "analysis" / "raw.json"
METRO = {"100": "서울", "400": "인천", "410": "경기"}
ORDER = {"해당지역": 0, "기타경기": 1, "기타지역": 2}


def n(v):
    t = re.sub(r"[^\d.]", "", str(v or ""))
    return float(t) if t else 0.0


def short(v):
    m = re.search(r"△\s*([\d,]+)", str(v or ""))
    return int(m.group(1).replace(",", "")) if m else None


def sigungu(addr):
    p = (addr or "").split()
    if p and p[0].startswith(("서울", "인천")):   # 광역시는 구·군
        for w in p[1:4]:
            if w.endswith(("구", "군")):
                return w
    for w in p[1:4]:
        if w.endswith(("시", "군")):
            return w.replace("특례시", "시")
    for w in p[1:4]:
        if w.endswith("구"):
            return w
    return p[1] if len(p) > 1 else ""


def norm(s):
    s = re.sub(r"\((?:[^)]*차|[^)]*취소[^)]*|[^)]*조합원[^)]*|[^)]*회차|보류지)\)|\[.*?\]", "", s or "")   # (2차)·(조합원 취소분) 등만 지우고 (AB23BL) 같은 블록은 남김
    s = re.sub(r"\d+차|조합원.*|잔여.*|무순위.*|취소.*|계약.*", "", s)
    return re.sub(r"[\s·,.-]", "", s)


def compute():
    d = json.loads(RAW.read_text())
    apt = {a["HOUSE_MANAGE_NO"]: a for a in d["apt"]}
    res = []
    for no, rows in d["cmpet"].items():
        a = apt.get(no)
        if not a or not rows or str(a.get("SUBSCRPT_AREA_CODE")) not in METRO:
            continue
        if a.get("RENT_SECD_NM") != "분양주택":   # 임대·분양전환임대 제외
            continue
        types = collections.defaultdict(list)
        for r in rows:
            types[r["HOUSE_TY"].strip()].append(r)
        sup = req1 = 0
        tinfo = []
        for ty, rs in types.items():
            s = int(n(rs[0]["SUPLY_HSHLDCO"]))
            r1 = [r for r in rs if int(r["SUBSCRPT_RANK_CODE"]) == 1]
            r2 = [r for r in rs if int(r["SUBSCRPT_RANK_CODE"]) == 2 and str(r.get("CMPET_RATE") or "").strip() not in ("-", "")]   # 1순위 마감이면 2순위 행이 "-"로 옴
            last = sorted(r2 or r1, key=lambda r: ORDER.get(r.get("RESIDE_SENM"), 3))[-1]
            last1 = sorted(r1, key=lambda r: ORDER.get(r.get("RESIDE_SENM"), 3))[-1] if r1 else None
            fin_short = short(last["CMPET_RATE"])
            close1 = bool(last1) and short(last1["CMPET_RATE"]) is None and not r2
            sup += s; req1 += sum(int(n(r["REQ_CNT"])) for r in r1)
            tinfo.append({"ty": ty, "sup": s, "short": fin_short or 0, "close1": close1, "under": fin_short is not None})
        if not sup:
            continue
        res.append({"no": no, "name": a["HOUSE_NM"], "sido": METRO[str(a["SUBSCRPT_AREA_CODE"])], "sgg": sigungu(a.get("HSSPLY_ADRES")),
                    "date": a["RCRIT_PBLANC_DE"], "kind": a.get("HOUSE_DTL_SECD_NM"), "sup": sup, "req1": req1, "rate1": round(req1 / sup, 2),
                    "under": any(t["under"] for t in tinfo), "short": sum(t["short"] for t in tinfo),
                    "all_close1": all(t["close1"] for t in tinfo), "ntypes": len(tinfo), "under_types": sum(t["under"] for t in tinfo)})
    out = {"n": len(res), "period": [min(r["date"] for r in res), max(r["date"] for r in res)]}
    # 1) 미달
    by_sido = collections.Counter(r["sido"] for r in res); un_sido = collections.Counter(r["sido"] for r in res if r["under"])
    by_sgg = collections.Counter((r["sido"], r["sgg"]) for r in res); un_sgg = collections.Counter((r["sido"], r["sgg"]) for r in res if r["under"])
    sh_sgg = collections.Counter(); [sh_sgg.update({(r["sido"], r["sgg"]): r["short"]}) for r in res]
    out["under"] = {"total": sum(r["under"] for r in res), "all_close1": sum(r["all_close1"] for r in res), "short_sum": sum(r["short"] for r in res),
                    "by_sido": {k: [un_sido[k], v] for k, v in by_sido.items()},
                    "sgg": sorted([[f"{k[0]} {k[1]}", un_sgg[k], v, sh_sgg[k]] for k, v in by_sgg.items()], key=lambda x: -x[3])[:12],
                    "top_short": sorted([[r["name"], r["sido"] + " " + r["sgg"], r["short"], r["sup"], r["rate1"], r["date"], r["no"]] for r in res if r["short"]], key=lambda x: -x[2])[:8],
                    "close1_list": [[r["name"], r["sido"] + " " + r["sgg"], r["rate1"], r["sup"], r["date"], r["no"]] for r in res if r["all_close1"]],
                    "rate_over1_but_under": [[r["name"], r["rate1"], r["short"], r["no"]] for r in res if r["under"] and r["rate1"] >= 1]}
    # 2) 1순위 마감 → 무순위 다시
    rem = [x for x in d["remndr"] if str(x.get("SUBSCRPT_AREA_CODE")) in METRO]
    rem_by = collections.defaultdict(list)
    for x in rem:
        rem_by[norm(x["HOUSE_NM"])].append(x)
    def later(r):
        k = norm(r["name"])
        hits = []
        for rk, xs in rem_by.items():
            if k and rk and (k in rk or rk in k) and min(len(k), len(rk)) >= 4:
                hits += [x for x in xs if x["RCRIT_PBLANC_DE"] > r["date"]]
        return hits
    c1 = [r for r in res if r["all_close1"]]; un = [r for r in res if r["under"]]
    out["rem"] = {"remndr_metro": len(rem), "close1": len(c1), "close1_rem": [[r["name"], r["sido"] + " " + r["sgg"], r["rate1"], r["date"], [(x["HOUSE_NM"], x["RCRIT_PBLANC_DE"], x.get("TOT_SUPLY_HSHLDCO")) for x in later(r)], r["no"]] for r in c1 if later(r)],
                  "under": len(un), "under_rem": sum(1 for r in un if later(r)),
                  "old_close1": sum(1 for r in c1 if r["date"] <= "2026-09-30"), "old_close1_rem": sum(1 for r in c1 if r["date"] <= "2026-09-30" and later(r))}
    # 3) 가점
    sc = []
    for no, rows in d["score"].items():
        a = apt.get(no)
        if not a or str(a.get("SUBSCRPT_AREA_CODE")) not in METRO:
            continue
        for r in rows:
            lo = n(r.get("LWET_SCORE")); hi = n(r.get("TOP_SCORE")); av = n(r.get("AVRG_SCORE"))
            if lo <= 0:
                continue
            ty = r["HOUSE_TY"].strip(); m = re.match(r"0*(\d+)", ty); sq = int(m.group(1)) if m else 0
            sc.append({"no": no, "name": a["HOUSE_NM"], "sido": METRO[str(a["SUBSCRPT_AREA_CODE"])], "sgg": sigungu(a.get("HSSPLY_ADRES")), "ty": ty, "sq": sq,
                       "area": r.get("RESIDE_SENM"), "min": lo, "avg": av, "max": hi, "date": a["RCRIT_PBLANC_DE"]})
    def band(sq): return "59㎡ 이하" if sq < 60 else ("60~84㎡" if sq <= 85 else "85㎡ 초과")
    agg = collections.defaultdict(list)
    for s in sc:
        if s["area"] == "해당지역":
            agg[(s["sido"], band(s["sq"]))].append(s)
    out["score"] = {"rows": len(sc), "complexes": len({s["no"] for s in sc}),
                    "sido_band": {f"{k[0]}|{k[1]}": {"n": len({x['no'] for x in v}), "min_of_min": min(x["min"] for x in v), "median_min": sorted(x["min"] for x in v)[len(v)//2], "max_min": max(x["min"] for x in v)} for k, v in agg.items()},
                    "seoul84": sorted([[s["name"], s["sgg"], s["ty"], s["area"], s["min"], s["avg"], s["max"], s["date"], s["no"]] for s in sc if s["sido"] == "서울" and 80 <= s["sq"] <= 85], key=lambda x: -x[4]),
                    "top_min": sorted([[s["name"], s["sido"] + " " + s["sgg"], s["ty"], s["area"], s["min"], s["no"]] for s in sc if s["area"] == "해당지역"], key=lambda x: -x[4])[:10]}
    # 4) 경쟁률 상하위
    rr = sorted(res, key=lambda r: -r["rate1"])
    out["rank"] = {"top": [[r["name"], r["sido"] + " " + r["sgg"], r["rate1"], r["sup"], r["req1"], r["date"], r["no"]] for r in rr[:10]],
                   "bottom": [[r["name"], r["sido"] + " " + r["sgg"], r["rate1"], r["sup"], r["req1"], r["date"], r["no"]] for r in rr[::-1][:10]],
                   "median": rr[len(rr)//2]["rate1"], "over10": sum(r["rate1"] >= 10 for r in rr), "below1": sum(r["rate1"] < 1 for r in rr),
                   "by_sido_median": {k: sorted(r["rate1"] for r in rr if r["sido"] == k)[len([1 for r in rr if r["sido"] == k])//2] for k in by_sido}}
    return out, res, sc, later, d


def main():
    print(json.dumps(compute()[0], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
