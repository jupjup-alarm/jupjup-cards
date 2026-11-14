"""⓪ 사진 검수 — 모델 API 없이 정기 작업(구독)이 눈으로 보고 표시 (2026-11-14 사용자 결정).

API 크레딧이 끝나 실행기(runner/s0.py qc)의 Sonnet 검수가 11/13부터 빠졌다. 그 대신 정기 오전 작업이
④ 디자인 전에 이 도구로 아직 안 본 그림만 접촉 시트로 보고 index.json에 같은 표시를 적는다
(checked·ok·name_shown·full·label·cat — s0.py qc와 같은 필드, ④ 릴스·⑦ SEO·블로그가 그대로 믿고 씀).

  python3 tools/review.py list [--max-keys 12] [--per-key 36] [--keys k1,k2] [-o 폴더]
      → 단지마다 번호 붙인 접촉 시트 <폴더>/review_<key>_<n>.jpg 와 목록(JSON)을 출력
  python3 tools/review.py apply 판정.json
      → {"<key>": {"items": [{"n": 1, "cat": "birdseye", "ok": true, "name_shown": false, "full": true, "label": "단지 낮 조감도"}]}}
        n은 list 출력의 번호. cat이 junk면 ok=false. 판정이 없는 번호는 그대로(다음에 다시 나옴).

판정 기준 (s0.py SYSTEM과 같음):
- ok: 단지 조감도·투시도·실제 커뮤니티·인테리어 투시도·평면·배치·위치도만 true. 흐림·깨짐·글자 표·광고 문구 위주·
  다른 단지(라벨에 다른 단지 이름)·워터마크·장식·스톡 사진(모델 인물·가족·마트·일반 도시 풍경·소품·무늬·로고)은 false.
  모르면 false.
- name_shown: 단지 이름·브랜드 로고가 크게 보이면 true (작은 블록 표시 'A-54블록'은 false)
- full: 세로 영상 배경으로 꽉 채워도 볼 만한 사진·조감도면 true (흰 바탕 그림·평면도·표·지도 그림은 false)
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_CATS = {"notice"}   # 공고문 컷은 실행기가 잘라 둔 것 — 검수 대상 아님


def today():
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")


def todo_of(idx):
    return [im for im in idx.get("images", []) if not im.get("checked") and im.get("cat") not in SKIP_CATS
            and (ROOT / im["file"]).exists()]


def contact(paths, out, start=0):
    from PIL import Image, ImageDraw
    tw, th, cols = 300, 260, 6
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * max(rows, 1)), "white")
    d = ImageDraw.Draw(sheet)
    for k, p in enumerate(paths):
        x, y = (k % cols) * tw, (k // cols) * th
        try:
            im = Image.open(ROOT / p).convert("RGB")
            im.thumbnail((tw - 8, th - 34))
            sheet.paste(im, (x + 4, y + 30))
        except OSError:
            pass
        d.rectangle([x + 4, y + 2, x + 64, y + 28], fill="black")
        d.text((x + 10, y + 7), f"[{start + k + 1}]", fill="white")
    sheet.save(out, quality=82)
    return str(out)


def cmd_list(a):
    out_dir = Path(a.o)
    out_dir.mkdir(parents=True, exist_ok=True)
    want = set(a.keys.split(",")) if a.keys else None
    res = []
    for idx_p in sorted((ROOT / "photos/site").glob("*/index.json")):
        key = idx_p.parent.name
        if want and key not in want:
            continue
        idx = json.loads(idx_p.read_text())
        todo = todo_of(idx)[:a.per_key]
        if not todo:
            continue
        sheets = [contact([im["file"] for im in todo[s:s + 18]], out_dir / f"review_{key}_{s // 18 + 1}.jpg", s)
                  for s in range(0, len(todo), 18)]
        res.append({"key": key, "name": idx.get("name", ""), "sheets": sheets,
                    "items": [{"n": k + 1, "file": im["file"].split("/")[-1], "cat": im["cat"], "from": im.get("from", ""),
                               "label": (im.get("label") or "")[:40], "size": f"{im.get('w')}x{im.get('h')}"}
                              for k, im in enumerate(todo)]})
        if len(res) >= a.max_keys:
            break
    left = sum(1 for p in (ROOT / "photos/site").glob("*/index.json") if todo_of(json.loads(p.read_text())))
    print(json.dumps({"keys": res, "unchecked_keys_total": left}, ensure_ascii=False, indent=1))


def cmd_apply(a):
    verdict = json.loads(Path(a.file).read_text())
    done = bad = 0
    for key, v in verdict.items():
        idx_p = ROOT / "photos/site" / key / "index.json"
        if not idx_p.exists():
            print(f"없는 key: {key}", file=sys.stderr)
            continue
        idx = json.loads(idx_p.read_text())
        todo = todo_of(idx)   # list 때와 같은 순서 (그 사이 새 그림이 붙으면 뒤에 붙으므로 번호는 그대로)
        for x in v.get("items", []):
            n = int(x["n"])
            if not 1 <= n <= len(todo):
                continue
            im = todo[n - 1]
            junk = x.get("cat") == "junk"
            if x.get("cat") and not junk:
                im["cat"] = x["cat"]
            im.update(checked=today(), ok=bool(x.get("ok")) and not junk, name_shown=bool(x.get("name_shown")),
                      full=bool(x.get("full")), label=x.get("label") or im.get("label", ""), checked_by="정기 작업")
            done += 1
            bad += not im["ok"]
        idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f"검수 {done}장 (못 씀 {bad})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list")
    l.add_argument("--max-keys", type=int, default=12)
    l.add_argument("--per-key", type=int, default=36)
    l.add_argument("--keys", default="")
    l.add_argument("-o", default="/tmp/review")
    p = sub.add_parser("apply")
    p.add_argument("file")
    a = ap.parse_args()
    {"list": cmd_list, "apply": cmd_apply}[a.cmd](a)
