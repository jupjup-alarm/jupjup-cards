"""청약홈 당첨 가점 받기 → site/data/scores.json (2026-11-20 사용자 요청 '단지별 당첨 가점·경쟁률 결과').

API: 한국부동산원_청약홈 청약접수 경쟁률 및 특별공급 신청현황 조회 서비스 (공공데이터포털 15098905)
     https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancScore  (주택형 × 해당/기타지역별 최저·평균·최고 당첨가점)
키:  환경변수 DATA_GO_KR_KEY, 없으면 CHEONGYAK_ENV 파일의 DATA_GO_KR_KEY= 줄 (site/tools/realprice.py 와 같은 키).
     이 데이터셋은 공공데이터포털에서 '활용신청'을 따로 해야 한다 — 안 했으면 401.

대상: site/data/applyhome.json 의 공고 중 당첨자 발표일이 지난 것. 이미 받은 공고는 발표 후 14일까지만 다시 받는다(값이 늦게 채워질 수 있어서).
실행:  python3 site/tools/scores.py            # 받기
       python3 site/tools/scores.py --show NO   # 공고 하나의 원본 응답 보기 (필드 이름 확인용)
GitHub Actions: .github/workflows/scores.yml (저장소 비밀 DATA_GO_KR_KEY 필요)

응답 필드 이름은 공식 문서로 확정하지 못해서, 이름에 LWET/MIN(최저)·AVRG/AVG(평균)·TOP/MAX(최고)·RESIDE…NM(지역)·HOUSE_TY(주택형)
이 들어간 칸을 찾아 쓴다. 처음 받을 때 --show 로 한 번 확인할 것. 추첨·미달 칸은 0 → 저장하지 않음.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = SITE / "data"
OUT = DATA / "scores.json"
API = "https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancScore"
KST = dt.timezone(dt.timedelta(hours=9))


def key():
    k = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if k:
        return k
    p = os.environ.get("CHEONGYAK_ENV")
    if p and Path(p).exists():
        for ln in Path(p).read_text().splitlines():
            if ln.startswith("DATA_GO_KR_KEY="):
                return ln.split("=", 1)[1].strip()
    return ""


def fetch(no, k):
    q = urllib.parse.urlencode({"page": 1, "perPage": 500, "serviceKey": k, "cond[HOUSE_MANAGE_NO::EQ]": str(no)})
    req = urllib.request.Request(f"{API}?{q}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def pick(row, *needles, exclude=()):
    for k, v in row.items():
        K = k.upper()
        if any(n in K for n in needles) and not any(x in K for x in exclude):
            return v
    return None


def num(v):
    try:
        f = float(str(v).replace(",", "").strip())
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def normalize(rows):
    out = []
    for r in rows:
        mn = num(pick(r, "LWET", "LOWEST", "MIN"))
        av = num(pick(r, "AVRG", "AVG"))
        mx = num(pick(r, "TOP", "MAX", "HIGHEST"))
        if not (mn or av or mx):
            continue
        out.append({"type": str(pick(r, "HOUSE_TY", "HOUSE_TYPE", "MODEL") or "").strip(),
                    "area": str(pick(r, "RESIDE_SENM", "RESIDE_NM", "RESIDE", "AREA_NM", exclude=("SECD", "CODE")) or "").strip(),
                    "min": mn, "avg": av, "max": mx})
    return out


def main():
    a = sys.argv[1:]
    k = key()
    if not k:
        print("DATA_GO_KR_KEY가 없어서 건너뜀 (저장소 비밀 또는 CHEONGYAK_ENV)")
        return 0
    if a[:1] == ["--show"]:
        print(json.dumps(fetch(a[1], k), ensure_ascii=False, indent=1)[:4000])
        return 0
    today = dt.datetime.now(KST).date()
    rows = json.loads((DATA / "applyhome.json").read_text())["rows"]
    have = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = []
    for r in rows:
        no, ann = str(r.get("주택관리번호") or ""), (r.get("당첨자 발표") or "")[:10]
        if not no or not ann or ann > today.isoformat():
            continue
        h = have.get(no)
        if h and (h.get("rows") or (today - dt.date.fromisoformat(ann)).days > 14):
            continue
        todo.append(no)
    print(f"받을 공고 {len(todo)}곳")
    n_ok = 0
    for no in todo:
        try:
            js = fetch(no, k)
        except Exception as e:  # 401 = 활용신청 안 됨, 그 밖은 다음 날 다시
            print(f"{no} 실패: {e}")
            if "401" in str(e):
                break
            continue
        data = js.get("data") or []
        norm = normalize(data)
        have[no] = {"fetched": dt.datetime.now(KST).isoformat(timespec="seconds"), "rows": norm,
                    "fields": sorted(data[0].keys()) if data else []}
        n_ok += bool(norm)
        time.sleep(0.3)
    OUT.write_text(json.dumps(have, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(f"가점 있는 공고 {n_ok}곳 저장 → {OUT.relative_to(SITE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
