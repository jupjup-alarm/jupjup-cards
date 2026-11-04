"""자동 검수를 API 크레딧으로 (구독 주간 한도 아끼기, 2026-11-04).

python3 lib/review.py fact   episodes/<편> [--apply]   # 팩트체크: 원문을 직접 열어 대조 (Opus + web_fetch)
python3 lib/review.py style  episodes/<편> [--apply]   # 문장 검수: README 4·4-1절 (Sonnet)
python3 lib/review.py visual episodes/<편> 그림.png …  # 시각 검수: 스냅샷 시트 (Sonnet, 그림 입력)

결과: out/review_<종류>.json, 판정 '통과'면 종료 코드 0, '반려'면 2.
--apply: 고칠 문장(now → fix)을 video.json에 그대로 바꿔 넣는다(정확히 한 번 나오는 것만). 바꾼 뒤 같은 검수를 한 번 더 돌린다.
검수는 대본을 쓴 맥락과 따로 돈다(새 API 대화) — README 5절의 '별도 에이전트' 조건을 만족한다.
"""
import json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import llm

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()


def section(title_prefix):
    m = re.search(rf"^## {re.escape(title_prefix)}.*?(?=^## )", README, re.S | re.M)
    return m.group(0) if m else ""


FMT = """마지막에 아래 형식의 ```json 블록 하나로만 판정을 낸다.
{"verdict": "통과" 또는 "반려", "summary": "한 줄", "fixes": [{"scene": "장면 id", "field": "say[2] 또는 data.rows[1][1] 같은 위치", "now": "지금 video.json에 있는 글자 그대로(정확히 복사)", "fix": "고친 글자", "why": "이유(팩트체크면 원문 발췌와 URL)"}]}
now는 video.json 원문과 한 글자도 다르지 않게 복사한다(바꿔 넣기에 쓴다). 고칠 게 없으면 fixes는 []."""


def fact(ep, spec, research):
    system = ("너는 시니어 대상 정책 유튜브 '효도알람'의 팩트체커다. 대본을 쓴 사람과 다른 사람이다. "
              "기억이나 짐작으로 판정하지 않는다. web_fetch로 공식 원문(부처 보도자료·정책브리핑·법령·복지로·기관 공지)을 직접 열어 확인한다. "
              "블로그·유튜브·커뮤니티는 근거가 아니다.")
    user = f"""아래 video.json의 모든 숫자·날짜·요일·기간·대상 조건·금액·기관명·전화번호·신청처·사이트 주소를 하나씩 원문과 대조해라.
- 요일은 달력으로 직접 계산해 확인한다.
- 예산안·정부안을 확정처럼 쓴 곳, 사실과 다른 공포 표현('폐지', '이제 못 받는다'), 개인별 수급을 단정한 곳도 잡는다.
- 원문에서 확인 못 한 숫자는 '반려' 사유다(빼거나 '기관 확인'으로 돌리는 fix를 낸다).
- 화면(data)과 내레이션(say) 둘 다 본다. `{{표시|읽기}}`는 앞이 화면, 뒤가 읽는 말 — 둘 다 맞아야 한다. ` / `는 쉼 표기라 무시.
- 각 확인 항목을 판정 전에 짧게 적어라(항목 · 원문 발췌 · URL · 맞음/틀림).

[research.md — 대본 쓴 사람의 조사 메모, 출처 주소 참고용]
{research}

[video.json]
{json.dumps(spec, ensure_ascii=False, indent=1)}

{FMT}"""
    return llm.ask(user, system=system, model=llm.MODEL_SMART, web=True, max_tokens=24000,
                   log=ep / "out" / "llm_usage.jsonl", tag="fact")


def style(ep, spec, research):
    rules = "\n".join(section(t) for t in ("3. video.json", "3-1.", "3-2.", "4. 문장 규칙", "4-1.", "4-2.", "4-3."))
    system = ("너는 '효도알람' 문장 검수자다. 60대 시청자가 일상에서 쓰는 말인지, 번역투·행정투가 없는지, 쉼 표기(` / `)가 규칙대로인지 본다. "
              "사실(숫자·날짜·조건)의 뜻은 절대 바꾸지 않는다.")
    user = f"""규칙:
{rules}

아래 video.json의 화면 문구(title, thumb, 모든 data 글자, shorts의 lines)와 say(롱폼 장면·숏츠 beats)를 한 줄씩 판정해라. 0초 규칙(hook 첫 문장·숏츠 첫 beat가 대상+손익인지)도 본다.
- 번역투(~에 대해, ~를 통해, ~으로 인해, ~하는 것이 가능, ~되어지다, ~하게 됩니다, 사물 주어 피동문), 명사로 뚝 끊긴 문구, '끝·완료·마감' 같은 두 뜻 말을 고친다.
- 쉼 표기: 넣어야 할 자리에 없는 ` / `, 넣으면 안 되는 자리(날짜·숫자와 단위·꾸미는 말과 명사 사이)의 ` / `, 5자 미만 구절, 32자 넘는 구절.
- 화면 문구가 길어 글자가 줄어들 만한 곳(표 한 칸 14자 넘음, 체크 문항 두 줄 넘음)은 짧게.
- 좋은 문장은 건드리지 않는다. 고칠 이유가 분명한 것만 fixes에 넣는다. fixes가 있어도 모두 적용하면 되는 수준이면 verdict는 '통과'.

[video.json]
{json.dumps(spec, ensure_ascii=False, indent=1)}

{FMT}"""
    return llm.ask(user, system=system, model=llm.MODEL_FAST, max_tokens=16000,
                   log=ep / "out" / "llm_usage.jsonl", tag="style")


def visual(ep, spec, images):
    rules = section("4-3.")
    blocks = [{"type": "text", "text": f"""너는 '효도알람' 영상 시각 검수자다. 아래 그림은 장면별 마지막 화면(스냅샷 시트)이다.
규칙:
{rules}
확인: 글자 줄바꿈·넘침·잘림, 화면 글자가 자막 자리(롱폼 y>830, 숏츠 y>1270)를 침범하는지, 글자가 너무 작아졌는지(본문이 보조 글자보다 작아 보이면),
캐릭터와 글자 겹침, 공식 캡처의 강조 박스가 보이는지, 빈 칸·깨진 글자(□)·영어 변수명이 보이는지.
글자 문제는 video.json에서 고칠 문구로 fixes를 낸다(now는 video.json 글자 그대로). 레이아웃 코드 문제라 문구로 못 고치면 fixes에 scene과 why만 적고 now·fix는 비운다.

[video.json 장면 목록] {json.dumps([{'id': s['id'], 'type': s['type']} for s in spec['scenes']], ensure_ascii=False)}

{FMT}"""}]
    for p in images:
        blocks.append({"type": "text", "text": f"그림: {pathlib.Path(p).name}"})
        blocks.append(llm.image_block(p))
    return llm.ask(blocks, model=llm.MODEL_FAST, max_tokens=8000,
                   log=ep / "out" / "llm_usage.jsonl", tag="visual")


def apply(ep, fixes):
    f = ep / "video.json"
    raw = f.read_text()
    spec = json.loads(raw)
    done, skipped = 0, []
    for x in fixes:
        now, new = x.get("now") or "", x.get("fix") or ""
        if not now or not new or now == new:
            skipped.append(x); continue
        # JSON 안의 글자로 비교(따옴표·역슬래시 이스케이프 맞춤)
        a, b = json.dumps(now, ensure_ascii=False)[1:-1], json.dumps(new, ensure_ascii=False)[1:-1]
        if raw.count(a) == 1:
            raw = raw.replace(a, b); done += 1
        else:
            skipped.append(x)
    json.loads(raw)  # 깨지지 않았는지
    f.write_text(raw)
    return done, skipped


def main():
    kind, ep = sys.argv[1], pathlib.Path(sys.argv[2])
    rest = sys.argv[3:]
    spec = json.loads((ep / "video.json").read_text())
    research = (ep / "research.md").read_text() if (ep / "research.md").exists() else ""
    if kind == "fact":
        text = fact(ep, spec, research)
    elif kind == "style":
        text = style(ep, spec, research)
    elif kind == "visual":
        imgs = [p for p in rest if not p.startswith("--")]
        if not imgs:
            sys.exit("시각 검수는 스냅샷 그림 경로가 필요해요")
        text = visual(ep, spec, imgs)
    else:
        sys.exit("종류: fact | style | visual")
    out = ep / "out"; out.mkdir(exist_ok=True)
    (out / f"review_{kind}.md").write_text(text)
    try:
        res = llm.json_out(text)
    except Exception:
        res = {"verdict": "반려", "summary": "판정 JSON을 읽지 못함 — review_%s.md 확인" % kind, "fixes": []}
    if "--apply" in rest and res.get("fixes"):
        n, skipped = apply(ep, res["fixes"])
        res["applied"] = n
        res["not_applied"] = skipped
    (out / f"review_{kind}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({"kind": kind, "verdict": res.get("verdict"), "summary": res.get("summary"),
                      "fixes": len(res.get("fixes") or []), "applied": res.get("applied"),
                      "not_applied": len(res.get("not_applied") or [])}, ensure_ascii=False))
    sys.exit(0 if res.get("verdict") == "통과" else 2)


if __name__ == "__main__":
    main()
