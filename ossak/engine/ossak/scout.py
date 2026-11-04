#!/usr/bin/env python3
"""오싹알람 소재 조사 — 무거운 글 작업(후보 고르기·원문 조사·사전 검수)을 콘솔 API 크레딧으로 돌린다
(2026-11-05 사용자 결정: "소재 조사도 API 우선 → 크레딧 다 쓰면 주간 한도(구독)로"). 효도알람 hyodo/engine/lib/llm.py를 같이 쓴다:
배치(요금 반값)가 기본, 시스템 규칙·긴 입력은 프롬프트 캐시(0.1배), 크레딧이 떨어지면 종료 코드 3.

  python3 ossak/scout.py --brief <메모 파일> --out <폴더> [--n 3] [--scan <proven.py --scan --global --json 결과>]

메모 파일(예약 작업이 시트에서 모아 텍스트로): '지침로그' 최근 행, '소재조사' 기존 사건명 전부(중복 금지), 상태 '조사중' 개수,
'유튜브' 탭 최근 14편 제목, '제보함' 사용 동의된 제보, 다음 ID(말머리별 마지막 번호 + 1 — 예: "W-0013 N-0009 M-0004 D-0001 A-0001").

하는 일 (예약 작업은 결과 JSON만 보고 시트에 쓴다 — 구독 사용량을 아끼는 게 목적):
  1. 터진 쇼츠 목록: --scan이 없으면 proven.py 넓은 검색(국내+해외, 30만+)을 직접 돈다 (키 GOOGLE_TTS_KEY)
  2. 후보 고르기 (Opus + 웹 검색): 실제 기록이 있는 사건만, 버리는 기준 적용, 결(공포/기묘/신기), 국내·영문 사건명
  3. 후보마다 반응 증명: proven.py로 같은 사건 국내·해외 쇼츠 최고 조회
  4. 후보마다 원문 조사 (Opus + web_fetch, 동시에): 사실 5~10개·등급·출처, 훅 후보 3개, 0초 장면, 실제 기록의 오답, 답·남는 의문,
     끝 단서, 실물 증거(원본 신문·사진·문서) 찾을 곳 — 2026-11-04 구성·편집 규칙에 맞춰
  5. 사전 검수 (Sonnet, 조사한 대화와 따로 — 사건을 모르는 성급한 시청자 역할)
  6. 점수(100점, 소재 조사 규칙 그대로) → 70점 미만 버림 → 상위 n개
→ <out>/rows.json: {"소재조사": [[A..N]], "조사노트": [[ID, 순번, 사실, 등급, URL, 주의]], "dropped": [...], "report": "..."}
   <out>/llm_usage.jsonl (토큰·추정 비용), <out>/*.json (단계별 원본)
종료 코드: 0 성공 / 3 API 크레딧 부족·키 없음 → 예약 작업은 예전 방식(하위 에이전트, 구독 사용량)으로 이어 간다 / 그 밖 오류.
"""
import argparse, concurrent.futures as cf, datetime, json, os, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO / "hyodo" / "engine" / "lib"))
sys.path.insert(0, str(HERE))
import llm      # noqa: E402  (효도알람과 같은 API 모듈 — 배치·캐시·크레딧 부족 처리)
import proven   # noqa: E402

PREFIX = {"세계기담": "W", "새벽괴담": "N", "미제파일": "M", "그날의 기록": "D", "그 후": "A"}

# 모든 단계가 같은 시스템 규칙을 쓴다 → 프롬프트 캐시로 두 번째 호출부터 0.1배
RULES = """너는 세로 쇼츠 채널 '오싹알람'(@ossak_alarm)의 소재 조사 담당이다. 오싹알람은 '기록으로 확인된, 말이 안 되는 이야기'를
1분 안팎 쇼츠로 만든다(유튜브 쇼츠 18:00 서사형 50~70초, 22:00 루프형 20~43초, 인스타 릴스). 말머리: 세계기담 · 새벽괴담 · 미제파일 · 그날의 기록 · 그 후.

[최우선 원칙 — 사용자 결정 2026-11-03] 국내·해외 쇼츠에서 이미 터진 실제 사건을 우리 스타일로 다듬어 올린다. 터졌다는 건 가능성이 높다는 것.
무서움으로만 판단하지 않는다 — 소재의 결대로: 공포(귀신·흉가·금기·있으면 안 되는 누군가) / 기묘(실종·설명 안 되는 디테일) / 신기('와, 진짜?' 싶은 기록·현상·발견).

[버리는 것 — 화제성보다 우선] 창작 괴담·'이해하면 무서운 이야기' 같은 남의 창작물, 연예인 썰, 드라마·예능·영화 클립, 최근 국내 사건·실종·살인,
아동 피해, 성범죄, 자살·자해 중심 사건, 재판 중인 사건, 범행 수법 상세. 국내 피해자·유족 실명·특정 정보 금지, 용의자·무죄자 실명·범인 암시 금지.

[사실 등급] A: 공식 기록 또는 독립 원문 2개 이상(괴이 기록은 "그렇게 기록됐다"가 A) / B: 주요 언론 2곳 이상 / C: 단일 출처·소문.
원문 우선(실록·고전 원문, 당시 신문 — 미국 의회도서관 Chronicling America, 네이버 뉴스라이브러리, 수사·조사 기관 기록, 학술 자료). 위키·커뮤니티·남의 영상은 소재 찾기용.
사실 문장은 한국어로 새로 쓴다. 남의 영상·기사 문장, 대본, 구성, 그림을 가져오지 않는다. 기억으로 쓰지 말고 연 원문에 있는 것만.

[만드는 방식 — 2026-11-04 구성·편집 규칙, 소재를 고를 때 이게 되는지 본다]
- 0초에 가장 이상한 장면을 눈으로 보여 줄 수 있어야 한다(떨어지는 고기, 초록 피부 아이, 계단 위 형체). 말로만 이상한 소재는 약하다.
- 사람의 행동·반응(놀람·만짐·먹음·올려다봄)이 기록에 있으면 좋다.
- 이상한 점이 3단 이상 세지는 순서로 쌓이고, 당시 실제로 나온 오답(그럴듯한 설명)이 기록에 있으면 좋다.
- 답이 있는 소재는 답 한 줄(75~85% 지점) + 의견 질문, 정말 답이 없는 소재·공포형은 끝 단서 질문.
- 실물 증거(옛 신문 지면·원본 사진·문서·지도)를 화면에 넣는다 — 저작권이 끝났거나 공개된 원본이 어디 있는지 찾는다(Chronicling America 검색어, 위키미디어 공용 파일 이름·라이선스, 실록 원문 주소).
- 표지 훅: 평범한 설명으로 1초 안에 안 풀리는 구체적 디테일 1개 + 사람·숫자. 답·원인은 훅·제목에 넣지 않는다. 화면 제목 2줄(줄당 10자 안팎).
- 리스크: 세계기담·새벽괴담 = 저 / 미제파일·그 후 = 중 / 그날의 기록 = 고 (사람이 다친 실제 사건이면 한 단계 올린다).

답은 마지막에 ```json 블록 하나로만 낸다."""


def scan_lines(scan):
    seen, allv = set(), []
    for vs in scan.values():
        for v in vs:
            if v["url"] not in seen:
                seen.add(v["url"]); allv.append(v)
    allv.sort(key=lambda v: -v["views"])
    return "\n".join(f'{v["views"]:,}회 댓글{v["comments"]:,} {v["sec"]}s {v["date"]} [{v["channel"][:14]}] {v["title"][:70]} {v["url"]}'
                     for v in allv[:70])


def pick(brief, scan_txt, n, out):
    user = f"""[예약 작업이 모은 메모]
{brief}

[최근 1년 국내·해외 공포·미스터리 쇼츠 상위 영상 — proven.py, 조회순]
{scan_txt}

할 일: 위 터진 영상들(필요하면 web_search로 국내 커뮤니티 최근 30일 '이거 진짜야?' 글, 해외 쇼츠·Reddit 반복 소재, 다가오는 기념일도 몇 번 찾아본다)에서
'실제 기록이 있는 사건' 후보를 {n + 3}개 고른다. 메모의 기존 사건명과 겹치면 안 된다(같은 사건 다른 이름도). 해외에서만 터지고 국내엔 아직 없는 소재는 기회로 본다.
버리는 기준에 걸리는데 반응이 컸던 것 1~2개는 dropped에 이유와 함께.
후보마다: ko(한국어 사건명, 검색용 짧게), en(영문 사건명), series(말머리), mood(공포|기묘|신기), year, country, why(터진 영상이 어떤 감정·반응으로 터졌는지 — 제목·댓글 말투 근거),
proof_hint(위 목록에서 이 사건을 다룬 영상 URL 1~2개, 없으면 빈 배열), visual0(0초에 보여 줄 가장 이상한 장면 한 줄), format(서사형|루프형).
```json {{"candidates": [{{"ko": "", "en": "", "series": "", "mood": "", "year": "", "country": "", "why": "", "proof_hint": [], "visual0": "", "format": ""}}], "dropped": [{{"topic": "", "views": 0, "reason": ""}}]}}```"""
    text = llm.ask(user, system=RULES, model=llm.MODEL_SMART, web=True, max_tokens=12000,
                   log=out / "llm_usage.jsonl", tag="scout-pick")
    res = llm.json_out(text)
    (out / "1_pick.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def proof(c, days=3650):
    """같은 사건 국내·해외 쇼츠 최고 조회 (proven.py — 유튜브 검색 1번에 100단위)."""
    best = {}
    for label, q, glob in (("kr", c.get("ko"), False), ("global", c.get("en"), True)):
        if not q:
            continue
        try:
            vs = sorted(proven.stats(proven.search(q, days, glob=glob)), key=lambda v: -v["views"])
        except Exception as e:      # 할당량(403/429) 등 — 증명 없이 진행하고 보고에 남긴다
            best[label] = {"error": str(e)[:120]}
            continue
        best[label] = vs[0] if vs else None
    return best


def research(c, out):
    user = f"""다음 사건을 원문 우선으로 조사해 오싹알람 소재 카드를 만든다. web_search로 원문을 찾고 web_fetch로 직접 열어 확인한다.

[사건] {c.get('ko')} / {c.get('en')} ({c.get('year')}, {c.get('country')}) · 말머리 {c.get('series')} · 결 {c.get('mood')} · {c.get('format')}
[터진 이유] {c.get('why')}
[0초 장면 후보] {c.get('visual0')}

낼 것:
- facts: 사실 5~10개 {{"text": 한국어 새 문장, "grade": "A|B|C", "url": 연 원문 주소, "note": 주의(기록마다 다른 숫자 등)}}. 훅이 될 디테일은 A/B로 확인. 널리 퍼진 오해는 facts에 grade "C"·note "퍼진 오해"로.
- hooks: 표지 훅 후보 3개(터진 영상 제목과 틀이 겹치지 않게, 결에 맞는 말투) + best(1초 안에 평범한 답이 안 떠오르는 것).
- title2: 화면 제목 2줄(줄당 10자 안팎, 답·원인 없이). detail: 평범한 설명으로 안 풀리는 디테일 한 줄.
- plot3: 세 줄 줄거리(답 포함 — 검수용). wrong: 당시 실제로 나온 오답·그럴듯한 설명(기록에 있는 것만, 출처 포함). answer: 가장 유력한 설명 한 줄(없으면 "답 없음").
- open_q: 남는 의문. clue: 끝 단서 후보(앞·중간에 깔 구체적 디테일 + 그걸 가리키는 마지막 질문, 완결된 문장). ending: "답+의견 질문" 또는 "단서 질문".
- evidence: 실물 증거 찾을 곳 2~4개 {{"what": 무엇(신문 지면·원본 사진·문서), "where": 주소 또는 Chronicling America 검색어·날짜 범위, "license": 공개·저작권 만료·CC 종류 등 확인한 것}}.
- people: 기록 속 사람의 행동·반응 1~3개. risk: 저|중|고 + 이유. source: 대표 출처 URL 하나.
- self: 자체 판단 {{"human": 0~10(사람·행동·사건 중심), "clue": 0~10(끝 단서), "angle": 0~5(터진 영상들과 다른 첫 1초를 만들 수 있나)}}.
```json {{"facts": [], "hooks": [], "best": "", "title2": ["", ""], "detail": "", "plot3": ["", "", ""], "wrong": [], "answer": "", "open_q": "", "clue": "", "ending": "", "evidence": [], "people": [], "risk": "", "source": "", "self": {{}}}}```"""
    tag = "scout-research-" + re.sub(r"\W+", "", c.get("en") or "x")[:20]
    text = llm.ask(user, system=RULES, model=llm.MODEL_SMART, web=True, max_tokens=12000,
                   log=out / "llm_usage.jsonl", tag=tag)
    return llm.json_out(text)


def review(cards, out):
    """사건을 모르는 성급한 시청자 — 조사한 대화와 따로(새 API 대화), 웹 없음."""
    items = []
    for i, (c, r) in enumerate(cards):
        pv = [p for p in (c.get("_proof", {}).get("kr"), c.get("_proof", {}).get("global")) if isinstance(p, dict) and p.get("title")]
        items.append(f"""## 후보 {i + 1} (결: {c.get('mood')})
표지 훅: {r.get('best')}
화면 제목: {' / '.join(r.get('title2', []))}
0초 장면: {c.get('visual0')}
세 줄 줄거리: {' / '.join(r.get('plot3', []))}
마지막 질문: {r.get('clue')}
이 소재로 이미 터진 영상: {' | '.join(f"{p['title'][:60]} ({p['views']:,}회, {p['sec']}초)" for p in pv) or '없음'}""")
    user = ("너는 이 사건들을 처음 듣는, 엄지로 쇼츠를 넘기는 성급한 한국 시청자다. 후보마다 답한다:\n"
            "① 1초 뒤 계속 볼지(yes/no와 이유) ② 그 결의 점수 1~5(공포=무서움, 기묘=기묘함, 신기=신기함·놀라움 — 신기형에 '안 무섭다'는 감점 사유가 아니다) "
            "③ 처음 떠오르는 평범한 답(동물·유성·이중노출·장난 등, 없으면 빈칸) ④ 마지막 질문에 댓글로 뭐라고 답하겠는지 "
            "⑤ 이미 터진 영상보다 우리 첫 1초가 더 궁금한가(더/비슷/덜).\n\n" + "\n\n".join(items) +
            '\n\n```json {"reviews": [{"n": 1, "watch": true, "why": "", "score": 4, "plain_answer": "", "comment": "", "vs": "비슷"}]}```')
    text = llm.ask(user, system="너는 냉정한 시청자 검수자다. 칭찬하려 하지 말고 넘길 것 같으면 넘긴다고 말한다. 답은 마지막 ```json 블록 하나로.",
                   model=llm.MODEL_FAST, max_tokens=6000, log=out / "llm_usage.jsonl", tag="scout-review")
    res = llm.json_out(text)
    (out / "3_review.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return {int(x.get("n", 0)): x for x in res.get("reviews", [])}


def top_views(p):
    return max([v["views"] for v in (p.get("kr"), p.get("global")) if isinstance(v, dict) and v.get("views")] or [0])


def score(c, r, rv):
    v = top_views(c.get("_proof", {}))
    s_proof = 30 if v >= 300000 else 22 if v >= 100000 else 15 if v >= 50000 else 8 if v >= 10000 else 0
    rs = int(rv.get("score") or 0)
    s_rev = rs * 5
    self_ = r.get("self") or {}
    grades = [f.get("grade") for f in r.get("facts", [])]
    s_fact = 10 if grades.count("A") + grades.count("B") >= 5 else 5 if grades.count("A") + grades.count("B") >= 3 else 0
    risk = (r.get("risk") or "중")[:1]
    s_risk = {"저": 10, "중": 5, "고": 0}.get(risk, 5)
    parts = {"증명": s_proof, "사전검수": s_rev, "사람·행동": min(10, int(self_.get("human") or 0)),
             "끝 단서": min(10, int(self_.get("clue") or 0)), "사실": s_fact, "우리 각도": min(5, int(self_.get("angle") or 0)), "리스크": s_risk}
    total = sum(parts.values())
    passed = rs >= 4 and (v >= 300000 or not (rv.get("plain_answer") or "").strip())
    return total, parts, passed, v


def fmt_proof(p):
    def one(x, label):
        if isinstance(x, dict) and x.get("views"):
            return f'{label} 최고 {x["views"]:,}회 ({x["channel"][:14]}, {x["url"]})'
        if isinstance(x, dict) and x.get("error"):
            return f"{label} 확인 실패"
        return f"{label} 없음"
    return "증명: " + one(p.get("kr"), "국내") + " / " + one(p.get("global"), "해외")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--scan", help="proven.py --scan --global --min 200000 --json 결과 파일 (없으면 직접 돈다)")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    brief = pathlib.Path(a.brief).read_text()
    llm.key()   # 키가 없으면 여기서 종료 코드 3 → 예약 작업이 예전 방식으로

    if a.scan:
        scan = json.loads(pathlib.Path(a.scan).read_text())
    else:
        scan = {}
        for q, g in [(q, False) for q in proven.SCAN] + [(q, True) for q in proven.SCAN_GLOBAL]:
            try:
                scan[("[해외] " if g else "") + q] = [v for v in proven.stats(proven.search(q, 365, glob=g)) if v["views"] >= 200000]
            except Exception as e:
                print("scan 실패:", q, str(e)[:100], file=sys.stderr)
        (out / "0_scan.json").write_text(json.dumps(scan, ensure_ascii=False, indent=1))

    picked = pick(brief, scan_lines(scan), a.n, out)
    cands = picked.get("candidates", [])
    for c in cands:
        c["_proof"] = proof(c)
    # 원문 조사는 후보마다 따로, 동시에 (배치 여러 개 — 한 배치씩 기다리면 몇 시간이 걸린다)
    with cf.ThreadPoolExecutor(max_workers=min(6, len(cands) or 1)) as ex:
        res = list(ex.map(lambda c: research(c, out), cands))
    cards = list(zip(cands, res))
    (out / "2_research.json").write_text(json.dumps([{"cand": c, "card": r} for c, r in cards], ensure_ascii=False, indent=1))
    rvs = review(cards, out)

    ranked = []
    for i, (c, r) in enumerate(cards):
        rv = rvs.get(i + 1, {})
        total, parts, passed, v = score(c, r, rv)
        ranked.append((total, passed, i, c, r, rv, parts, v))
    ranked.sort(key=lambda x: (-x[1], -x[0]))
    nexts = dict(re.findall(r"\b([WNMDA])-(\d{4})\b", brief))
    nexts = {k: int(v) for k, v in nexts.items()}
    rows_s, rows_n, kept, dropped = [], [], [], list(picked.get("dropped", []))
    for total, passed, i, c, r, rv, parts, v in ranked:
        why_drop = None
        if not passed:
            why_drop = f"사전검수 미통과(결 {rv.get('score')}점, 떠오른 답: {rv.get('plain_answer') or '-'})"
        elif total < 70:
            why_drop = f"점수 {total}점 < 70"
        elif len(kept) >= a.n:
            why_drop = f"하루 {a.n}개 초과(점수 {total})"
        if why_drop:
            dropped.append({"topic": c.get("ko"), "views": v, "reason": why_drop, "score": total})
            continue
        p = PREFIX.get(c.get("series"), "W")
        nexts.setdefault(p, 1)
        sid = f"{p}-{nexts[p]:04d}"; nexts[p] += 1
        kept.append(c)
        memo = "\n".join(x for x in [
            f"결: {c.get('mood')}", f"유형: {'공포형' if c.get('mood') == '공포' else '실화·실종' if c.get('mood') == '기묘' else '신기한 기록'}"
            + (" [루프형]" if c.get("format") == "루프형" else ""),
            f"0초 장면: {c.get('visual0')}", f"답: {r.get('answer')}", f"끝맺음: {r.get('ending')} — {r.get('clue')}",
            "오답(기록): " + "; ".join(r.get("wrong", []) if isinstance(r.get("wrong"), list) else [str(r.get("wrong"))]),
            f"열린 의문: {r.get('open_q')}", "사람 행동: " + "; ".join(r.get("people", [])),
            "실물 증거: " + "; ".join(f"{e.get('what')} — {e.get('where')} ({e.get('license')})" for e in r.get("evidence", [])),
            "훅 후보: " + " / ".join(r.get("hooks", [])), f"주의: {r.get('risk')}"] if x)
        basis = "\n".join([fmt_proof(c["_proof"]),
                           f"사전검수: 결 {rv.get('score')}점 / 계속 봄 {rv.get('watch')} / 떠오른 답: {rv.get('plain_answer') or '없음'} / 터진 영상 대비 {rv.get('vs')} / 예상 댓글: {rv.get('comment')}",
                           " · ".join(f"{k} {v_}" for k, v_ in parts.items()), "조사: API(scout.py)"])
        rows_s.append([sid, c.get("series"), c.get("ko"), "'" + str(c.get("year") or ""), c.get("country"), r.get("best"),
                       r.get("detail"), (r.get("risk") or "중")[:1], "조사중", r.get("source"), memo, c.get("why"), total, basis])
        for k, f in enumerate(r.get("facts", []), 1):
            rows_n.append([sid, k, f.get("text"), f.get("grade"), f.get("url"), f.get("note") or ""])
    report = "\n".join([f"추가 {len(rows_s)}개: " + ", ".join(f"{x[0]} {x[2]}({x[12]}점)" for x in rows_s)] +
                       [f"버림: {d.get('topic')} — {d.get('reason')}" for d in dropped[:6]])
    (out / "rows.json").write_text(json.dumps({"소재조사": rows_s, "조사노트": rows_n, "dropped": dropped, "report": report},
                                              ensure_ascii=False, indent=1))
    usage = [json.loads(l) for l in (out / "llm_usage.jsonl").read_text().splitlines() if l.strip()]
    usd = sum(u.get("usd_executor", 0) + u.get("usd_advisor_full", 0) + u.get("usd_search", 0) for u in usage)
    print(json.dumps({"added": [[x[0], x[2], x[12]] for x in rows_s], "facts": len(rows_n), "dropped": len(dropped),
                      "usd": round(usd, 3), "batch": sum(u.get("batch", 0) for u in usage),
                      "direct": sum(u.get("direct", 0) for u in usage)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
