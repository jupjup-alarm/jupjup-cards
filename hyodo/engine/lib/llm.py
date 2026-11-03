"""Anthropic API(콘솔 API 크레딧)로 글 작업을 돌린다 — 예약 작업(구독 주간 한도)을 아끼려고 (2026-11-04 운영자 결정).

키: 환경변수 ANTHROPIC_API_KEY (운영시트 '설정' B26). 값은 출력·커밋·보고하지 않는다.
쓴 토큰은 episodes/<편>/out/llm_usage.jsonl 에 한 줄씩 남는다.
"""
import base64, json, os, pathlib, re, sys, time, urllib.request, urllib.error

URL = "https://api.anthropic.com/v1/messages"
MODEL_SMART = os.environ.get("HYODO_MODEL_SMART", "claude-opus-5-5")    # 대본·팩트체크
MODEL_FAST = os.environ.get("HYODO_MODEL_FAST", "claude-sonnet-5-5")    # 문장·시각 검수
WEB_TOOLS = [{"type": "web_fetch_20260318", "name": "web_fetch", "max_uses": 25},
             {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]


def key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k:
        sys.exit("ANTHROPIC_API_KEY가 없어요 — 운영시트 '설정' B26 값을 환경변수로 넣어 주세요(키는 출력하지 말 것).")
    return k


def _post(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": key(), "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
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


def image_block(path):
    p = pathlib.Path(path)
    mt = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": mt,
                                        "data": base64.b64encode(p.read_bytes()).decode()}}


def ask(content, system="", model=None, web=False, max_tokens=16000, log=None, tag=""):
    """content: 문자열 또는 블록 목록. 서버 도구(web_fetch/web_search)를 쓰면 pause_turn을 이어 받는다.
    돌려주는 값: 마지막 답의 글(text 블록을 이은 것)."""
    model = model or MODEL_SMART
    msgs = [{"role": "user", "content": content}]
    body = {"model": model, "max_tokens": max_tokens, "messages": msgs}
    if system:
        body["system"] = system
    if web:
        body["tools"] = WEB_TOOLS
    use = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "web_fetch": 0, "web_search": 0}
    texts = []
    for _ in range(12):
        r = _post(body)
        u = r.get("usage", {})
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
            use[k] += u.get(k) or 0
        st = u.get("server_tool_use") or {}
        use["web_fetch"] += st.get("web_fetch_requests") or 0
        use["web_search"] += st.get("web_search_requests") or 0
        texts = [b.get("text", "") for b in r.get("content", []) if b.get("type") == "text"]
        if r.get("stop_reason") == "pause_turn":
            msgs.append({"role": "assistant", "content": r["content"]})
            continue
        if r.get("stop_reason") == "max_tokens":
            print(f"[llm] {tag} max_tokens에서 끊김", file=sys.stderr)
        break
    if log:
        log = pathlib.Path(log); log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M"), "tag": tag, "model": model, **use},
                               ensure_ascii=False) + "\n")
    print(f"[llm] {tag} {model} 입력 {use['input_tokens']:,} · 출력 {use['output_tokens']:,} 토큰"
          + (f" · fetch {use['web_fetch']} · search {use['web_search']}" if web else ""), file=sys.stderr)
    return "".join(texts)


def json_out(text):
    """답에서 마지막 ```json 블록(없으면 첫 { … 마지막 })을 읽는다."""
    m = re.findall(r"```json\s*(.*?)```", text, re.S)
    s = m[-1] if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(s)
