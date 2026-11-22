"""'줍줍 분석' 2차 글(2026-11-22 사용자 요청: 분양가 vs 시세 · 10·15 대책 전후 · 정부 발표 vs 실거래 · 입주 물량과 전셋값 · 8·13 대책)
에 쓸 국토부 실거래가·청약홈 원자료 받기. 키 = 저장소 비밀 DATA_GO_KR_KEY (realprice.py·analysis_data.py 와 같은 키, 실거래 활용신청 2026-10-29).

받는 것
  - 국토부 아파트 매매 실거래 상세(RTMSDataSvcAptTradeDev): 수도권 시군구 × 2025-01 ~ 이번 달 → rt_trade.json.gz (건별, 해제 거래 제외)
  - 국토부 아파트 전월세(RTMSDataSvcAptRent): 같은 범위 → rt_rent.json.gz (건별 — 보증금·월세 만원, 신규/갱신)
  - 청약홈 주택형별 분양가(getAPTLttotPblancMdl): raw.json 의 수도권 APT 공고 → mdl.json
  - 청약홈 APT 분양정보 2022-01-01 이후 전국(입주예정월 MVN_PREARNGE_YM) → apt_hist.json
행정구역 개편(인천 2026-07 제물포·영종·서해·검단구, 화성 4개 구, 부천 3개 구)으로 예전 코드와 새 코드를 둘 다 받고 같은 거래는 하나로 합친다.
실행: DATA_GO_KR_KEY=… python3 site/tools/analysis_rt.py   (GitHub Actions: .github/workflows/analysis-rt.yml)
"""
import datetime as dt, gzip, json, os, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "data" / "analysis"
RT = "https://apis.data.go.kr/1613000/"
EP = {"trade": "RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev", "rent": "RTMSDataSvcAptRent/getRTMSDataSvcAptRent"}
OLD = {"28110": "인천 중구(옛)", "28140": "인천 동구(옛)", "28260": "인천 서구(옛)", "41590": "경기 화성시(옛)", "41190": "경기 부천시(옛)"}


def key():
    k = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not k:
        sys.exit("DATA_GO_KR_KEY 없음")
    return k


def months(start="202501"):
    y, m = int(start[:4]), int(start[4:])
    t = dt.date.today()
    out = []
    while (y, m) <= (t.year, t.month):
        out.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def rt(kind, lawd, ym, k):
    rows, page = [], 1
    while True:
        q = urllib.parse.urlencode({"serviceKey": k, "LAWD_CD": lawd, "DEAL_YMD": ym, "numOfRows": "1000", "pageNo": str(page)})
        for t in range(6):
            try:
                raw = urllib.request.urlopen(RT + EP[kind] + "?" + q, timeout=40).read()
                root = ET.fromstring(raw)
                break
            except Exception as ex:
                if t == 5:
                    print(f"  실패 {kind} {lawd} {ym}: {type(ex).__name__}")
                    return rows, False
                time.sleep(2 + 3 * t)
        code = root.findtext(".//resultCode") or ""
        if code not in ("00", "000"):
            print(f"  API 오류 {code} {kind} {lawd} {ym}: {root.findtext('.//resultMsg')}")
            return rows, False
        items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
        rows += items
        total = int(root.findtext(".//totalCount") or 0)
        if page * 1000 >= total or not items:
            return rows, True
        page += 1


def f(s):
    s = (s or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def odc(path, k, **cond):
    out, page = [], 1
    while True:
        q = {"page": page, "perPage": 1000, "serviceKey": k, **cond}
        req = urllib.request.Request("https://api.odcloud.kr/api/" + path + "?" + urllib.parse.urlencode(q), headers={"Accept": "application/json"})
        for t in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    j = json.loads(r.read().decode("utf-8"))
                break
            except Exception:
                if t == 2:
                    raise
                time.sleep(3)
        data = j.get("data") or []
        out += data
        if len(out) >= (j.get("matchCount") or j.get("totalCount") or 0) or not data:
            return out
        page += 1


def main():
    k = key()
    codes = dict(json.loads((SITE / "data" / "lawd.json").read_text())["codes"])
    lawd = {}
    for nm, c in codes.items():
        lawd.setdefault(c, nm.replace("화성특례시", "화성시"))
    lawd.update(OLD)
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else ["trade", "rent", "mdl", "hist"]
    MS = months()
    fails = []
    for kind in ("trade", "rent"):
        if kind not in only:
            continue
        seen, out = set(), []
        for c, nm in lawd.items():
            for ym in MS:
                items, ok = rt(kind, c, ym, k)
                if not ok:
                    fails.append(f"{kind} {c} {ym}")
                for it in items:
                    if kind == "trade" and (it.get("cdealType") or "").strip() == "O":
                        continue
                    day = int(f"{it.get('dealYear')}{int(it.get('dealMonth') or 0):02d}{int(it.get('dealDay') or 0):02d}")
                    base = [nm, it.get("umdNm", ""), it.get("aptNm", ""), round(f(it.get("excluUseAr")), 2), day, int(f(it.get("buildYear"))), int(f(it.get("floor")))]
                    if kind == "trade":
                        row = base + [int(f(it.get("dealAmount"))), 1 if "직거래" in (it.get("dealingGbn") or "") else 0]
                    else:
                        row = base + [int(f(it.get("deposit"))), int(f(it.get("monthlyRent"))), (it.get("contractType") or "")[:2]]
                    sig = tuple(row[1:])   # 옛 코드·새 코드 겹침 제거 (시군구 이름 빼고 같은 거래)
                    if sig in seen:
                        continue
                    seen.add(sig)
                    out.append(row)
                time.sleep(0.05)
            print(f"{kind} {c} {nm} 누적 {len(out)}", flush=True)
        cols = ["sgg", "dong", "apt", "area", "date", "built", "floor"] + (["price_man", "direct"] if kind == "trade" else ["deposit_man", "monthly_man", "contract"])
        with gzip.open(OUT / f"rt_{kind}.json.gz", "wt", encoding="utf-8") as g:
            json.dump({"fetched": dt.date.today().isoformat(), "months": MS, "cols": cols, "rows": out}, g, ensure_ascii=False, separators=(",", ":"))
        print(f"{kind}: {len(out)}건 저장")
    if "mdl" in only:
        raw = json.loads((OUT / "raw.json").read_text())
        mdl = {}
        for a in raw["apt"]:
            if str(a.get("SUBSCRPT_AREA_CODE")) in ("100", "400", "410"):
                mdl[a["HOUSE_MANAGE_NO"]] = odc("ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancMdl", k, **{"cond[HOUSE_MANAGE_NO::EQ]": a["HOUSE_MANAGE_NO"]})
                time.sleep(0.15)
        (OUT / "mdl.json").write_text(json.dumps(mdl, ensure_ascii=False))
        print(f"분양가(주택형) {len(mdl)}개 공고")
    if "hist" in only:
        h = odc("ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail", k, **{"cond[RCRIT_PBLANC_DE::GTE]": "2022-01-01"})
        keep = ["HOUSE_MANAGE_NO", "HOUSE_NM", "HOUSE_SECD_NM", "HOUSE_DTL_SECD_NM", "RENT_SECD_NM", "SUBSCRPT_AREA_CODE_NM", "HSSPLY_ADRES", "TOT_SUPLY_HSHLDCO", "RCRIT_PBLANC_DE", "MVN_PREARNGE_YM"]
        (OUT / "apt_hist.json").write_text(json.dumps([{x: a.get(x) for x in keep} for a in h], ensure_ascii=False))
        print(f"분양정보 2022~ {len(h)}건")
    if fails:
        print("실패:", len(fails), fails[:20])


if __name__ == "__main__":
    main()
