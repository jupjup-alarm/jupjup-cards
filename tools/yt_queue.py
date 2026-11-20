"""유튜브 쇼츠 업로드 대기열 (2026-11-20 사용자 결정 "줍줍알람 유튜브 채널에 공고 릴스를 업로드 — ego lite로 시간 예약").

흐름
  ① ④ 디자인이 '유튜브' 탭에 행을 쓴다 (제목·설명·태그·고정 댓글·영상·표지·시각·접수 마감).
  ② 실행기 assets.yml(모델 없음)이 그 탭을 site/data/sheet/youtube.json 으로 내려 둔다 (07:20·10:40·11:50·22:40 KST).
  ③ 사용자 Mac의 예약 작업(ego lite)이 이 도구로 대기열을 맞추고(sync) → 올릴 것을 고르고(next) → 파일을 받고(fetch)
     → YouTube Studio에서 '예약'으로 올린 뒤 → done 으로 기록하고 저장소에 올린다. 순서는 docs/youtube_ego.md.
  ④ 게시 시각이 지나면 고정 댓글을 단다(comment-due → commented).
  '유튜브' 탭 K열(상태)·L열(링크)은 시트의 유튜브 동기화 스크립트가 제목으로 영상을 찾아 1시간마다 채운다 — 이 도구는 시트에 쓰지 않는다.

대기열 파일: youtube/queue/<편ID>.json  (status: 대기 → 예약됨 → 게시됨 / 건너뜀 / 실패)

  python3 tools/yt_queue.py sync                 # youtube.json → 대기열 (새 행 추가·게시된 것 표시·무음/마감 지남 건너뜀)
  python3 tools/yt_queue.py next [--n 4]         # 지금 올릴 것: 예약 시각을 정해 저장하고 목록 출력 (JSON은 --json)
  python3 tools/yt_queue.py fetch <편ID> [--dir ~/줍줍알람/유튜브]   # 영상·표지 받기 + 붙여 넣을 글 파일
  python3 tools/yt_queue.py done <편ID> --url <유튜브 주소> [--push]
  python3 tools/yt_queue.py fail <편ID> --why "<원인>" [--push]
  python3 tools/yt_queue.py comment-due          # 게시 시각이 지났는데 고정 댓글을 안 단 것
  python3 tools/yt_queue.py commented <편ID> [--push]
  python3 tools/yt_queue.py status               # 한눈에 보기
  python3 tools/yt_queue.py channel              # 줍줍알람 채널 ID·Studio 주소
  python3 tools/yt_queue.py verify [--push]      # 게시된 편이 줍줍알람 채널에 있는지 (다른 채널이면 대기열로 되돌림)
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / "youtube" / "queue"
SRC = ROOT / "site" / "data" / "sheet" / "youtube.json"
KST = timezone(timedelta(hours=9))
LEAD_MIN = 40                 # 지금부터 이 분 뒤보다 이른 시각엔 예약하지 않음 (업로드·처리 시간)
SLOTS = ["08:30", "12:00", "19:30", "21:30"]   # 밀린 편을 올릴 빈 시각 (인스타 13:00·17:00과 안 겹치게)
PER_SLOT = 1
RESULT_DAYS = 3               # 청약 결과 편은 원래 날짜에서 3일까지만
CHANNEL_ID = "UCbIKC-joj_M279Tii7sLSiA"   # 줍줍알람 (@jupjup_alarm) — 투키즈노트 등 다른 채널에 올라가면 안 됨
CHANNEL_NAME = "줍줍알람"
MIN_DB = -32.0                # 이보다 조용하면 무음 편 — 올리지 않음 (11/4·11/5 무음 릴스)


def now():
    return datetime.now(KST)


def load(slug):
    p = Q / f"{slug}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save(d):
    Q.mkdir(parents=True, exist_ok=True)
    (Q / f"{d['slug']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def items():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Q.glob("*.json"))] if Q.exists() else []


def parse_dt(d, t):
    try:
        hh, mm = (t or "12:00").strip().split(":")[:2]
        return datetime.fromisoformat(d.strip()).replace(hour=int(hh), minute=int(mm), tzinfo=KST)
    except Exception:
        return None


def mean_db(slug):
    m = ROOT / "reels" / slug / "manifest.json"
    if m.exists():
        v = json.loads(m.read_text(encoding="utf-8")).get("mean_db")
        if v is not None:
            return float(v)
    mp4 = ROOT / "reels" / slug / "reel.mp4"
    if not mp4.exists():
        return None
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m2 = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
    return float(m2.group(1)) if m2 else None


def skip_reason(d):
    """올리면 안 되는 이유 (없으면 None)."""
    dl = (d.get("deadline") or "").strip()
    today = now().date()
    if re.fullmatch(r"\d{4}-\d\d-\d\d", dl) and date.fromisoformat(dl) < today:
        return f"접수 마감 지남({dl})"
    if dl == "공고 전":
        orig = parse_dt(d.get("date", ""), d.get("time", ""))
        if orig and (now() - orig).days > 7:
            return "공고 전 편 — 7일 넘게 지나 내용이 바뀌었을 수 있음"
    if dl == "결과":
        orig = parse_dt(d.get("date", ""), d.get("time", ""))
        if orig and (now() - orig).days > RESULT_DAYS:
            return f"청약 결과 편 — {RESULT_DAYS}일 넘게 지남"
    db = mean_db(d["slug"])
    if db is None:
        return "영상 파일 없음"
    if db < MIN_DB:
        return f"무음 영상({db:.1f}dB)"
    return None


def cmd_sync(a):
    if not SRC.exists():
        sys.exit(f"{SRC.relative_to(ROOT)} 없음 — 실행기 assets.yml(시트 내보내기)이 아직 안 돌았어요. git pull 후 다시")
    src = json.loads(SRC.read_text(encoding="utf-8"))
    new = upd = 0
    for r in src.get("rows", []):
        slug = (r.get("편ID") or "").strip()
        if not slug:
            continue
        sheet_state = (r.get("상태") or "").strip()
        cur = load(slug)
        if cur is None:
            if sheet_state not in ("", "대기"):
                continue                       # 이미 올라간 예전 편은 대기열에 넣지 않음
            cur = {"slug": slug, "status": "대기", "created": now().strftime("%Y-%m-%d %H:%M")}
            new += 1
        if cur["status"] == "대기":            # 아직 안 올린 편만 시트 내용으로 새로 고침
            cur.update({
                "row": r.get("_row"), "date": r.get("업로드일", ""), "time": r.get("시각", ""),
                "title": r.get("제목", ""), "description": r.get("설명", ""),
                "tags": [t.strip() for t in (r.get("태그") or "").split(",") if t.strip()],
                "pinned_comment": r.get("고정 댓글", ""), "video": r.get("영상 파일", ""),
                "thumb": r.get("표지(썸네일)", ""), "deadline": r.get("접수 마감", ""),
                "keywords": r.get("목표 검색어 3개", ""),
            })
            why = skip_reason(cur)
            if why:
                cur.update({"status": "건너뜀", "why": why})
        if sheet_state == "게시됨" and cur["status"] in ("대기", "예약됨"):
            cur.update({"status": "게시됨", "url": r.get("유튜브 링크") or cur.get("url", "")})
        save(cur)
        upd += 1
    print(f"sync: 새 {new} · 확인 {upd} (시트 내보낸 시각 {src.get('dumped_at', '?')})")
    cmd_status(a)


def taken_slots():
    out = {}
    for d in items():
        if d.get("publish_at") and d["status"] in ("대기", "예약됨", "게시됨"):
            out[d["publish_at"]] = out.get(d["publish_at"], 0) + 1
    return out


def plan_time(d, used):
    """예약 시각 정하기: 원래 시각이 아직 충분히 남았으면 그대로, 아니면 마감 전 가장 빠른 빈 SLOTS."""
    soon = now() + timedelta(minutes=LEAD_MIN)
    orig = parse_dt(d.get("date", ""), d.get("time", ""))
    if orig and orig >= soon:
        return orig
    dl = (d.get("deadline") or "").strip()
    last = datetime.fromisoformat(dl).replace(hour=9, minute=0, tzinfo=KST) if re.fullmatch(r"\d{4}-\d\d-\d\d", dl) else None
    day = now().date()
    for _ in range(14):
        for s in SLOTS:
            t = parse_dt(day.isoformat(), s)
            key = t.isoformat(timespec="minutes")
            if t < soon or used.get(key, 0) >= PER_SLOT:
                continue
            if last and t > last:
                return None
            return t
        day += timedelta(days=1)
    return None


def cmd_next(a):
    used = taken_slots()
    todo = [d for d in items() if d["status"] == "대기"]

    def order(d):   # 원래 시각이 남은 오늘 편 먼저, 그다음 마감 가까운 순
        orig = parse_dt(d.get("date", ""), d.get("time", ""))
        fresh = 0 if orig and orig >= now() + timedelta(minutes=LEAD_MIN) else 1
        dl = d.get("deadline") or ""
        return (fresh, dl if re.fullmatch(r"\d{4}-\d\d-\d\d", dl) else "9999", d["slug"])

    out = []
    for d in sorted(todo, key=order):
        why = skip_reason(d)
        if why:
            d.update({"status": "건너뜀", "why": why}); save(d); continue
        if d.get("publish_at") and datetime.fromisoformat(d["publish_at"]) >= now() + timedelta(minutes=LEAD_MIN):
            t = datetime.fromisoformat(d["publish_at"])
        else:
            t = plan_time(d, used)
            if t is None:
                d.update({"status": "건너뜀", "why": "마감 전에 예약할 빈 시각이 없음"}); save(d); continue
            d["publish_at"] = t.isoformat(timespec="minutes")
            key = d["publish_at"]
            used[key] = used.get(key, 0) + 1
            save(d)
        out.append(d)
        if len(out) >= a.n:
            break
    if a.json:
        print(json.dumps([{k: d.get(k) for k in ("slug", "publish_at", "title", "deadline")} for d in out], ensure_ascii=False, indent=1))
    else:
        if not out:
            print("올릴 것 없음")
        for d in out:
            t = datetime.fromisoformat(d["publish_at"])
            print(f"{d['slug']}  예약 {t:%Y-%m-%d %H:%M} (한국 시간)  마감 {d.get('deadline')}  | {d['title']}")


def cmd_fetch(a):
    d = load(a.slug) or sys.exit(f"대기열에 없음: {a.slug}")
    out = Path(a.dir).expanduser() / a.slug
    out.mkdir(parents=True, exist_ok=True)
    for key, name in (("video", f"{a.slug}.mp4"), ("thumb", f"{a.slug}_thumb.jpg")):
        local = ROOT / "reels" / a.slug / name
        dst = out / name
        if local.exists():
            dst.write_bytes(local.read_bytes())
        else:
            urllib.request.urlretrieve(d[key], dst)
    t = datetime.fromisoformat(d["publish_at"]) if d.get("publish_at") else None
    files = {
        "title.txt": d["title"],
        "description.txt": d["description"],
        "tags.txt": ", ".join(d.get("tags", [])),
        "comment.txt": d.get("pinned_comment", ""),
        "schedule.txt": (f"{t:%Y-%m-%d} {t:%H:%M} (한국 시간, Asia/Seoul)\n날짜: {t.year}년 {t.month}월 {t.day}일\n시각: {t:%H:%M}"
                         if t else "예약 시각 없음 — next 먼저"),
    }
    for n, v in files.items():
        (out / n).write_text(v.rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"dir": str(out), "video": str(out / f"{a.slug}.mp4"), "thumb": str(out / f"{a.slug}_thumb.jpg"),
                      "publish_at": d.get("publish_at"), "title_len": len(d["title"]),
                      "files": sorted(files)}, ensure_ascii=False, indent=1))
    if len(d["title"]) > 100:
        print("⚠ 제목이 100자 넘음 — 유튜브 제한", file=sys.stderr)


def push(msg):
    subprocess.run(["git", "add", "youtube"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    subprocess.run(["git", "commit", "-qm", msg], cwd=ROOT, check=True)
    for _ in range(4):
        if (subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"], cwd=ROOT).returncode == 0
                and subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=ROOT).returncode == 0):
            print("푸시 완료")
            return
    print("⚠ 푸시 실패 — 나중에 git push origin HEAD:main", file=sys.stderr)


def set_state(a, **kw):
    d = load(a.slug) or sys.exit(f"대기열에 없음: {a.slug}")
    d.update(kw, updated=now().strftime("%Y-%m-%d %H:%M"))
    save(d)
    print(f"{a.slug}: {d['status']}")
    if getattr(a, "push", False):
        push(f"youtube: {a.slug} {d['status']}")


def cmd_done(a):
    m = re.search(r"(?:shorts/|v=|youtu\.be/|/video/)([\w-]{11})", a.url)
    set_state(a, status="예약됨", url=(f"https://www.youtube.com/shorts/{m.group(1)}" if m else a.url),
              video_id=(m.group(1) if m else ""))


def cmd_fail(a):
    d = load(a.slug) or sys.exit(f"대기열에 없음: {a.slug}")
    tries = int(d.get("tries", 0)) + 1
    set_state(a, status=("실패" if tries >= 3 else "대기"), why=a.why, tries=tries)


def cmd_comment_due(a):
    due = [d for d in items() if d["status"] in ("예약됨", "게시됨") and d.get("pinned_comment") and not d.get("commented")
           and d.get("publish_at") and datetime.fromisoformat(d["publish_at"]) <= now() and d.get("url")]
    if not due:
        print("고정 댓글 달 것 없음")
    for d in due:
        print(f"{d['slug']}  {d['url']}\n  댓글: {d['pinned_comment'].splitlines()[0]} …")


def cmd_commented(a):
    d = load(a.slug) or sys.exit(f"대기열에 없음: {a.slug}")
    set_state(a, status=("게시됨" if d["status"] == "예약됨" else d["status"]), commented=now().strftime("%Y-%m-%d %H:%M"))


def channel_of(url):
    """공개된 쇼츠 주소 → (채널 ID, 채널 이름). 예약 중(비공개)이면 (None, None)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko"})
    try:
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return None, None
    cid = re.search(r'"(?:externalChannelId|channelId)":"(UC[\w-]{22})"', html)
    name = re.search(r'"ownerChannelName":"([^"]+)"', html)
    return (cid.group(1) if cid else None), (name.group(1) if name else None)


def cmd_verify(a):
    """게시된 편이 줍줍알람 채널에 올라갔는지 (게시 시각 지난 편만 확인 가능)."""
    bad = 0
    for d in items():
        if a.slug and d["slug"] != a.slug:
            continue
        if d["status"] not in ("예약됨", "게시됨") or not d.get("url") or d.get("channel_ok"):
            continue
        if datetime.fromisoformat(d.get("publish_at", "2100-01-01T00:00+09:00")) > now():
            continue
        cid, name = channel_of(d["url"])
        if cid is None:
            print(f"{d['slug']}: 아직 확인 못 함(비공개·처리 중)")
            continue
        if cid == CHANNEL_ID:
            d["channel_ok"] = True
            save(d)
            print(f"{d['slug']}: 채널 맞음 ({name})")
        else:
            bad += 1
            d.update({"status": "대기", "why": f"다른 채널에 올라감: {name} ({cid}) {d['url']} — 그 영상은 비공개로 바꾸고 줍줍알람에 다시", "wrong": d["url"]})
            d.pop("url", None); d.pop("publish_at", None)
            save(d)
            print(f"⚠ {d['slug']}: 다른 채널({name})에 올라감 → 대기열로 되돌림")
    if bad and getattr(a, "push", False):
        push("youtube: 다른 채널 업로드 되돌림")


def cmd_status(a):
    rows = items()
    by = {}
    for d in rows:
        by.setdefault(d["status"], []).append(d)
    for s in ("대기", "예약됨", "게시됨", "건너뜀", "실패"):
        for d in by.get(s, []):
            extra = d.get("publish_at") or ""
            print(f"[{s}] {d['slug']}  {extra}  {d.get('why', '')}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("sync")
    p = sp.add_parser("next"); p.add_argument("--n", type=int, default=4); p.add_argument("--json", action="store_true")
    p = sp.add_parser("fetch"); p.add_argument("slug"); p.add_argument("--dir", default="~/줍줍알람/유튜브")
    p = sp.add_parser("done"); p.add_argument("slug"); p.add_argument("--url", required=True); p.add_argument("--push", action="store_true")
    p = sp.add_parser("fail"); p.add_argument("slug"); p.add_argument("--why", required=True); p.add_argument("--push", action="store_true")
    sp.add_parser("comment-due")
    p = sp.add_parser("commented"); p.add_argument("slug"); p.add_argument("--push", action="store_true")
    sp.add_parser("status")
    p = sp.add_parser("verify"); p.add_argument("slug", nargs="?"); p.add_argument("--push", action="store_true")
    sp.add_parser("channel")
    a = ap.parse_args()
    {"sync": cmd_sync, "next": cmd_next, "fetch": cmd_fetch, "done": cmd_done, "fail": cmd_fail,
     "comment-due": cmd_comment_due, "commented": cmd_commented, "status": cmd_status, "verify": cmd_verify,
     "channel": lambda a: print(f"{CHANNEL_NAME} {CHANNEL_ID}\nhttps://studio.youtube.com/channel/{CHANNEL_ID}")}[a.cmd](a)


if __name__ == "__main__":
    main()
