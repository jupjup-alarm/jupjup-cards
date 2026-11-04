"""Anthropic API(콘솔 API 크레딧)로 글 작업을 돌린다 — 예약 작업(구독 주간 한도)을 아끼려고 (2026-11-04 운영자 결정).

키: 환경변수 ANTHROPIC_API_KEY (운영시트 '설정' B26, 없으면 engine/.env). 값은 출력·커밋·보고하지 않는다.
배치(Message Batches API, 요금 50%)가 기본이다: 요청을 배치로 넣고 끝날 때까지 기다린다(보통 1시간 안).
HYODO_BATCH_WAIT분(기본 45) 안에 안 끝나면 배치를 취소하고 바로(정가) 다시 부른다. HYODO_BATCH=0이면 처음부터 바로 부른다.
어드바이저(advisor_20260301, 베타): ask(advisor="claude-opus-5-5") — 싼 실행자 모델이 일하다 상위 모델에게 방향을 묻는다.
쓴 토큰·추정 비용(USD)은 episodes/<편>/out/llm_usage.jsonl 에 한 줄씩 남는다(어드바이저 몫은 따로).
"""
import base64, json, os, pathlib, re, sys, time, urllib.request, urllib.error

URL = "https://api.anthropic.com/v1/messages"
MODEL_SMART = os.environ.get("HYODO_MODEL_SMART", "claude-opus-5-5")    # 대본·팩트체크
MODEL_FAST = os.environ.get("HYODO_MODEL_FAST", "claude-sonnet-5-5")    # 문장·시각 검수, 어드바이저 방식의 실행자
WEB_TOOLS = [{"type": "web_fetch_20260318", "name": "web_fetch", "max_uses": 25},
             {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
ADVISOR_BETA = "advisor-tool-2026-03-01"

# 정가(USD / 100만 토큰): 입력, 캐시 쓰기(5분), 캐시 읽기, 출력 — platform.claude.com 가격표 2026-11-04 확인
PRICE = {"claude-opus-5-5": (4, 5, 0.20, 20), "claude-sonnet-5-5": (2, 2.5, 0.10, 10),
         "claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50), "claude-fable-5-1": (10, 12.5, 0.25, 50)}
SEARCH_USD = 10 / 1000

BATCH = os.environ.get("HYODO_BATCH", "1") != "0"
BATCH_WAIT = float(os.environ.get("HYODO_BATCH_WAIT", "45")) * 60


def key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k:
        import env
        k = env.load().get("ANTHROPIC_API_KEY")
    if not k:
        sys.exit("ANTHROPIC_API_KEY가 없어요 — 운영시트 '설정' B26 값을 환경변수로 넣어 주세요(키는 출력하지 말 것).")
    return k


def _headers(beta=None):
    h = {"x-api-key": key(), "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if beta:
        h["anthropic-beta"] = beta
    return h


def _req(url, body=None, method="POST", raw=False, beta=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers=_headers(beta))
    with urllib.request.urlopen(req, timeout=600) as r:
        b = r.read()
    return b if raw else json.loads(b)


def _batch(body, tag, beta=None):
    """한 요청짜리 배치. 끝나면 메시지 응답(dict), 시간 안에 안 끝나면 None."""
    b = _req(URL + "/batches", {"requests": [{"custom_id": "r1", "params": body}]}, beta=beta)
    bid, t0 = b["id"], time.time()
    print(f"[llm] {tag} 배치 {bid} 넣음 — 기다리는 중", file=sys.stderr)
    while True:
        time.sleep(20 if time.time() - t0 < 300 else 60)
        try:
            b = _req(f"{URL}/batches/{bid}", method="GET", beta=beta)
        except (urllib.error.URLError, TimeoutError):
            continue
        if b["processing_status"] == "ended":
            break
        if time.time() - t0 > BATCH_WAIT:
            try:
                _req(f"{URL}/batches/{bid}/cancel", {}, beta=beta)
            except Exception:
                pass
            print(f"[llm] {tag} 배치가 {BATCH_WAIT/60:.0f}분 안에 안 끝나 취소 — 바로 부름(정가)", file=sys.stderr)
            return None
    for line in _req(b["results_url"], method="GET", raw=True, beta=beta).decode().splitlines():
        if not line.strip():
            continue
        res = json.loads(line)["result"]
        if res["type"] == "succeeded":
            print(f"[llm] {tag} 배치 끝 ({(time.time()-t0)/60:.1f}분)", file=sys.stderr)
            return res["message"]
        print(f"[llm] {tag} 배치 결과 {res['type']}: {json.dumps(res.get('error'), ensure_ascii=False)[:300]} — 바로 부름", file=sys.stderr)
    return None


def _call(body, tag, stats, beta=None):
    if BATCH:
        try:
            r = _batch(body, tag, beta)
        except urllib.error.HTTPError as e:
            print(f"[llm] {tag} 배치 오류 {e.code}: {e.read().decode(errors='replace')[:300]} — 바로 부름", file=sys.stderr)
            r = None
        if r is not None:
            stats["batch"] += 1
            return r, True
    stats["direct"] += 1
    return _post(body, beta), False


def _post(body, beta=None):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers=_headers(beta))
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and i < 4:
                time.sleep(15 * (i + 1)); continue
            sys.exit(f"Anthropic API 오류 {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if i < 4:
                time.sleep(15 * (i + 1)); continue
            sys.exit(f"Anthropic API 연결 실패: {e}")


def _usd(model, it, batch):
    p = PRICE.get(model)
    if not p:
        return 0.0
    c = ((it.get("input_tokens") or 0) * p[0] + (it.get("cache_creation_input_tokens") or 0) * p[1]
         + (it.get("cache_read_input_tokens") or 0) * p[2] + (it.get("output_tokens") or 0) * p[3]) / 1e6
    return c * (0.5 if batch else 1)


def image_block(path):
    p = pathlib.Path(path)
    mt = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": mt,
                                        "data": base64.b64encode(p.read_bytes()).decode()}}


def ask(content, system="", model=None, web=False, max_tokens=16000, log=None, tag="",
        advisor=None, advisor_max_uses=3, advisor_max_tokens=2048):
    """content: 문자열 또는 블록 목록. 서버 도구(web_fetch/web_search/advisor)는 pause_turn을 이어 받는다.
    돌려주는 값: 마지막 답의 글(text 블록을 이은 것)."""
    model = model or MODEL_SMART
    msgs = [{"role": "user", "content": content}]
    body = {"model": model, "max_tokens": max_tokens, "messages": msgs}
    if system:
        body["system"] = system
    tools = list(WEB_TOOLS) if web else []
    beta = None
    if advisor:
        tools.append({"type": "advisor_20260301", "name": "advisor", "model": advisor,
                      "max_uses": advisor_max_uses, "max_tokens": advisor_max_tokens})
        beta = ADVISOR_BETA
    if tools:
        body["tools"] = tools
    use = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
           "web_fetch": 0, "web_search": 0, "batch": 0, "direct": 0,
           "advisor_calls": 0, "advisor_input_tokens": 0, "advisor_output_tokens": 0, "advisor_errors": [],
           "usd_executor": 0.0, "usd_advisor_batch": 0.0, "usd_advisor_full": 0.0, "usd_search": 0.0}
    texts = []
    for _ in range(16):
        r, was_batch = _call(body, tag, use, beta)
        u = r.get("usage", {})
        its = u.get("iterations") or [dict(u, type="message")]
        for it in its:
            if it.get("type") == "advisor_message":
                use["advisor_input_tokens"] += (it.get("input_tokens") or 0) + (it.get("cache_read_input_tokens") or 0) \
                    + (it.get("cache_creation_input_tokens") or 0)
                use["advisor_output_tokens"] += it.get("output_tokens") or 0
                am = it.get("model") or advisor
                use["usd_advisor_full"] += _usd(am, it, False)
                use["usd_advisor_batch"] += _usd(am, it, was_batch)
            else:
                for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                    use[k] += it.get(k) or 0
                use["usd_executor"] += _usd(model, it, was_batch)
        st = u.get("server_tool_use") or {}
        use["web_fetch"] += st.get("web_fetch_requests") or 0
        use["web_search"] += st.get("web_search_requests") or 0
        use["usd_search"] += (st.get("web_search_requests") or 0) * SEARCH_USD
        for b in r.get("content", []):
            if b.get("type") == "server_tool_use" and b.get("name") == "advisor":
                use["advisor_calls"] += 1
            if b.get("type") == "advisor_tool_result":
                c = b.get("content") or {}
                if c.get("type") == "advisor_tool_result_error":
                    use["advisor_errors"].append(c.get("error_code"))
        texts = [b.get("text", "") for b in r.get("content", []) if b.get("type") == "text"]
        if r.get("stop_reason") == "pause_turn":
            msgs.append({"role": "assistant", "content": r["content"]})
            continue
        if r.get("stop_reason") == "max_tokens":
            print(f"[llm] {tag} max_tokens에서 끊김", file=sys.stderr)
        break
    for k in list(use):
        if k.startswith("usd_"):
            use[k] = round(use[k], 4)
    if log:
        log = pathlib.Path(log); log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M"), "tag": tag, "model": model,
                                "advisor": advisor, **use}, ensure_ascii=False) + "\n")
    adv = (f" · 어드바이저 {advisor} {use['advisor_calls']}회 입력 {use['advisor_input_tokens']:,} 출력 {use['advisor_output_tokens']:,}"
           if advisor else "")
    print(f"[llm] {tag} {model} 입력 {use['input_tokens'] + use['cache_read_input_tokens']:,} · 출력 {use['output_tokens']:,} 토큰"
          + (f" · fetch {use['web_fetch']} · search {use['web_search']}" if web else "") + adv
          + f" · 배치 {use['batch']}회(반값)·바로 {use['direct']}회 · 약 ${use['usd_executor'] + use['usd_advisor_full'] + use['usd_search']:.3f}",
          file=sys.stderr)
    return "".join(texts)


def json_out(text):
    """답에서 마지막 ```json 블록(없으면 첫 { … 마지막 })을 읽는다."""
    m = re.findall(r"```json\s*(.*?)```", text, re.S)
    s = m[-1] if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(s)
