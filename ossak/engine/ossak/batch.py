#!/usr/bin/env python3
"""하루 전 배치 생성 (Gemini Batch API, 일반 요청의 절반 가격, 최대 24시간 소요).

  제출: python3 ossak/batch.py submit episodes/<편>      -> 아직 없는 컷을 한 번에 제출
  수거: python3 ossak/batch.py collect episodes/<편>     -> 끝났으면 panels/ 에 저장
  상태: python3 ossak/batch.py status episodes/<편>

운영: 발행 전날 제출 -> 다음 날 아침 수거 -> 빠진 컷만 render.py(일반 요청)로 보충.
"""
import json, pathlib, sys, time, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render import DEFAULT_MODEL, build_request, image_from_response, load_key, panel_refs  # noqa: E402

BASE = "https://generativelanguage.googleapis.com/v1beta/"
LIMIT = 19 * 1024 * 1024  # 인라인 요청 20MB 제한보다 여유 있게


def call(key, url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=170) as res:
        return json.load(res)


def submit(ep, key, model):
    spec = json.loads((ep / "episode.json").read_text(encoding="utf-8"))
    (ep / "panels").mkdir(exist_ok=True)
    reqs, keys, size = [], [], 0
    for p in spec["panels"]:
        if (ep / "panels" / f'{p["id"]}.png').exists():
            continue
        refs = panel_refs(ep, p)
        if any(not r.exists() for r in refs):
            print("레퍼런스 없음, 건너뜀:", p["id"])
            continue
        body, _ = build_request(spec, p, refs)
        item = {"request": body, "metadata": {"key": p["id"]}}
        size += len(json.dumps(item))
        if size > LIMIT:
            print("20MB 제한으로 나머지는 다음 배치로:", p["id"])
            break
        reqs.append(item)
        keys.append(p["id"])
    if not reqs:
        print("제출할 컷이 없습니다")
        return
    res = call(key, BASE + f"models/{model}:batchGenerateContent",
               {"batch": {"display_name": f'ossak-{spec["id"]}-{time.strftime("%Y%m%d%H%M")}',
                          "input_config": {"requests": {"requests": reqs}}}})
    job = {"name": res["name"], "model": model, "keys": keys, "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (ep / "batch_job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    print("제출 완료:", res["name"], len(keys), "컷")


def status(ep, key):
    job = json.loads((ep / "batch_job.json").read_text(encoding="utf-8"))
    st = call(key, BASE + job["name"])
    state = st.get("metadata", {}).get("state") or st.get("state")
    return job, st, state


def collect(ep, key):
    job, st, state = status(ep, key)
    print("상태:", state)
    if not st.get("done") and state not in ("JOB_STATE_SUCCEEDED", "BATCH_STATE_SUCCEEDED"):
        return 2
    holder = st.get("response") or st.get("dest") or {}
    items = holder.get("inlinedResponses", {})
    items = items.get("inlinedResponses", items) if isinstance(items, dict) else items
    got = []
    for it in items:
        k = it.get("metadata", {}).get("key")
        img = image_from_response(it.get("response", {})) if "response" in it else None
        if k and img:
            (ep / "panels" / f"{k}.png").write_bytes(img)
            got.append(k)
        else:
            print("실패:", k, json.dumps(it.get("error", it), ensure_ascii=False)[:200])
    missing = [k for k in job["keys"] if k not in got]
    job.update({"collected_at": time.strftime("%Y-%m-%d %H:%M:%S"), "got": got, "missing": missing})
    (ep / "batch_job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장", len(got), "컷 / 빠진 컷:", missing or "없음")
    return 0


if __name__ == "__main__":
    cmd, ep = sys.argv[1], pathlib.Path(sys.argv[2])
    model = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MODEL
    key = load_key()
    if cmd == "submit":
        submit(ep, key, model)
    elif cmd == "status":
        print(status(ep, key)[2])
    elif cmd == "collect":
        sys.exit(collect(ep, key))
