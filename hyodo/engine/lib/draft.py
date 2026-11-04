"""조사 + 대본 초안을 API 크레딧으로 (구독 주간 한도 아끼기, 2026-11-04).

python3 lib/draft.py episodes/<ID>-<slug> --brief <소재 메모 파일> [--minutes 8] [--mode solo|advisor]
  --mode solo(기본): Opus가 원문을 읽고 대본까지 쓴다.
  --mode advisor: Sonnet이 원문을 읽고 대본을 쓰고, Opus 어드바이저에게 두 번(원문을 다 읽은 뒤 구성 · JSON 내기 직전 점검) 묻는다.
  기본값은 환경변수 HYODO_DRAFT_MODE로 바꿀 수 있다.
  소재 메모: 소재조사 행(ID·카테고리·정책명·대상·핵심 숫자·마감·표지 훅·대표 출처)과 조사노트 사실 문장·출처, 지침로그 최근 방향을
  예약 작업이 텍스트로 모아 둔 파일.
→ episodes/<편>/research.md, video.json 을 새로 쓴다(이미 있으면 .bak으로 남김). 공식 원문은 Opus가 web_fetch로 직접 연다.
그다음은 README 그대로: review.py fact/style → 빌드 → review.py visual → …
"""
import json, os, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import llm

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()
EXAMPLE = ROOT / "episodes" / "S-0001-youth-future"


def section(title_prefix):
    m = re.search(rf"^## {re.escape(title_prefix)}.*?(?=^## )", README, re.S | re.M)
    return m.group(0) if m else ""


def main():
    ep = pathlib.Path(sys.argv[1])
    args = sys.argv[2:]
    brief = pathlib.Path(args[args.index("--brief") + 1]).read_text()
    minutes = args[args.index("--minutes") + 1] if "--minutes" in args else "8"
    mode = args[args.index("--mode") + 1] if "--mode" in args else os.environ.get("HYODO_DRAFT_MODE", "solo")
    ep.mkdir(parents=True, exist_ok=True)
    ex_video = (EXAMPLE / "video.json").read_text()
    ex_research = (EXAMPLE / "research.md").read_text()
    rules = "\n".join(section(t) for t in ("2. 조사", "3. video.json", "4. 문장 규칙", "4-1.", "4-2.", "4-3.", "하지 않는 것"))
    system = ("너는 시니어 대상 정책 유튜브 '효도알람'의 작가다. 진행자 '막내'(30대, 복지 제도에 빠삭한 집안 막내)가 존댓말로 말한다. "
              "한 문장에 정보 하나, 금액과 날짜는 두 번 말한다. 숫자·날짜·조건은 web_fetch로 연 공식 원문에서만 가져온다 — 기억으로 쓰지 않는다. "
              "블로그·유튜브는 근거가 아니다. 특정 금융상품 추천, 정당·정치인 평가, 개인별 수급 단정, 확정 전 숫자를 확정처럼 쓰기는 하지 않는다.")
    user = f"""다음 소재로 롱폼 {minutes}분 안팎(5분 이상, 같은 말 되풀이로 늘리지 말 것) 한 편의 research.md와 video.json을 써라.
영상마다 "부모님 해당 여부 → 자녀분 해당 여부"를 함께 짚는다(kids 장면은 반대 세대 혜택 1개 — 원문으로 확인).
대본 길이 감: 1분에 약 300자(say 글자 수 합 기준).

[소재 메모]
{brief}

[규칙 — README]
{rules}

[예시 research.md]
{ex_research}

[예시 video.json — 형식·장면 data 필드 이름만 따른다. 내용·숫자·kids 주제(청년미래적금)는 가져오지 말고 이번 소재로 새로. kids 장면은 이번 소재와 이어지는 반대 세대 혜택 1개, check 장면은 정확히 3문항]
{ex_video}

순서: ① 소재 메모의 출처와 공식 원문을 web_fetch로 열어 사실을 확인한다(요일은 직접 계산). ② research.md(사실·등급·출처·원문 발췌·주의)를 쓴다.
③ video.json을 쓴다(id·category·checked(오늘 날짜)·title·thumb·voice·tags·hashtags·playlist·sources·scenes 9종·shorts 2편).
마지막에 ```json 블록 하나로만 낸다: {{"research_md": "research.md 전체 글", "video": {{video.json 객체}}, "doubts": ["원문으로 확인 못 한 것·애매한 것"]}}"""
    if mode == "advisor":
        system += ("\n\n어드바이저(advisor 도구): 너보다 강한 검토자가 대화 전체를 보고 조언한다. 정확히 두 번 부른다 — "
                   "① 공식 원문을 다 열어 읽은 뒤, research.md·video.json을 쓰기 전에(장면 구성·강조할 숫자·빠진 조건을 묻는다) "
                   "② 마지막 ```json 블록을 내기 직전에(원문과 다른 숫자·날짜·요일, 확정 전 숫자를 확정처럼 쓴 곳, 문장 규칙 위반을 점검받는다). "
                   "조언은 무겁게 받아들이되, 원문과 다르면 원문을 따른다.")
        text = llm.ask(user, system=system, model=llm.MODEL_FAST, web=True, max_tokens=32000,
                       log=ep / "out" / "llm_usage.jsonl", tag="draft-advisor", advisor=llm.MODEL_SMART)
    else:
        text = llm.ask(user, system=system, model=llm.MODEL_SMART, web=True, max_tokens=32000,
                       log=ep / "out" / "llm_usage.jsonl", tag="draft")
    (ep / "out").mkdir(exist_ok=True)
    (ep / "out" / "draft_raw.md").write_text(text)
    res = llm.json_out(text)
    for name, body in (("research.md", res["research_md"]),
                       ("video.json", json.dumps(res["video"], ensure_ascii=False, indent=1) + "\n")):
        f = ep / name
        if f.exists():
            f.rename(f.with_suffix(f.suffix + ".bak"))
        f.write_text(body)
    v = res["video"]
    says = sum(len(x) for s in v.get("scenes", []) for x in s.get("say", []))
    print(json.dumps({"id": v.get("id"), "title": v.get("title"), "scenes": [s["id"] for s in v.get("scenes", [])],
                      "say_chars": says, "est_min": round(says / 300, 1), "doubts": res.get("doubts", [])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
