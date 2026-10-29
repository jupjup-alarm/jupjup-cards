#!/usr/bin/env python3
"""국토교통부 실거래가 공개 API(공공데이터포털)로 비교 단지 시세를 찾는다 (2026-10-29 사용자가 활용신청).

키: CHEONGYAK_ENV 파일(권한 600)의 DATA_GO_KR_KEY — '청약노트 블로그 운영' 시트 '키' 탭 B8.
    값을 출력·커밋하지 않는다. 이 스크립트도 키를 화면에 찍지 않는다.

예)
  # 분당구 정자동 84㎡ 안팎 아파트 매매, 최근 6개월
  python3 site/tools/realprice.py trade 41135 --dong 정자동 --area 84 --months 6
  # 같은 동 아파트 전월세(임대 비교용)
  python3 site/tools/realprice.py rent 41135 --dong 정자동 --area 59
  # 오피스텔·연립다세대 전월세: offi / rowhouse
  python3 site/tools/realprice.py offi 41590 --dong 영천동 --area 26

출력: JSON (건별 거래, 단지별 요약). 해제된 거래(cdealType=O)는 뺀다.
LAWD_CD(시군구 5자리)는 data/lawd.json 또는 --lawd 로. 새로 생긴 구(화성·인천·부천 등)는
  한 번 조회해 결과의 동 이름이 맞는지 확인한 뒤 data/lawd.json에 추가한다.
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

BASE = "https://apis.data.go.kr/1613000/"
EP = {
    "trade": "RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",   # 아파트 매매 실거래가 상세
    "rent": "RTMSDataSvcAptRent/getRTMSDataSvcAptRent",             # 아파트 전월세
    "offi": "RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",           # 오피스텔 전월세
    "rowhouse": "RTMSDataSvcRHRent/getRTMSDataSvcRHRent",           # 연립다세대 전월세
    "house": "RTMSDataSvcSHRent/getRTMSDataSvcSHRent",              # 단독/다가구 전월세
}
NAME = {"trade": "aptNm", "rent": "aptNm", "offi": "offiNm", "rowhouse": "mhouseNm", "house": None}


def key():
    p = os.environ.get("CHEONGYAK_ENV")
    if not p or not os.path.exists(p):
        sys.exit("CHEONGYAK_ENV 파일이 없어요 (DATA_GO_KR_KEY=… 한 줄, 권한 600)")
    for ln in open(p, encoding="utf-8"):
        if ln.startswith("DATA_GO_KR_KEY="):
            return ln.split("=", 1)[1].strip()
    sys.exit("CHEONGYAK_ENV 파일에 DATA_GO_KR_KEY가 없어요")


def months(n, end=None):
    d = end or dt.date.today()
    y, m = d.year, d.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if not m:
            y, m = y - 1, 12
    return out


def num(s):
    s = (s or "").replace(",", "").strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def fetch(kind, lawd, ym, k):
    rows, page = [], 1
    while True:
        q = urllib.parse.urlencode({"serviceKey": k, "LAWD_CD": lawd, "DEAL_YMD": ym, "numOfRows": "1000", "pageNo": str(page)})
        for t in range(3):
            try:
                raw = urllib.request.urlopen(BASE + EP[kind] + "?" + q, timeout=30).read()
                break
            except Exception as ex:  # 일시 오류는 다시
                if t == 2:
                    raise SystemExit(f"API 요청 실패 ({kind} {lawd} {ym}): {type(ex).__name__}")
                time.sleep(2)
        root = ET.fromstring(raw)
        code = root.findtext(".//resultCode") or ""
        if code not in ("00", "000"):
            msg = root.findtext(".//resultMsg") or root.findtext(".//returnAuthMsg") or "알 수 없는 오류"
            raise SystemExit(f"API 오류 {code}: {msg} — 활용신청 직후면 1~2시간 뒤 다시")
        items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
        rows += items
        total = int(root.findtext(".//totalCount") or 0)
        if page * 1000 >= total or not items:
            return rows
        page += 1


def norm(kind, it):
    """API 한 건 → 공통 형식. 금액은 원 단위."""
    nm = it.get(NAME[kind] or "", "") if NAME[kind] else ""
    area = num(it.get("excluUseAr") or it.get("totalFloorAr"))
    d = f"{it.get('dealYear')}.{int(it.get('dealMonth') or 0):02d}.{int(it.get('dealDay') or 0):02d}"
    out = {"name": nm, "dong": it.get("umdNm", ""), "jibun": it.get("jibun", ""), "area": area,
           "floor": it.get("floor", ""), "built": it.get("buildYear", ""), "date": d}
    if kind == "trade":
        if (it.get("cdealType") or "").strip() == "O":
            return None  # 해제된 거래
        out["price"] = (num(it.get("dealAmount")) or 0) * 10_000
    else:
        out["deposit"] = (num(it.get("deposit")) or 0) * 10_000
        out["monthly"] = (num(it.get("monthlyRent")) or 0) * 10_000
        out["contract"] = it.get("contractType", "")  # 신규·갱신
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=EP)
    ap.add_argument("lawd", help="시군구 5자리 (예 41135) 또는 data/lawd.json의 이름 (예 '경기 성남시 분당구')")
    ap.add_argument("--dong", help="법정동 이름 (예 정자동) — 여러 개면 쉼표")
    ap.add_argument("--name", help="단지 이름 일부 (예 파크뷰)")
    ap.add_argument("--area", type=float, help="전용면적 기준 ㎡ (±--tol)")
    ap.add_argument("--tol", type=float, default=10)
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--monthly-only", action="store_true", help="전월세 중 월세만")
    ap.add_argument("--jeonse-only", action="store_true", help="전월세 중 전세만")
    a = ap.parse_args()
    lawd = a.lawd
    if not re.fullmatch(r"\d{5}", lawd):
        tbl = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "lawd.json"), encoding="utf-8"))
        lawd = tbl.get(lawd) or sys.exit(f"data/lawd.json에 '{a.lawd}'가 없어요 — 5자리 코드를 직접 넣으세요")
    k = key()
    dongs = [x.strip() for x in (a.dong or "").split(",") if x.strip()]
    deals = []
    for ym in months(a.months):
        for it in fetch(a.kind, lawd, ym, k):
            r = norm(a.kind, it)
            if not r:
                continue
            if dongs and r["dong"] not in dongs:
                continue
            if a.name and a.name not in r["name"]:
                continue
            if a.area and (r["area"] is None or abs(r["area"] - a.area) > a.tol):
                continue
            if a.kind != "trade":
                if a.monthly_only and not r["monthly"]:
                    continue
                if a.jeonse_only and r["monthly"]:
                    continue
            deals.append(r)
    deals.sort(key=lambda r: r["date"], reverse=True)
    by = {}
    for r in deals:
        g = by.setdefault((r["name"], r["dong"]), {"name": r["name"], "dong": r["dong"], "built": r["built"], "n": 0, "latest": r})
        g["n"] += 1
    out = {"source": "국토교통부 실거래가 공개시스템 (공공데이터포털 API)", "kind": a.kind, "lawd": lawd,
           "months": months(a.months)[::-1], "filters": {"dong": dongs, "name": a.name, "area": a.area, "tol": a.tol},
           "count": len(deals), "complexes": sorted(by.values(), key=lambda g: -g["n"])[:20], "deals": deals[:60]}
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
