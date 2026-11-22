"""비축 가이드 칼럼 꺼내기 (2026-11-23 사용자 결정 — 요금제 변경 전 20편 미리 써 둠).

site/data/guide/_ready/<slug>.json 에 검수까지 끝난 칼럼을 쌓아 두고, 정기 ⑧이 하루 N편씩 꺼내 공개한다.
- 순서: _plan.json에서 status "ready"인 항목의 day → 목록 순서.
- 꺼낼 때: published·checked를 오늘로, 파일을 site/data/guide/<slug>.json 으로 옮김, _plan status "done"·published 기록.
- 출력: 꺼낸 slug와 그 칼럼 facts 중 다시 확인할 '변하는 숫자'(금리·한도·소득·세율·공고 숫자) 목록 — 정기 ⑧이 출처에서 다시 확인.

사용:
  python3 site/tools/guide_release.py --list            # 남은 비축분
  python3 site/tools/guide_release.py --n 2              # 2편 꺼내기 (오늘 날짜, KST)
  python3 site/tools/guide_release.py --n 2 --dry-run
"""
import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path

GDIR = Path(__file__).resolve().parent.parent / "data" / "guide"
READY = GDIR / "_ready"
PLAN = GDIR / "_plan.json"
VOLATILE = re.compile(r"금리|이율|한도|소득|자산|세율|요율|기준금리|보증금|임대료|월세|분양가|만원|억|%|공고")


def today_kst():
    return (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%Y-%m-%d")


def ready_items(plan):
    items = [it for it in plan["items"] if it.get("status") == "ready" and (READY / f"{it['slug']}.json").exists()]
    items.sort(key=lambda it: (it.get("day", 0), plan["items"].index(it)))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    items = ready_items(plan)
    if a.list or not a.n:
        print(f"비축 {len(items)}편")
        for it in items:
            print(f"  day {it.get('day')} · {it['slug']} · {it.get('category')}")
        return
    day = a.date or today_kst()
    out = []
    for it in items[: a.n]:
        src = READY / f"{it['slug']}.json"
        g = json.loads(src.read_text(encoding="utf-8"))
        g["published"] = day
        g["checked"] = day
        vol = [f"{f.get('item')}: {f.get('value')} ({f.get('source')}, {f.get('effective', '')})"
               for f in g.get("facts", []) if VOLATILE.search(f"{f.get('item')} {f.get('value')}")]
        out.append({"slug": it["slug"], "h1": g.get("h1"), "recheck": vol})
        if a.dry_run:
            continue
        (GDIR / f"{it['slug']}.json").write_text(json.dumps(g, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        src.unlink()
        img = READY / "img" / it["slug"]
        if img.exists():
            shutil.move(str(img), str(GDIR / "img" / it["slug"]))
        it["status"] = "done"
        it["published"] = day
        it["checked"] = day
    if not a.dry_run:
        PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"date": day, "released": out, "left": len(items) - len(out)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
