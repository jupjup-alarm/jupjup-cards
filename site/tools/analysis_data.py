"""'줍줍 분석' 글에 쓸 청약홈 원자료 받기 (2026-11-22 사용자 요청: 분석 탭·분석 글 4편).

받는 것 (공공데이터포털 odcloud, 키 = 저장소 비밀 DATA_GO_KR_KEY — scores.py 와 같은 키):
  - ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail      APT 분양정보 (올해 모집공고)
  - ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancDetail   무순위·잔여세대 (올해)
  - ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet      APT 순위별 경쟁률 (1·2순위 전부)
  - ApplyhomeInfoCmpetRtSvc/v1/getRemndrLttotPblancCmpet   무순위 경쟁률
  - ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancScore      당첨 가점
범위: 모집공고일 SINCE(기본 2026-01-01) 이후, 수도권(서울 100·인천 400·경기 410) + 전국 목록은 공고 정보만.
출력: site/data/analysis/raw.json  (원본 필드 그대로 — 글의 숫자는 이 파일에서 계산하고 검증한다)
실행: python3 site/tools/analysis_data.py [--since 2026-01-01]
GitHub Actions: .github/workflows/analysis-data.yml (이 파일이 바뀌어 푸시되면 + 매주 월요일)
"""
import datetime as dt, json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "data" / "analysis" / "raw.json"
BASE = "https://api.odcloud.kr/api/"
METRO = {"100", "400", "410"}


def key():
    k = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not k:
        sys.exit("DATA_GO_KR_KEY 없음")
    return k


def call(path, k, **cond):
    out, page = [], 1
    while True:
        q = {"page": page, "perPage": 1000, "serviceKey": k, **cond}
        req = urllib.request.Request(BASE + path + "?" + urllib.parse.urlencode(q), headers={"Accept": "application/json"})
        for t in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    j = json.loads(r.read().decode("utf-8"))
                break
            except Exception as e:
                if t == 2:
                    raise
                time.sleep(3)
        data = j.get("data") or []
        out += data
        if len(out) >= (j.get("matchCount") or j.get("totalCount") or 0) or not data:
            return out
        page += 1


def main():
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else "2026-01-01"
    k = key()
    apt = call("ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail", k, **{"cond[RCRIT_PBLANC_DE::GTE]": since})
    rem = call("ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancDetail", k, **{"cond[RCRIT_PBLANC_DE::GTE]": since})
    print(f"APT {len(apt)} · 무순위 {len(rem)}")
    today = dt.date.today().isoformat()
    cm, sc, rcm = {}, {}, {}
    for a in apt:
        no = a["HOUSE_MANAGE_NO"]
        if str(a.get("SUBSCRPT_AREA_CODE")) not in METRO or (a.get("PRZWNER_PRESNATN_DE") or "9") > today and (a.get("RCEPT_ENDDE") or "9") > today:
            continue
        cm[no] = call("ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet", k, **{"cond[HOUSE_MANAGE_NO::EQ]": no})
        sc[no] = call("ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancScore", k, **{"cond[HOUSE_MANAGE_NO::EQ]": no})
        time.sleep(0.2)
    for a in rem:
        no = a["HOUSE_MANAGE_NO"]
        if str(a.get("SUBSCRPT_AREA_CODE")) not in METRO or (a.get("RCEPT_ENDDE") or "9") > today:
            continue
        rcm[no] = call("ApplyhomeInfoCmpetRtSvc/v1/getRemndrLttotPblancCmpet", k, **{"cond[HOUSE_MANAGE_NO::EQ]": no})
        time.sleep(0.2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"fetched": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds"), "since": since,
                               "apt": apt, "remndr": rem, "cmpet": cm, "score": sc, "remndr_cmpet": rcm}, ensure_ascii=False))
    print(f"경쟁률 {len(cm)} · 가점 {sum(1 for v in sc.values() if v)} · 무순위 경쟁률 {len(rcm)} → {OUT}")


if __name__ == "__main__":
    main()
