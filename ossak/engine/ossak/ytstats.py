#!/usr/bin/env python3
"""유튜브 공개 수치 가져오기 (API 키만, 계정 권한 없이) — 채널 @ossak_alarm.

  python3 ossak/ytstats.py                       # 채널의 공개 영상 목록과 조회·좋아요·댓글
  python3 ossak/ytstats.py --match tab.json      # '유튜브' 탭 값(A1:W, 2차원 배열 JSON)과 제목으로 짝지어
                                                 #   시트에 쓸 칸을 출력 → [{"row": 2, "L": 링크, "K": "게시됨", "N": 조회, "S": 좋아요, "T": 댓글, "W": 기준}]
키: 환경변수 YOUTUBE_API_KEY (없으면 GOOGLE_TTS_KEY — 사용자가 같은 키를 유튜브에도 쓰는 데 동의, 2026-10-27).
그 키의 Google Cloud 프로젝트에서 YouTube Data API v3가 켜져 있고, 키의 'API 제한'에 YouTube Data API v3가 들어 있어야 한다.
예약(비공개) 영상은 공개 전이라 보이지 않는다. 평균 시청률·구독 증가는 API 키로 볼 수 없다(스튜디오에서 수동).
"""
import argparse, datetime, json, os, re, sys, urllib.error, urllib.parse, urllib.request

API = "https://www.googleapis.com/youtube/v3/"


def get(path, missing_ok=False, **q):
    q["key"] = os.environ.get("YOUTUBE_API_KEY") or os.environ["GOOGLE_TTS_KEY"]
    try:
        return json.load(urllib.request.urlopen(API + path + "?" + urllib.parse.urlencode(q), timeout=30))
    except urllib.error.HTTPError as e:
        msg = e.read()[:300].decode(errors="ignore")
        if e.code == 404 and missing_ok:
            return {}
        if "blocked" in msg:
            sys.exit("API 키가 YouTube Data API를 막고 있어요 — Google Cloud → API 및 서비스 → 사용자 인증 정보 → 그 키 → "
                     "'API 제한사항'에 YouTube Data API v3를 추가하세요")
        sys.exit(f"유튜브 API 오류 {e.code}: {msg}")


def videos(handle="ossak_alarm"):
    ch = get("channels", part="contentDetails", forHandle=handle).get("items") or []
    if not ch:
        sys.exit("채널을 찾을 수 없어요: @" + handle)
    up = ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        # 아직 공개 영상이 하나도 없으면 업로드 목록이 없어 404 → 빈 목록
        r = get("playlistItems", missing_ok=True, part="contentDetails", playlistId=up, maxResults=50,
                **({"pageToken": tok} if tok else {}))
        ids += [it["contentDetails"]["videoId"] for it in r.get("items", [])]
        tok = r.get("nextPageToken")
        if not tok or len(ids) >= 300:
            break
    out = []
    for i in range(0, len(ids), 50):
        r = get("videos", part="snippet,statistics,status", id=",".join(ids[i:i + 50]))
        for v in r.get("items", []):
            s = v.get("statistics", {})
            out.append({"id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"],
                        "privacy": v.get("status", {}).get("privacyStatus"), "views": int(s.get("viewCount", 0)),
                        "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))})
    return out


def norm(t):
    t = re.sub(r"【[^】]*】", "", str(t))
    t = re.sub(r"#\S+", "", t)
    return re.sub(r"[\s,.?!…·'\"“”‘’~\-]", "", t)


def match(tab, vids):
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")
    ups = []
    for i, r in enumerate(tab[1:], start=2):
        r = list(r) + [""] * (23 - len(r))
        if str(r[10]).strip() == "보류":
            continue
        link = str(r[11])
        m = re.search(r"(?:shorts/|v=|youtu\.be/)([\w-]{11})", link)
        v = next((x for x in vids if m and x["id"] == m.group(1)), None)
        if not v:
            want = norm(r[4])
            v = next((x for x in vids if want and (norm(x["title"]) == want or norm(x["title"]).startswith(want)
                                                    or want.startswith(norm(x["title"])))), None)
        if not v:
            continue
        u = {"row": i, "L": "https://www.youtube.com/shorts/" + v["id"], "N": v["views"], "S": v["likes"],
             "T": v["comments"], "W": today + " (공개 누적)"}
        if v["privacy"] == "public" and str(r[10]).strip() != "게시됨":
            u["K"] = "게시됨"
        ups.append(u)
    return ups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", default="ossak_alarm")
    ap.add_argument("--match", help="유튜브 탭 값 JSON 파일")
    a = ap.parse_args()
    vids = videos(a.handle)
    if a.match:
        print(json.dumps(match(json.load(open(a.match)), vids), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(vids, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
