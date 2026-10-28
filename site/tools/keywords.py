"""공고 페이지 키워드 수치 조회 → site/data/keywords/{key}.json

네이버 검색광고 키워드도구(월간 검색량) + NAVER API HUB 블로그 검색(문서 수).
청약노트 블로그(jupjup-alarm/cheongyak-note note/keywords.py)와 같은 키·같은 방식.

사용:
    python3 site/tools/keywords.py            # 7일 넘은 것·없는 것만
    python3 site/tools/keywords.py 2026910275 lh0000061190   # 지정한 공고만 (기한 무시)
    python3 site/tools/keywords.py --site     # 목록 페이지용 일반 키워드 (_site.json)

키: 환경변수 CHEONGYAK_ENV 경로의 KEY=VALUE 파일 (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
    SEARCHAD_API_KEY, SEARCHAD_SECRET_KEY, SEARCHAD_CUSTOMER_ID). 값은 청약노트 블로그 운영 시트 '키' 탭.
    파일은 세션 임시 폴더에만 두고 저장소에 올리지 않는다. 키 값은 출력하지 않는다.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

SITE = Path(__file__).resolve().parents[1]
APT = SITE / "data" / "apt"
OUT = SITE / "data" / "keywords"
HUB = "https://naverapihub.apigw.ntruss.com"
SEARCHAD = "https://api.searchad.naver.com"
FRESH_DAYS = 7

# 공고 유형·상태별로 단지명 뒤에 붙여 볼 말 (청약노트 '키워드 패턴' 탭을 사이트용으로 줄인 것)
SUFFIX = {
    "sale": ["", "분양가", "청약", "청약 일정", "모델하우스", "평면도", "경쟁률", "당첨자 발표", "당첨 가점",
             "입주", "전매제한", "실거주 의무", "특별공급", "분양", "시세"],
    "mujeonwi": ["", "무순위", "줍줍", "분양가", "청약", "청약 일정", "경쟁률", "당첨자 발표", "자격", "실거주 의무",
                 "잔여세대", "모델하우스", "평면도", "시세"],
    "rental": ["", "보증금", "월세", "임대료", "입주자격", "모집공고", "경쟁률", "당첨자 발표", "청약", "평면도", "소득기준"],
    "pre": ["", "분양", "분양가", "분양 일정", "청약", "청약 일정", "모델하우스", "평면도", "시세", "재건축"],
}
SITE_KEYWORDS = ["청약 일정", "이번주 청약", "이번주 청약 일정", "다음주 청약 일정", "11월 청약 일정", "12월 청약 일정",
                 "아파트 청약 일정", "무순위 청약", "줍줍 청약", "줍줍", "무순위 줍줍", "잔여세대",
                 "서울 청약", "경기 청약", "인천 청약", "서울 아파트 청약", "경기도 청약", "인천 아파트 분양",
                 "민간분양", "공공분양", "신혼희망타운", "공공임대", "행복주택", "청약 경쟁률", "청약홈",
                 "분양 일정", "아파트 분양 일정", "로또 청약"]


def load_env():
    p = os.environ.get("CHEONGYAK_ENV")
    env = {}
    if p and Path(p).exists():
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "SEARCHAD_API_KEY", "SEARCHAD_SECRET_KEY", "SEARCHAD_CUSTOMER_ID"):
        env.setdefault(k, os.environ.get(k, ""))
    miss = [k for k, v in env.items() if not v]
    if miss:
        sys.exit("키가 없어요: " + ", ".join(miss) + " (CHEONGYAK_ENV 파일 또는 환경변수)")
    return env


def nospace(s):
    return re.sub(r"\s+", "", s).upper()


def clean(s):
    """키워드도구는 공백·기호가 있으면 400 → 한글·영문·숫자만."""
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).upper()


def num(v):
    """검색광고는 10 미만을 '< 10'으로 준다 → 5."""
    if isinstance(v, str):
        return 5 if "<" in v else int(re.sub(r"\D", "", v) or 0)
    return int(v or 0)


def searchad(env, hints):
    """hintKeywords 최대 5개. 공백 없는 키워드로 보내고 연관 키워드 전체를 돌려받는다."""
    ts = str(int(time.time() * 1000))
    uri = "/keywordstool"
    sig = base64.b64encode(hmac.new(env["SEARCHAD_SECRET_KEY"].encode(), f"{ts}.GET.{uri}".encode(),
                                    hashlib.sha256).digest()).decode()
    for attempt in range(3):
        r = requests.get(SEARCHAD + uri, params={"hintKeywords": ",".join(clean(h) for h in hints), "showDetail": 1},
                         headers={"X-Timestamp": ts, "X-API-KEY": env["SEARCHAD_API_KEY"],
                                  "X-Customer": env["SEARCHAD_CUSTOMER_ID"], "X-Signature": sig}, timeout=20)
        if r.status_code == 429:
            time.sleep(2 + attempt * 2)
            ts = str(int(time.time() * 1000))
            sig = base64.b64encode(hmac.new(env["SEARCHAD_SECRET_KEY"].encode(), f"{ts}.GET.{uri}".encode(),
                                            hashlib.sha256).digest()).decode()
            continue
        r.raise_for_status()
        return r.json().get("keywordList", [])
    r.raise_for_status()
    return []


def blog_total(env, kw):
    r = requests.get(f"{HUB}/search/v1/blog", params={"query": kw, "display": 1}, timeout=15,
                     headers={"X-NCP-APIGW-API-KEY-ID": env["NAVER_CLIENT_ID"], "X-NCP-APIGW-API-KEY": env["NAVER_CLIENT_SECRET"]})
    r.raise_for_status()
    return r.json().get("total")


def names_of(n):
    """검색에 쓰일 만한 단지 이름들. 블록·지구·괄호를 뺀 짧은 이름도 넣는다."""
    out = []
    for s in list(n.get("search_names") or []) + [n.get("complex"), n.get("title")]:
        if not s:
            continue
        s = re.sub(r"\(.*?\)", " ", s)
        s = re.sub(r"\s*(무순위|임의공급|추가모집|본청약|입주자\s*모집|모집공고|공고|잔여세대|\d+차)\s*$", "", s).strip()
        for v in (s, re.sub(r"\s*[A-Z]{0,2}-?\d+[A-Z]?\s*블록$", "", s).strip(), re.sub(r"\s*(공공주택지구|지구)\s*", " ", s).strip()):
            v = re.sub(r"\s+", " ", v).strip()
            if len(nospace(v)) >= 3 and v not in out:
                out.append(v)
    return out[:4]


def group_of(n):
    if n.get("source") == "pre" or str(n.get("key", "")).startswith("pre-"):
        return "pre"
    if n.get("kind") == "rental":
        return "rental"
    if n.get("kind") == "mujeonwi":
        return "mujeonwi"
    return "sale"


def lookup(env, keywords, related_core=None):
    """키워드 목록의 월간 검색량. related_core가 있으면 그 말이 들어간 연관 키워드도 모은다."""
    vol, related = {}, {}
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        try:
            rows = searchad(env, batch)
        except requests.RequestException as e:
            print(f"  검색광고 오류: {str(e)[:100]}", file=sys.stderr)
            continue
        by = {clean(r["relKeyword"]): r for r in rows}
        for kw in batch:
            r = by.get(clean(kw))
            vol[kw] = (num(r["monthlyPcQcCnt"]), num(r["monthlyMobileQcCnt"])) if r else (0, 0)
        if related_core:
            for r in rows:
                rk = r["relKeyword"]
                if any(nospace(c) in nospace(rk) for c in related_core):
                    related[rk] = num(r["monthlyPcQcCnt"]) + num(r["monthlyMobileQcCnt"])
        time.sleep(0.4)
    return vol, related


def run_notice(env, n):
    names = names_of(n)
    cands = []
    for nm in names:
        for suf in SUFFIX[group_of(n)]:
            kw = f"{nm} {suf}".strip()
            if kw not in cands:
                cands.append(kw)
    vol, related = lookup(env, cands, related_core=names)
    rows = [{"kw": k, "pc": v[0], "mo": v[1], "total": v[0] + v[1]} for k, v in vol.items()]
    rows.sort(key=lambda r: -r["total"])
    for r in rows[:8]:
        if r["total"] >= 20:
            try:
                r["docs"] = blog_total(env, r["kw"])
            except requests.RequestException:
                pass
            time.sleep(0.2)
    known = {nospace(r["kw"]) for r in rows}
    rel = [{"kw": k, "total": v} for k, v in sorted(related.items(), key=lambda x: -x[1]) if nospace(k) not in known and v >= 20][:20]
    return {"key": n["key"], "fetched": dt.date.today().isoformat(), "names": names, "group": group_of(n),
            "rows": rows, "related": rel}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    env = load_env()
    OUT.mkdir(parents=True, exist_ok=True)
    if "--site" in sys.argv:
        vol, related = lookup(env, SITE_KEYWORDS, related_core=["청약", "분양", "줍줍", "무순위"])
        rows = sorted([{"kw": k, "pc": v[0], "mo": v[1], "total": v[0] + v[1]} for k, v in vol.items()], key=lambda r: -r["total"])
        rel = [{"kw": k, "total": v} for k, v in sorted(related.items(), key=lambda x: -x[1])][:40]
        (OUT / "_site.json").write_text(json.dumps({"fetched": dt.date.today().isoformat(), "rows": rows, "related": rel},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"_site: {len(rows)}개, 1위 {rows[0]['kw']} {rows[0]['total']:,}")
        return
    today = dt.date.today()
    for f in sorted(APT.glob("*.json")):
        n = json.loads(f.read_text(encoding="utf-8"))
        n.setdefault("key", f.stem)
        out = OUT / f"{n['key']}.json"
        if args and n["key"] not in args:
            continue
        if not args and out.exists():
            old = json.loads(out.read_text(encoding="utf-8"))
            if (today - dt.date.fromisoformat(old.get("fetched", "2000-01-01"))).days < FRESH_DAYS:
                continue
        res = run_notice(env, n)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        top = ", ".join(f"{r['kw']} {r['total']:,}" for r in res["rows"][:3])
        print(f"{n['key']}: {top}")


if __name__ == "__main__":
    main()
