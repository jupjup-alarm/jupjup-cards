#!/usr/bin/env python3
"""'이미 반응이 증명된 소재' 찾기 — 유튜브 공개 수치로 국내 공포·미스터리 쇼츠 중 터진 영상을 모은다 (2026-11-03 사용자 결정:
"이미 반응이 증명된 소재를 우리 스타일로 만드는 걸 우선").

  python3 ossak/proven.py --scan [--global]          # 넓은 검색어로(--global: 해외 영어권 쇼츠도) 최근 1년 국내 쇼츠 상위 영상 → 소재 후보 찾기
  python3 ossak/proven.py --topic "디아틀로프" "메리 셀레스트"   # 그 사건을 다룬 국내 쇼츠의 조회·댓글 → 반응 증거
  옵션: --days 365  --min 300000  --json

키: 환경변수 YOUTUBE_API_KEY (없으면 GOOGLE_TTS_KEY — 설정 탭 B17, 출력·커밋 금지).
할당량: 검색 1번에 100단위(하루 1만) → 한 번에 검색어 20개 안쪽으로.
쓰는 법: 제목·조회·댓글은 '수요의 증거'로만 쓴다. 남의 대본·자막·그림·창작 괴담(이해하면 무서운 이야기 같은 창작물)은 가져오지 않는다.
실제 기록이 있는 사건이면 우리가 원문으로 다시 조사해 우리 훅·구성으로 만든다.
"""
import argparse, datetime, json, os, re, sys, urllib.parse, urllib.request

API = "https://www.googleapis.com/youtube/v3/"
SCAN = ["실화 괴담", "조선왕조실록 귀신", "실록 괴담", "미스터리 실화", "미제사건 쇼츠", "기묘한 실화", "소름 돋는 실화",
        "실종 미스터리", "흉가 실화", "심령사진", "세계 미스터리", "설명할 수 없는 사건", "조선 괴담", "귀신 기록",
        "유령선", "미스터리 사진", "공포 실화 쇼츠", "역사 속 미스터리"]
SCAN_GLOBAL = ["unsolved mystery", "creepy true story", "disappearance mystery", "haunted history", "unexplained photo",
               "strange historical record", "real ghost story", "mystery solved", "weird history facts", "ghost ship"]


def get(path, **q):
    q["key"] = os.environ.get("YOUTUBE_API_KEY") or os.environ["GOOGLE_TTS_KEY"]
    return json.load(urllib.request.urlopen(API + path + "?" + urllib.parse.urlencode(q), timeout=30))


def secs(s):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    return sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1))) if m else 0


def search(q, days, n=25, glob=False):
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    loc = {"regionCode": "US", "relevanceLanguage": "en"} if glob else {"regionCode": "KR", "relevanceLanguage": "ko"}
    r = get("search", part="snippet", q=q, type="video", videoDuration="short", order="viewCount",
            maxResults=n, publishedAfter=after, **loc)
    return [it["id"]["videoId"] for it in r.get("items", [])]


def stats(ids):
    out = []
    for i in range(0, len(ids), 50):
        r = get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))
        for v in r.get("items", []):
            s, d = v["statistics"], secs(v["contentDetails"]["duration"])
            if d > 180:
                continue
            out.append({"title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
                        "views": int(s.get("viewCount", 0)), "comments": int(s.get("commentCount", 0)),
                        "likes": int(s.get("likeCount", 0)), "sec": d, "date": v["snippet"]["publishedAt"][:10],
                        "url": "https://www.youtube.com/shorts/" + v["id"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--topic", nargs="*")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--min", type=int, default=0, help="이 조회수 이상만")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--global", dest="glob", action="store_true", help="해외(영어권) 쇼츠도 함께 (--scan은 해외 검색어 추가, --topic은 해외 결과도)")
    a = ap.parse_args()
    res = {}
    jobs = [(q, False) for q in (SCAN if a.scan else []) + (a.topic or [])]
    if a.glob:
        jobs += [(q, True) for q in (SCAN_GLOBAL if a.scan else []) + (a.topic or [])]
    for q, g in jobs:
        vids = sorted(stats(search(q, a.days, glob=g)), key=lambda v: -v["views"])
        res[("[해외] " if g else "") + q] = [v for v in vids if v["views"] >= a.min]
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    if a.scan:
        seen, allv = set(), []
        for vs in res.values():
            for v in vs:
                if v["url"] not in seen:
                    seen.add(v["url"]); allv.append(v)
        for v in sorted(allv, key=lambda v: -v["views"])[:60]:
            print(f'{v["views"]:>10,} 댓글{v["comments"]:>6,} {v["sec"]:>3}s {v["date"]} {v["channel"][:12]:12} | {v["title"][:60]} {v["url"]}')
    for q in [k for k in res if k.replace("[해외] ", "") in (a.topic or [])]:
        vs = res[q]
        top = vs[0] if vs else None
        print(f"## {q}: 쇼츠 {len(vs)}개" + (f" · 최고 {top['views']:,}회 댓글 {top['comments']:,} ({top['channel']}) {top['url']}" if top else " · 없음"))
        for v in vs[1:4]:
            print(f'   {v["views"]:>10,} 댓글{v["comments"]:>6,} {v["channel"][:12]} | {v["title"][:50]}')


if __name__ == "__main__":
    main()
