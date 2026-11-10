"""⑦ SEO — 바뀐 공고만 고르기 (2026-11-09 사용자 결정 "매일 전체 대신 새 공고·정정·경쟁률 발표만").

입력: site/data/sheet/{applyhome,research,lh,myhome}.json (jupjup-runner assets 워크플로가 07:20·10:40·22:40에 내려 둠)
      + site/data/apt/*.json + site/data/notice_files/*.json
기억: site/data/sheet/seen.json — 공고 key별로 지난번 ⑦이 처리할 때의 원자료 지문(해시)

  python3 site/tools/changed.py              # 오늘 할 일 목록 (새 공고 / 바뀐 공고와 무엇이 바뀌었는지)
  python3 site/tools/changed.py --json       # 같은 내용을 JSON으로
  python3 site/tools/changed.py --mark KEY…  # 처리한 공고를 '처리함'으로 기록 (커밋할 것)
  python3 site/tools/changed.py --mark-all   # 지금 상태 전체를 기준으로 (첫날 전체 점검 뒤 한 번)

새 공고 = 원자료에 있는데 site/data/apt/{key}.json이 없음.
바뀐 공고 = 지문이 지난번과 다름 (어느 탭·어느 열이 바뀌었는지 같이 보여 줌 — 경쟁률·일정·가격·청약조사 H열 등).
정정공고 = notice_files/{key}.json 첨부 md5가 지난번 처리 때와 다름.
D-day·접수 상태 표시는 build.py가 날짜로 자동으로 바꾸니 여기서는 다루지 않는다.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "site/data"
SHEET = DATA / "sheet"
SEEN = SHEET / "seen.json"
IGNORE = {"_row", "받은 시각", "상세 받은 시각", "수집일"}      # 매번 바뀌는 시각 칸은 비교에서 뺌


def load(name):
    p = SHEET / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")).get("rows", []) if p.exists() else []


def norm(s):
    return re.sub(r"[\s()\[\]·,.\-]", "", str(s or "")).lower()


def fp(d):
    clean = {k: v for k, v in sorted(d.items()) if k not in IGNORE}
    return hashlib.md5(json.dumps(clean, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12], clean


def sources():
    """key → {출처: 원자료 dict} (청약조사는 이름으로 공고에 붙임)."""
    src = {}
    for r in load("applyhome"):
        k = str(r.get("주택관리번호", "")).strip()
        if k:
            src.setdefault(k, {})["청약홈API"] = r
    for r in load("lh"):
        k = str(r.get("공고ID", "")).strip()
        if k:
            src.setdefault(f"lh{k}", {})["LH공고"] = r
    apts = {}
    for p in (DATA / "apt").glob("*.json"):
        try:
            apts[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            apts[p.stem] = {}
    for r in load("myhome"):
        gid = str(r.get("공고ID", "")).strip()
        if not gid:
            continue
        keys = [k for k in apts if k == f"mh{gid}" or k.startswith(f"mh{gid}-")] or [f"mh{gid}"]
        for k in keys:
            src.setdefault(k, {}).setdefault("마이홈공고", []).append(r)
    # 청약조사 → 공고 key (제목·단지명·별칭·검색 이름이 같은 공고)
    names = {}
    for k, a in apts.items():
        for n in [a.get("title"), a.get("complex")] + list(a.get("aliases") or []) + list(a.get("search_names") or []):
            if n and len(norm(n)) >= 3:
                names.setdefault(norm(n), set()).add(k)
    for r in load("research"):
        n = norm(r.get("단지명") or r.get("C") or "")
        if not n:
            continue
        hit = names.get(n) or {k for nn, ks in names.items() for k in ks if len(n) >= 4 and (n in nn or nn in n)}
        for k in hit:
            src.setdefault(k, {}).setdefault("청약조사", []).append(r)
    # 공고문 첨부 지문 (md5) — notice_files의 changed 표시는 계속 남아 있어서 지난번 처리 때와 md5를 비교 (정정공고)
    for p in (DATA / "notice_files").glob("*.json"):
        try:
            nf = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        md5 = {f.get("name", ""): f.get("md5", "") for f in nf.get("files", []) if f.get("md5")}
        if md5 and p.stem in apts:
            src.setdefault(p.stem, {})["공고문 첨부"] = md5
    return src, apts


def diff_fields(old, new):
    keys = sorted(set(old) | set(new))
    return [k for k in keys if old.get(k) != new.get(k)]


def scan():
    src, apts = sources()
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    first = not seen
    new, changed = [], []
    for k, parts in sorted(src.items()):
        cur = {}
        for tab, v in parts.items():
            vs = v if isinstance(v, list) else [v]
            for j, one in enumerate(vs):
                h, clean = fp(one)
                cur[f"{tab}#{j}"] = {"h": h, "v": clean}
        if k not in apts:
            if set(parts) <= {"청약조사", "공고문 첨부"}:
                continue            # 청약조사에만 있는 이름(공고 전 등)은 아래 '공고 전 후보'로
            if k in seen and {a: b.get("h") for a, b in seen[k].items()} == {a: b["h"] for a, b in cur.items()}:
                continue            # 다른 공고 페이지가 이미 담은 공고(정정·중복)로 처리함 표시한 것 — 원자료가 안 바뀌면 다시 안 띄움
            title = (parts.get("청약홈API") or parts.get("LH공고") or (parts.get("마이홈공고") or [{}])[0]).get("주택명") \
                or (parts.get("LH공고") or {}).get("공고명") or (parts.get("마이홈공고") or [{}])[0].get("공고명", "")
            new.append({"key": k, "title": title, "from": sorted(parts)})
            continue
        old = seen.get(k, {})
        what = []
        for part, x in cur.items():
            o = old.get(part)
            if not o:
                what.append(f"{part.split('#')[0]} 새로 연결")
            elif o["h"] != x["h"]:
                f = diff_fields(o.get("v", {}), x["v"])
                tab = part.split('#')[0]
                what.append("공고문 첨부가 바뀜(정정공고 가능)" if tab == "공고문 첨부" else f"{tab}: " + ", ".join(f[:6]) + (" …" if len(f) > 6 else ""))
        if what and not first:
            changed.append({"key": k, "title": apts[k].get("title", ""), "what": what})
    return {"first_run": first, "new": new, "changed": changed, "_cur": {k: {
        f"{tab}#{j}": dict(zip(("h", "v"), fp(one)))
        for tab, v in parts.items() for j, one in enumerate(v if isinstance(v, list) else [v])} for k, parts in src.items()}}


def mark(keys, all_=False):
    res = scan()
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    for k, v in res["_cur"].items():
        if all_ or k in keys:
            seen[k] = v
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"처리함 기록: {'전체 ' + str(len(res['_cur'])) if all_ else len(keys)}개 → {SEEN.relative_to(ROOT)}")


def main(a):
    if not (SHEET / "applyhome.json").exists():
        print("site/data/sheet/ 가 없음 — jupjup-runner assets 워크플로(시트 내보내기)가 아직 안 돌았음. 예전처럼 시트를 직접 읽어 전체 점검.")
        return
    if a[:1] == ["--mark"]:
        return mark(set(a[1:]))
    if a[:1] == ["--mark-all"]:
        return mark(set(), all_=True)
    res = scan()
    res.pop("_cur")
    if "--json" in a:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    dumped = json.loads((SHEET / "applyhome.json").read_text(encoding="utf-8")).get("dumped_at", "?")
    print(f"시트 내보낸 시각: {dumped}")
    if res["first_run"]:
        print("⚠ 기준(seen.json)이 없음 — 오늘은 예전처럼 전체 점검하고, 끝나면 `python3 site/tools/changed.py --mark-all`로 기준을 남겨.")
    print(f"\n새 공고 {len(res['new'])}개")
    for x in res["new"]:
        print(f"  + {x['key']}  {x['title']}  ({'·'.join(x['from'])})")
    print(f"\n바뀐 공고 {len(res['changed'])}개")
    for x in res["changed"]:
        print(f"  ~ {x['key']}  {x['title']}\n      " + "\n      ".join(x["what"]))
    print("\n그 밖의 공고는 손대지 않는다 (상태·D-day는 build.py가 날짜로 자동 갱신).")


if __name__ == "__main__":
    main(sys.argv[1:])
