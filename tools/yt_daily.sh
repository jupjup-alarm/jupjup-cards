#!/bin/bash
# 줍줍알람 유튜브 쇼츠 예약 업로드 + 고정 댓글 — Claude 없이 도는 하루 실행기 (2026-11-23, Pro 요금제 전환으로 예약 작업 대체)
# launchd com.jupjup.youtube (매일 12:14) 가 부른다. 손으로: bash tools/yt_daily.sh
# 순서: git pull → yt_queue sync/next → 편마다 fetch → job.json → yt_upload.mjs → done/fail
#       → verify → comment-due 편마다 yt_comment.mjs → commented
# 지키는 선(docs/youtube_ego.md): 줍줍알람 채널에만, 글은 고치지 않음, 실패한 편은 바로 다시 올리지 않음, 로그인·캡차는 우회하지 않음.
set -u
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT=/Users/den/줍줍알람/jupjup-cards
JOBDIR=/Users/den/줍줍알람/유튜브
LOGDIR=$JOBDIR/logs; mkdir -p "$LOGDIR"   # 저장소 밖에 둔다(커밋 안 되게)
LOG=$LOGDIR/yt_daily.log
exec >>"$LOG" 2>&1
cd "$ROOT" || exit 1
echo "=== $(date '+%F %T') 시작"

git pull -q --rebase --autostash origin main || echo "⚠ git pull 실패 — 받은 그대로 진행"
python3 tools/yt_queue.py sync

# 1) 업로드
SLUGS=$(python3 tools/yt_queue.py next --json | python3 -c 'import json,sys; [print(d["slug"]) for d in json.load(sys.stdin)]')
up=0; bad=0
for slug in $SLUGS; do
  python3 tools/yt_queue.py fetch "$slug" >/dev/null || { python3 tools/yt_queue.py fail "$slug" --why "fetch 실패" --push; bad=$((bad+1)); continue; }
  python3 - "$slug" <<'EOF'
import json, sys
from pathlib import Path
slug = sys.argv[1]
q = json.loads(Path(f"/Users/den/줍줍알람/jupjup-cards/youtube/queue/{slug}.json").read_text(encoding="utf-8"))
d = Path(f"/Users/den/줍줍알람/유튜브/{slug}")
date, time = q["publish_at"][:10], q["publish_at"][11:16]
job = {"id": slug, "title": q["title"], "description": q["description"], "tags": q.get("tags", []),
       "video": str(d / f"{slug}.mp4"), "thumb": str(d / f"{slug}_thumb.jpg"),
       "date": date, "time": time, "mode": "schedule"}
Path("/Users/den/줍줍알람/유튜브/job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
EOF
  OUT=$(ego-browser nodejs < tools/yt_upload.mjs 2>&1); echo "$OUT" | tail -5
  RES=$(echo "$OUT" | grep '^RESULT ' | tail -1 | sed 's/^RESULT //')
  STATUS=$(echo "$RES" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("status",""))
except Exception: print("")')
  LINK=$(echo "$RES" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("link") or "")
except Exception: print("")')
  if [ "$STATUS" = "예약완료" ] || { [ "$STATUS" = "중복" ] && [ -n "$LINK" ]; }; then
    python3 tools/yt_queue.py done "$slug" --url "${LINK:-unknown}" --push; up=$((up+1))
  else
    WHY=$(echo "$OUT" | grep -E 'Error|RESULT' | tail -1 | cut -c1-200)
    python3 tools/yt_queue.py fail "$slug" --why "${WHY:-알 수 없는 오류}" --push; bad=$((bad+1))
    # 채널 전환·로그인 문제면 나머지 편도 같은 이유로 실패하니 멈춘다
    if echo "$OUT" | grep -qE '채널이 아님|로그인|signin|accounts.google'; then echo "채널/로그인 문제 — 남은 편 건너뜀"; break; fi
  fi
done

# 2) 게시된 편 채널 확인
python3 tools/yt_queue.py verify --push

# 3) 고정 댓글 (게시 시각이 지난 편)
pin=0
for slug in $(python3 tools/yt_queue.py comment-due | awk '/^[0-9]/{print $1}'); do
  python3 - "$slug" <<'EOF'
import json, sys
from pathlib import Path
q = json.loads(Path(f"/Users/den/줍줍알람/jupjup-cards/youtube/queue/{sys.argv[1]}.json").read_text(encoding="utf-8"))
Path("/Users/den/줍줍알람/유튜브/comment_job.json").write_text(
    json.dumps({"id": q["slug"], "url": q["url"], "comment": q["pinned_comment"]}, ensure_ascii=False), encoding="utf-8")
EOF
  OUT=$(ego-browser nodejs < tools/yt_comment.mjs 2>&1); echo "$OUT" | tail -3
  if echo "$OUT" | grep -qE '"status":"(고정완료|이미고정)"'; then
    python3 tools/yt_queue.py commented "$slug" --push; pin=$((pin+1))
  else
    echo "⚠ $slug 고정 댓글 실패 — 다음 실행에서 다시(이미 단 댓글은 고정만 함)"
  fi
done

echo "=== $(date '+%F %T') 끝 — 예약 ${up}편 · 실패 ${bad}편 · 고정 댓글 ${pin}편"
python3 tools/yt_queue.py status | grep -v '^\[건너뜀\]' | tail -8
